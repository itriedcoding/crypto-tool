## Advanced Multi‑Language Crypto Mining Suite

Warning: Crypto mining may be restricted or illegal in your jurisdiction or against policies of your infrastructure provider. Ensure you have explicit authorization before proceeding. You are solely responsible for compliance, electricity costs, and security.

### Overview
This suite provides a production‑ready, multi‑language crypto mining control plane with:
- Python orchestrator and REST API
- PHP web dashboard
- Shell installers and lifecycle scripts
- Adapters for XMRig and cpuminer‑opt
- System telemetry, watchdogs, auto‑restart, log rotation, and more

### Features (40+)
- Process orchestration for multiple miners
- XMRig adapter (Monero RandomX)
- cpuminer‑opt adapter (many CPU algos)
- Config via YAML with examples
- REST API with token auth
- Start/stop/restart miners by ID
- Global stop/start all miners
- Per‑miner args and environment overrides
- Health checks and watchdog restarts
- Graceful shutdown
- Auto‑download miners (Linux)
- Update script for miners
- System metrics (CPU, RAM, load, temps when available)
- Miner metrics parsing (hashrate, accepted, rejected)
- Rolling metrics retention window
- Log files per miner with rotation
- JSON logs for API and events
- PHP dashboard with live stats
- Dashboard auth token support via API key
- Dark/light responsive UI
- Charts for hashrate and shares
- Pool connection status surface
- Error/event timeline
- Configurable donate level passthrough (XMRig)
- Auto‑switch scheduler (optional)
- CPU utilization limiting target
- Thread auto detection and overrides
- Grace period on start before health checks
- Backoff strategy on repeated failures
- Crash loop detection and quarantine
- API rate limiting and CORS control
- API key rotation without restart
- Safe exec with absolute paths and validation
- PID tracking and cleanup
- Cross‑arch handling (x64/arm64 best‑effort)
- Offline mode without downloads
- Idempotent setup and start scripts
- Self‑contained venv for Python components
- Minimal external dependencies
- Extensible miner adapter interface
- Structured logging with correlation IDs
- Ready for systemd/containerization

### Quick start (Linux)
1) Clone the repo and enter the directory.
2) Run:
```bash
chmod +x setup.sh start.sh stop.sh update_miners.sh
./setup.sh
```
3) Edit `config/config.yaml` and set:
   - `api.api_key`
   - Miner `wallet`, `pool_url`, and desired `threads`
4) Start services:
```bash
./start.sh
```
   - Orchestrator API: `http://127.0.0.1:8765`
   - Dashboard: `http://127.0.0.1:8080`

Stop services:
```bash
./stop.sh
```

Update miners to latest release:
```bash
./update_miners.sh
```

### REST API
All requests require header `X-API-KEY: <token>`.

- GET `/api/health`
- GET `/api/miners`
- GET `/api/miners/{id}`
- POST `/api/miners/{id}/start`
- POST `/api/miners/{id}/stop`
- POST `/api/miners/{id}/restart`
- POST `/api/miners/all/start`
- POST `/api/miners/all/stop`
- GET `/api/metrics/system`
- GET `/api/metrics/miners`
- POST `/api/config/reload`
- GET `/api/logs/{id}?lines=200`
- GET `/api/events?limit=200`

### Configuration
See `config/config.example.yaml` and copy to `config/config.yaml`.

### License
MIT — see `LICENSE`.

### Security note
Do not expose the API or dashboard directly to the internet. If you must, place them behind a reverse proxy with TLS, restrict by IP, and use strong unguessable API keys.
