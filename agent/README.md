# XY Plotter Agent API

The plotter exposes the same capabilities through an in-page JavaScript API and a
local HTTP bridge. The visible UI and GitHub Pages deployment remain static.

## Start the local bridge

From PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\agent\start-agent-bridge.ps1
```

The launcher:

- binds only to `127.0.0.1:8765`;
- generates an `X-Agent-Token`;
- opens a new agent tab in Microsoft Edge;
- falls back to Google Chrome if Edge is unavailable;
- stores exported artifacts under `agent-exports/`.

Options:

```powershell
.\agent\start-agent-bridge.ps1 -Browser chrome -Port 8765
.\agent\start-agent-bridge.ps1 -Token "your-local-token" -NoOpen
```

The Agent tab URL is printed at startup and includes:

```text
?agent=1&fresh=1&bridge=http://127.0.0.1:8765&token=...
```

Agent mode starts with a clean in-memory project and never reads or writes the
normal UI's `xy-plotter-state` localStorage entry.

## HTTP API

All endpoints except `/v1/health` require:

```text
X-Agent-Token: <token printed by the bridge>
```

Available endpoints:

```text
GET  /v1/health
GET  /v1/status
GET  /v1/capabilities
POST /v1/execute
```

Example:

```bash
curl -X POST http://127.0.0.1:8765/v1/execute \
  -H "Content-Type: application/json" \
  -H "X-Agent-Token: LOCAL_TOKEN" \
  -d '{
    "requestId": "demo-001",
    "action": "project.replace",
    "params": {
      "title": "ADC error",
      "xLabel": "Input voltage (mV)",
      "yLabel": "Error (mV)",
      "curves": [
        {"name": "Mon0", "x": [1,2,3,4,5], "y": [2,4,9,16,25]}
      ],
      "options": {"grid": true, "smooth": "line", "cleanEnabled": false}
    }
  }'
```

Then export:

```json
{
  "requestId": "demo-export-001",
  "action": "export.xlsx",
  "params": {
    "filename": "ADC_error",
    "download": true
  }
}
```

The export response includes `artifactPath`, `size`, `mime`,
`downloadTriggered`, and the current `revision`.

## Browser API

```js
const api = window.XYPlotterAgent;

await api.execute("project.replace", {
  title: "ADC error",
  curves: [
    {name: "Mon0", x: [1, 2, 3], y: [2, 4, 9]}
  ]
});

const summary = api.getSummary();
const state = api.getState();
const capabilities = api.getCapabilities();
```

Every action returns:

```js
{
  ok: true,
  action: "plot.render",
  revision: 2,
  result: {},
  warnings: [],
  error: null
}
```

Use `chart.getSummary` to verify curve counts, point counts, visible curves,
view bounds, markers, and hidden points without reading the canvas.

## Action catalog

The canonical list is [actions.json](actions.json). Important groups:

- `project.*`, `curve.*`, `plot.*`: replace or patch data and render.
- `view.*`, `style.*`, `label.setPosition`: zoom, pan, axes, theme, ticks.
- `marker.*`, `cursor.*`: exact markers and measurement cursors.
- `cleanup.*`, `stats.*`: filtering, undo/redo and statistics.
- `import.*`, `export.*`: CSV/XLSX import and PNG/CSV/XLSX export.
- `chart.*`, `capabilities.get`: machine-readable state and discovery.

Data changes should normally use `project.replace` so the old curves, settings,
hidden points, and plot are replaced atomically.

## Troubleshooting

- `BRIDGE_AUTH_FAILED`: use the token printed by the current bridge process.
- `BROWSER_TIMEOUT`: confirm the Agent tab is open and not frozen.
- `BROWSER_NOT_CONNECTED`: check `/v1/status`; reopen the printed Agent URL.
- Port already in use: start with another `-Port` and copy the new Agent URL.
- Edge unavailable: pass `-Browser chrome` after installing Chrome.
- Local page testing: pass `--page-url http://127.0.0.1:8000/xy-plotter.html`
  when invoking Python directly.
