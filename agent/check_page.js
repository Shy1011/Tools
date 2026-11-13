const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "xy-plotter.html"), "utf8");
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) throw new Error("Inline plotter script was not found.");
new Function(match[1]);

const catalog = JSON.parse(
  fs.readFileSync(path.join(root, "agent", "actions.json"), "utf8"),
);
const catalogActions = new Set(catalog.actions.map((item) => item.name));
const handlerActions = new Set(
  [...match[1].matchAll(/case '([^']+)':/g)].map((item) => item[1]),
);
const missingHandlers = [...catalogActions].filter(
  (action) => !handlerActions.has(action),
);
const undocumentedHandlers = [...handlerActions].filter(
  (action) => !catalogActions.has(action),
);
if (missingHandlers.length || undocumentedHandlers.length) {
  throw new Error(
    "Action catalog mismatch: missing handlers=" +
      JSON.stringify(missingHandlers) +
      ", undocumented handlers=" +
      JSON.stringify(undocumentedHandlers),
  );
}
console.log(
  `Inline JavaScript syntax OK; ${catalogActions.size} catalog actions match handlers`,
);
