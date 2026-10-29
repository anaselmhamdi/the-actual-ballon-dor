import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import { DEFAULTS, verdicts, type Data } from "./src/model";
import { consoleGaps, decades, ledgerPanel } from "./src/render";

// Prerender the default ledger so the page carries its answer with scripting off.
export default defineConfig({
  plugins: [{
    name: "prerender-ledger",
    transformIndexHtml(html) {
      const data: Data = JSON.parse(readFileSync(new URL("./public/data.json", import.meta.url), "utf8"));
      const vs = verdicts(data, DEFAULTS);
      const awarded = vs.filter((v) => v.year.awarded);
      return html
        .replace("<!--LEDGER-->", decades(data).map((d) => ledgerPanel(data, vs, d, false)).join(""))
        .replace("<!--CHANGED-->", String(awarded.filter((v) => v.changed).length))
        .replace("<!--AWARDED-->", String(awarded.length))
        .replace("<!--GAPS-->", consoleGaps(data, vs));
    },
  }],
});
