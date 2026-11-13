const task = await taskSpace("xy plotter agent api verification 20261113");
const page = task.page("p1");

await page.goto(
  "http://127.0.0.1:8000/xy-plotter.html?cb=" + Date.now(),
  { timeout: 30_000 },
);
await page.waitForFunction(() => document.body.dataset.ready === "1");
await page.click("loc=role:button[name='示例']", { label: "绘制页面示例" });
await page.waitForFunction(
  () => document.querySelector("#status")?.textContent.includes("已绘制"),
  undefined,
  { timeout: 10_000 },
);
const state = await page.evaluate(() => ({
  ready: document.body.dataset.ready,
  apiVersion: window.XYPlotterAgent.version,
  agentMode: document.documentElement.dataset.agentMode,
  status: document.querySelector("#status").textContent,
  info: document.querySelector("#info").textContent,
  curveSections: document.querySelectorAll(".curve-sec").length,
}));

console.log(JSON.stringify({ state }, null, 2));
