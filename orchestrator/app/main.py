from __future__ import annotations
import os
import threading
import time
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
import uuid

from .config import ConfigLoader
from .auth import verify_api_key
from .metrics import SystemMetricsCollector
from .miner_manager import MinerManager
from .models import HealthResponse, MinerRuntime, MinerMetrics
from .logging_setup import setup_logging, get_logger
from .models import MinerDefinition
from .events import EventLogger
from .logrotate import rotate_logs

APP_VERSION = "1.0.0"


def create_app() -> FastAPI:
    cfg_loader = ConfigLoader()
    cfg = cfg_loader.config

    setup_logging(cfg.logging.directory, cfg.logging.level)
    logger = get_logger(__name__)

    # Simple Request ID middleware
    def request_id_middleware(app):
        async def middleware(request: Request, call_next):
            req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        return middleware

    app = FastAPI(title="Advanced Mining Suite", version=APP_VERSION)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # CORS basic
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Auth dependency
    api_key_dep = verify_api_key(lambda: cfg_loader.config.api.api_key)

    # Managers
    events = EventLogger()
    miner_manager = MinerManager(
        log_directory=cfg.logging.directory,
        get_scheduling=lambda: cfg_loader.config.scheduling,
        events=events,
    )

    # Register miners
    for m in cfg.miners:
        try:
            miner_manager.register(MinerDefinition(**m.__dict__))
        except Exception as e:
            logger.error(f"failed registering miner {m.id}: {e}")

    # System metrics
    sys_metrics = SystemMetricsCollector(interval_sec=cfg.telemetry.metrics_interval_sec)
    if cfg.telemetry.enable_system_metrics:
        sys_metrics.start()

    # Background updater
    def background_loop() -> None:
        last_rotate = 0.0
        while True:
            try:
                if cfg_loader.maybe_reload():
                    logger.info("config reloaded")
                    # Apply dynamic changes for miners (add/update/remove)
                    # Build set of desired IDs
                    desired = {m.id: m for m in cfg_loader.config.miners}
                    miner_manager.synchronize(desired)
                miner_manager.update_statuses()
                miner_manager.watchdog()
                # Rotate logs roughly once per minute
                now = time.time()
                if now - last_rotate > 60:
                    rotate_logs(cfg.logging.directory, cfg.logging.rotate_mb, cfg.logging.keep)
                    last_rotate = now
            except Exception as e:
                logger.error(f"background loop error: {e}")
            time.sleep(2)

    threading.Thread(target=background_loop, name="bg-loop", daemon=True).start()

    @app.get("/api/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(status="ok", version=APP_VERSION)

    @app.get("/api/miners", dependencies=[Depends(api_key_dep)], response_model=List[MinerRuntime])
    async def list_miners():
        return [rt for _, rt in miner_manager.list_miners()]

    @app.post("/api/miners/{miner_id}/start", dependencies=[Depends(api_key_dep)])
    async def start_miner(miner_id: str):
        if miner_id not in miner_manager.adapters:
            raise HTTPException(status_code=404, detail="Miner not found")
        miner_manager.start(miner_id)
        return {"status": "starting"}

    @app.post("/api/miners/{miner_id}/stop", dependencies=[Depends(api_key_dep)])
    async def stop_miner(miner_id: str):
        if miner_id not in miner_manager.adapters:
            raise HTTPException(status_code=404, detail="Miner not found")
        miner_manager.stop(miner_id)
        return {"status": "stopped"}

    @app.post("/api/miners/{miner_id}/restart", dependencies=[Depends(api_key_dep)])
    async def restart_miner(miner_id: str):
        if miner_id not in miner_manager.adapters:
            raise HTTPException(status_code=404, detail="Miner not found")
        miner_manager.restart(miner_id)
        return {"status": "restarting"}

    @app.post("/api/miners/all/start", dependencies=[Depends(api_key_dep)])
    async def start_all():
        miner_manager.start_all()
        return {"status": "starting"}

    @app.post("/api/miners/all/stop", dependencies=[Depends(api_key_dep)])
    async def stop_all():
        miner_manager.stop_all()
        return {"status": "stopped"}

    @app.get("/api/metrics/system", dependencies=[Depends(api_key_dep)])
    async def get_system_metrics():
        m = sys_metrics.latest
        return (m.dict() if m else {})

    @app.get("/api/metrics/miners", dependencies=[Depends(api_key_dep)], response_model=List[MinerMetrics])
    async def get_miner_metrics():
        return miner_manager.get_metrics()

    @app.get("/api/miners/{miner_id}", dependencies=[Depends(api_key_dep)])
    async def get_miner(miner_id: str):
        if miner_id not in miner_manager.adapters:
            raise HTTPException(status_code=404, detail="Miner not found")
        rt = miner_manager.runtime.get(miner_id)
        mt = miner_manager.metrics.get(miner_id)
        df = miner_manager.adapters[miner_id].definition
        return {
            "runtime": rt.dict() if rt else {},
            "metrics": mt.dict() if mt else {},
            "definition": df.dict() if hasattr(df, 'dict') else df.__dict__,
        }

    @app.get("/api/events", dependencies=[Depends(api_key_dep)])
    async def list_events(limit: int = 200):
        return [e.__dict__ for e in events.list(limit=limit)]

    @app.post("/api/config/reload", dependencies=[Depends(api_key_dep)])
    async def reload_config():
        cfg_loader.reload()
        miner_manager.synchronize({m.id: m for m in cfg_loader.config.miners})
        return {"status": "reloaded"}

    @app.get("/api/logs/{miner_id}", dependencies=[Depends(api_key_dep)])
    async def tail_logs(miner_id: str, lines: int = 200):
        if miner_id not in miner_manager.adapters:
            raise HTTPException(status_code=404, detail="Miner not found")
        base = cfg.logging.directory
        outp = os.path.join(base, f"{miner_id}.out.log")
        errp = os.path.join(base, f"{miner_id}.err.log")
        def _tail(path: str) -> str:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = f.readlines()
                return ''.join(data[-min(max(lines, 1), 2000):])
            except FileNotFoundError:
                return ''
        return {"stdout": _tail(outp), "stderr": _tail(errp)}

    return app


app = create_app()
