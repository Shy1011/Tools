const task = await taskSpace("xy plotter agent api verification 20261113");
const page = task.page("p1");

await page.goto(
  "http://127.0.0.1:8000/xy-plotter.html?agent=1&fresh=1&cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(
  () => window.XYPlotterAgent && window.XYPlotterAgent.ready === true,
  undefined,
  { timeout: 15_000 },
);

const result = await page.evaluate(async () => {
  const api = window.XYPlotterAgent;
  const output = {};
  const run = async (action, params = {}) => {
    const value = await api.execute(action, params);
    if (!value.ok) {
      throw new Error(action + ": " + value.error.code + " " + value.error.message);
    }
    return value;
  };

  output.capabilities = api.getCapabilities();
  output.replace = await run("project.replace", {
    title: "Agent API verification",
    xLabel: "Voltage (mV)",
    yLabel: "Error (mV)",
    curves: [
      { name: "Curve A", x: [1, 2, 3, 4, 5], y: [2, 4, 9, 16, 25] },
      { name: "Curve B", x: [1, 2, 3, 4, 5], y: [5, 6, 7, 8, 9] },
    ],
    options: {
      grid: true,
      smooth: "line",
      cleanEnabled: false,
      theme: "light",
      explanation: "Automated API verification",
    },
  });
  output.style = await run("style.update", {
    titleSize: 20,
    xScale: "linear",
    yScale: "linear",
    ticks: 8,
  });
  output.viewSet = await run("view.set", {
    xMin: 0,
    xMax: 6,
    yMin: 0,
    yMax: 30,
  });
  output.viewZoom = await run("view.zoom", { factor: 0.8 });
  output.viewPan = await run("view.pan", { dx: 0.02, dy: -0.01 });
  output.labels = await run("label.setPosition", {
    title: { x: 0.5, y: 8 },
    xAxis: { t: 0.5, d: 40 },
    yAxis: { t: 0.5, d: 18 },
  });
  output.markerAdd = await run("marker.add", {
    curveId: "c1",
    pointIndex: 2,
  });
  output.markerByY = await run("marker.markByY", {
    curveId: "c2",
    y: 7,
  });
  output.markerOffset = await run("marker.setOffset", {
    curveId: "c1",
    pointIndex: 2,
    dx: 8,
    dy: -6,
  });
  output.cursor = await run("cursor.update", {
    x: { on: true, v1: 1, v2: 4 },
    y: { on: true, v1: 2, v2: 16 },
    readoutPos: { tx: 0.04, ty: 0.06 },
  });
  output.cleanup = await run("cleanup.configure", {
    enabled: false,
    window: 5,
    fillGaps: true,
  });
  output.hide = await run("cleanup.hideIndices", {
    curves: [{ curveId: "c1", indices: [1] }],
  });
  output.undo = await run("cleanup.undo");
  output.redo = await run("cleanup.redo");
  output.restore = await run("cleanup.restore");
  output.stats = await run("stats.configure", {
    xMin: 1,
    xMax: 5,
    source: "raw",
    fitCurveId: "c1",
    showFit: true,
  });
  output.statsRead = await run("stats.get");
  output.interaction = await run("interaction.update", {
    panMode: false,
    eraserMode: false,
    modeBadge: true,
    theme: "light",
  });
  output.added = await run("curve.add", {
    name: "Temporary",
    x: [1, 2],
    y: [3, 4],
  });
  output.removed = await run("curve.remove", { id: "c3" });
  output.reordered = await run("curve.reorder", { order: ["c2", "c1"] });
  output.saved = await run("project.save");
  output.cleared = await run("project.reset");
  output.loaded = await run("project.load");
  output.imported = await run("import.csv", {
    filename: "import.csv",
    content: "X,Y\n1,2\n2,4\n3,9\n4,16\n",
  });
  output.summary = api.getSummary();
  output.state = api.getState();
  return output;
});

console.log(
  JSON.stringify(
    {
      taskSpaceId: task.spaceId,
      page: page.label,
      actionCount: result.capabilities.actions.length,
      replace: result.replace.result,
      style: result.style.result,
      viewSet: result.viewSet.result,
      viewZoom: result.viewZoom.result,
      viewPan: result.viewPan.result,
      markerCount: result.summary.markerCount,
      hiddenPointCount: result.summary.hiddenPointCount,
      stats: result.statsRead.result.curves,
      reordered: result.reordered.result.map((curve) => curve.id),
      imported: result.imported.result,
      summary: result.summary,
      stateStatus: result.state.status,
      stateRevision: result.state.revision,
    },
    null,
    2,
  ),
);
