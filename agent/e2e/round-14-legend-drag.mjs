const task = await taskSpace("xy plotter draggable legend verification 20261117");
const page = task.page("p1");
const baseUrl = "http://127.0.0.1:8000/xy-plotter.html";

await page.goto(
  baseUrl + "?agent=1&fresh=1&cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);

const initial = await page.evaluate(async () => {
  await window.XYPlotterAgent.execute("project.replace", {
    title: "Legend drag verification",
    curves: [
      { name: "SMU - ADC_ISense_IDAC5(mA)", x: [1, 2, 3], y: [3, 5, 8] },
      { name: "SMU - ADC_ISense_IDAC2(mA)", x: [1, 2, 3], y: [2, 4, 7] },
    ],
    options: { cleanEnabled: false },
    stats: { showFit: false },
  });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const canvas = document.querySelector("#canvas").getBoundingClientRect();
  const rect = legendRect;
  return {
    canvas: { left: canvas.left, top: canvas.top },
    rect,
    summary: window.XYPlotterAgent.getSummary(),
  };
});

const start = {
  x: initial.canvas.left + initial.rect.x + initial.rect.w / 2,
  y: initial.canvas.top + initial.rect.y + initial.rect.h / 2,
};
await page.mouse.click(start.x, start.y, { label: "单击图例验证显隐" });
await page.waitForTimeout(150);
const afterClick = await page.evaluate(() => window.XYPlotterAgent.getSummary());

const end = {
  x: Math.max(initial.canvas.left + 180, start.x - 340),
  y: start.y + 120,
};
await page.mouse.move(start.x, start.y, { label: "定位图例框" });
await page.mouse.down();
await page.mouse.move(end.x, end.y, { label: "拖动图例框" });
await page.mouse.up();
await page.waitForTimeout(200);

const afterDrag = await page.evaluate(async () => {
  const save = await window.XYPlotterAgent.execute("project.save");
  return {
    rect: legendRect,
    position: window.XYPlotterAgent.getState().legendPos,
    summary: window.XYPlotterAgent.getSummary(),
    save,
  };
});

await page.goto(baseUrl + "?agent=1&fresh=0&cb=" + Date.now(), {
  timeout: 30_000,
});
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);
await page.waitForTimeout(200);
const afterReload = await page.evaluate(() => ({
  rect: legendRect,
  position: window.XYPlotterAgent.getState().legendPos,
  summary: window.XYPlotterAgent.getSummary(),
}));

console.log(
  JSON.stringify(
    {
      initialRect: initial.rect,
      clickVisibility: {
        before: initial.summary.visibleCurveCount,
        after: afterClick.visibleCurveCount,
      },
      drag: {
        from: { x: initial.rect.x, y: initial.rect.y },
        to: afterDrag.rect,
        position: afterDrag.position,
        visibilityBefore: initial.summary.visibleCurveCount,
        visibilityAfter: afterDrag.summary.visibleCurveCount,
      },
      reload: {
        rect: afterReload.rect,
        position: afterReload.position,
        visibility: afterReload.summary.visibleCurveCount,
      },
    },
    null,
    2,
  ),
);
