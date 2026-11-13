const task = await taskSpace("xy plotter agent api verification 20261113");
const page = task.page("p1");

await page.goto(
  "http://127.0.0.1:8000/xy-plotter.html?agent=1&fresh=1&cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);

const result = await page.evaluate(async () => {
  const api = window.XYPlotterAgent;
  const output = {};
  const run = async (action, params = {}) => {
    const value = await api.execute(action, params);
    if (!value.ok) throw new Error(action + ": " + value.error.code + " " + value.error.message);
    return value;
  };

  await run("project.replace", {
    title: "Remaining actions",
    curves: [
      { id: "first", name: "First", x: [1, 2, 3, 4], y: [2, 4, 9, 16] },
      { id: "second", name: "Second", x: [1, 2, 3, 4], y: [4, 5, 6, 7] },
    ],
    options: { cleanEnabled: false },
  });
  output.patch = await run("project.patch", {
    curves: [{ curveId: "c1", y: [3, 5, 8, 15] }],
    options: { title: "Patched title" },
  });
  output.update = await run("curve.update", {
    curveId: "c2",
    fields: { name: "Second updated", width: 4, color: "#123456" },
  });
  output.markerAdd = await run("marker.add", { curveId: "c1", pointIndex: 1 });
  output.markerRemove = await run("marker.remove", { curveId: "c1", pointIndex: 1 });
  output.markerToggle = await run("marker.toggle", { curveId: "c2", pointIndex: 2 });
  output.markerClear = await run("marker.clear");
  output.cursorUpdate = await run("cursor.update", {
    x: { on: true, v1: 1, v2: 3 },
  });
  output.cursorReset = await run("cursor.reset");
  output.eraseRegion = await run("cleanup.eraseRegion", {
    xMin: 2,
    xMax: 3,
    yMin: 4,
    yMax: 10,
    curveIds: ["c1"],
  });
  output.restore = await run("cleanup.restore");
  output.viewReset = await run("view.reset");
  output.example = await run("project.example");
  output.clear = await run("plot.clear");
  output.emptyRender = await api.execute("plot.render");
  output.invalid = await api.execute("not.a.real.action");
  return output;
});

console.log(
  JSON.stringify(
    {
      patch: result.patch.result.curves,
      update: result.update.result,
      markerRemove: result.markerRemove.result,
      markerToggle: result.markerToggle.result,
      markerClear: result.markerClear.result,
      cursorReset: result.cursorReset.result,
      eraseRegion: result.eraseRegion.result,
      restore: result.restore.result,
      example: result.example.result.curves,
      clear: result.clear.result,
      emptyRender: result.emptyRender,
      invalid: result.invalid,
    },
    null,
    2,
  ),
);
