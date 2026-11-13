const task = await taskSpace("xy plotter padding and wheel verification 20261113");
const page = task.page("p1");

await page.goto(
  "http://127.0.0.1:8000/xy-plotter.html?agent=1&fresh=1&cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);

const initial = await page.evaluate(async () => {
  const result = await window.XYPlotterAgent.execute("project.replace", {
    title: "Wheel zoom test",
    curves: [{ name: "S", x: [1, 2, 3, 4, 5], y: [2, 4, 9, 16, 25] }],
    options: { cleanEnabled: false },
  });
  const canvas = document.querySelector("#canvas").getBoundingClientRect();
  const plot = getPlotRect(readConfig());
  return {
    result,
    point: {
      x: canvas.left + plot.L + plot.W * 0.7,
      y: canvas.top + plot.T + plot.H * 0.4,
    },
  };
});

await page.mouse.move(initial.point.x, initial.point.y, {
  label: "定位缩放中心",
});
await page.mouse.wheel(0, -300, { label: "滚轮放大图表" });
await page.waitForTimeout(250);

const zoomed = await page.evaluate(() =>
  window.XYPlotterAgent.execute("chart.getSummary"),
);
const manual = await page.evaluate(async () => {
  await window.XYPlotterAgent.execute("view.set", {
    xMin: 1,
    xMax: 5,
    yMin: 2,
    yMax: 25,
  });
  return window.XYPlotterAgent.execute("chart.getSummary");
});

console.log(
  JSON.stringify(
    {
      initialBounds: initial.result.result.bounds,
      zoomedBounds: zoomed.result.bounds,
      manualBounds: manual.result.bounds,
      expectedPadding: {
        xMin: 0.8,
        xMax: 5.2,
        yMin: 0.85,
        yMax: 26.15,
      },
    },
    null,
    2,
  ),
);
