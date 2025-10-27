<?php
// Simple PHP dashboard that queries the Python API.

$configPath = __DIR__ . '/../../config/config.yaml';
$apiUrl = null; // will be filled from config
$apiKey = 'change-me-32chars-min';

// Load api key from config if available
if (file_exists($configPath)) {
    $yaml = file_get_contents($configPath);
    if ($yaml !== false) {
        if (preg_match('/api_key:\s*"?([A-Za-z0-9_\-]{16,})"?/m', $yaml, $m)) {
            $apiKey = $m[1];
        }
        if (preg_match('/port:\s*(\d{2,5})/m', $yaml, $m2)) {
            $apiUrl = 'http://127.0.0.1:' . $m2[1];
        }
    }
}
if ($apiUrl === null) { $apiUrl = 'http://127.0.0.1:8765'; }

function api_get($path, $key) {
    global $apiUrl;
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $apiUrl . $path);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [ 'X-API-KEY: ' . $key ]);
    $res = curl_exec($ch);
    $http = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($http !== 200) return null;
    return json_decode($res, true);
}

$miners = api_get('/api/miners', $apiKey) ?? [];
$sys = api_get('/api/metrics/system', $apiKey) ?? [];
$metrics = api_get('/api/metrics/miners', $apiKey) ?? [];
$byId = [];
foreach ($metrics as $m) { $byId[$m['id']] = $m; }
?>
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Mining Suite Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #0f172a; color: #e2e8f0; }
header { padding: 16px; background: #111827; display: flex; justify-content: space-between; align-items: center; }
.card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 16px; margin: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; padding: 12px; }
button { background: #2563eb; color: white; border: 0; padding: 8px 12px; border-radius: 6px; cursor: pointer; }
button.secondary { background: #374151; }
.badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #374151; }
.status-running { color: #22c55e; }
.status-stopped { color: #ef4444; }
</style>
<script>
const API_BASE = '<?php echo htmlspecialchars($apiUrl); ?>';
async function apiPost(path) {
  const res = await fetch(API_BASE + path, { method: 'POST', headers: { 'X-API-KEY': '<?php echo htmlspecialchars($apiKey); ?>' } });
  if (!res.ok) alert('Request failed: ' + res.status);
  else location.reload();
}
async function showLogs(minerId) {
  const res = await fetch(API_BASE + '/api/logs/' + encodeURIComponent(minerId) + '?lines=200', { headers: { 'X-API-KEY': '<?php echo htmlspecialchars($apiKey); ?>' } });
  if (!res.ok) { alert('Failed to load logs'); return; }
  const data = await res.json();
  const text = 'STDOUT:\n' + (data.stdout || '') + '\n\nSTDERR:\n' + (data.stderr || '');
  const win = window.open('', '_blank');
  win.document.write('<pre style="white-space: pre-wrap; background:#0b1020; color:#e2e8f0; padding:12px;">' + 
    text.replaceAll('<', '&lt;') + '</pre>');
}
</script>
</head>
<body>
<header>
  <div>
    <strong>Advanced Mining Suite</strong>
  </div>
  <div>
    <button class="secondary" onclick="apiPost('/api/miners/all/start')">Start all</button>
    <button class="secondary" onclick="apiPost('/api/miners/all/stop')">Stop all</button>
  </div>
</header>

<div class="grid">
  <div class="card">
    <h3>System</h3>
    <div>CPU: <?php echo htmlspecialchars((string)($sys['cpu_percent'] ?? 'n/a')); ?>%</div>
    <div>Load: <?php echo htmlspecialchars((string)($sys['load_1'] ?? '0')); ?>, <?php echo htmlspecialchars((string)($sys['load_5'] ?? '0')); ?>, <?php echo htmlspecialchars((string)($sys['load_15'] ?? '0')); ?></div>
    <div>Memory: <?php echo htmlspecialchars((string)($sys['mem_used_mb'] ?? 0)); ?>/<?php echo htmlspecialchars((string)($sys['mem_total_mb'] ?? 0)); ?> MB (<?php echo htmlspecialchars((string)($sys['mem_percent'] ?? 0)); ?>%)</div>
  </div>

  <?php foreach ($miners as $m): $mid = $m['id']; $mm = $byId[$mid] ?? []; ?>
  <div class="card">
    <h3><?php echo htmlspecialchars($mid); ?></h3>
    <div>Status: <span class="badge <?php echo ($m['status'] === 'running') ? 'status-running' : 'status-stopped'; ?>"><?php echo htmlspecialchars($m['status']); ?></span></div>
    <div>PID: <?php echo htmlspecialchars((string)($m['pid'] ?? 'n/a')); ?></div>
    <div>Uptime: <?php echo htmlspecialchars((string)round(($m['uptime_sec'] ?? 0))); ?>s</div>
    <div>Hashrate: <?php 
        $hs = $mm['hashrate_hs'] ?? null;
        if ($hs === null) echo 'n/a';
        else if ($hs >= 1e9) echo round($hs/1e9,2).' GH/s';
        else if ($hs >= 1e6) echo round($hs/1e6,2).' MH/s';
        else if ($hs >= 1e3) echo round($hs/1e3,2).' kH/s';
        else echo round($hs,2).' H/s';
    ?></div>
    <div>Shares: <?php echo htmlspecialchars((string)($mm['accepted'] ?? 0)); ?> acc / <?php echo htmlspecialchars((string)($mm['rejected'] ?? 0)); ?> rej</div>
    <div style="height:160px; margin-top:10px;">
      <canvas id="chart_<?php echo htmlspecialchars(preg_replace('/[^A-Za-z0-9_\-]/','_', $mid)); ?>" height="120"></canvas>
    </div>
    <div style="margin-top:10px;">
      <button onclick="apiPost('/api/miners/<?php echo rawurlencode($mid); ?>/start')">Start</button>
      <button onclick="apiPost('/api/miners/<?php echo rawurlencode($mid); ?>/stop')">Stop</button>
      <button class="secondary" onclick="apiPost('/api/miners/<?php echo rawurlencode($mid); ?>/restart')">Restart</button>
      <button class="secondary" onclick="showLogs('<?php echo htmlspecialchars($mid); ?>')">Logs</button>
    </div>
  </div>
  <?php endforeach; ?>
</div>

<script>
const minersList = <?php echo json_encode(array_map(fn($x) => $x['id'], $miners)); ?>;
const charts = {};
function makeChart(id) {
  const ctx = document.getElementById('chart_' + id.replace(/[^A-Za-z0-9_\-]/g,'_'));
  if (!ctx) return;
  const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Hashrate (kH/s)', data: [], borderColor: '#60a5fa', tension: 0.2 }] },
    options: { responsive: true, plugins: { legend: { display: true } }, scales: { x: { display: false } } }
  });
  charts[id] = chart;
}
minersList.forEach(makeChart);

async function pollMetrics() {
  try {
    const res = await fetch(API_BASE + '/api/metrics/miners', { headers: { 'X-API-KEY': '<?php echo htmlspecialchars($apiKey); ?>' } });
    if (!res.ok) return;
    const data = await res.json();
    const now = new Date().toLocaleTimeString();
    data.forEach(m => {
      const c = charts[m.id];
      if (!c) return;
      const hs = m.hashrate_hs != null ? (m.hashrate_hs/1000.0) : null;
      if (hs == null) return;
      c.data.labels.push(now);
      c.data.datasets[0].data.push(hs);
      if (c.data.labels.length > 60) { c.data.labels.shift(); c.data.datasets[0].data.shift(); }
      c.update('none');
    });
  } catch (e) {}
}
setInterval(pollMetrics, 5000);
pollMetrics();
</script>

</body>
</html>
