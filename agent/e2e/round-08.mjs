const task = await taskSpace("xy plotter agent api verification 20261113");
const page = task.page("p1");

await page.goto(
  "http://127.0.0.1:8000/xy-plotter.html?agent=1&fresh=1&cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);

const isolation = await page.evaluate(async () => {
  const key = "xy-plotter-state";
  const sentinel = JSON.stringify({ userSentinel: "do-not-change" });
  localStorage.setItem(key, sentinel);
  await window.XYPlotterAgent.execute("project.replace", {
    title: "Isolation check",
    curves: [{ name: "S", x: [1, 2], y: [3, 4] }],
  });
  const save = await window.XYPlotterAgent.execute("project.save");
  await new Promise((resolve) => setTimeout(resolve, 500));
  return {
    save,
    normalState: localStorage.getItem(key),
    agentStatePresent: localStorage.getItem("xy-plotter-agent-state") !== null,
  };
});

await page.reload();
await page.waitForFunction(() => window.XYPlotterAgent?.ready === true);
const afterFreshReload = await page.evaluate(() => ({
  summary: window.XYPlotterAgent.getSummary(),
  normalState: localStorage.getItem("xy-plotter-state"),
}));

console.log(JSON.stringify({ isolation, afterFreshReload }, null, 2));
