#!/usr/bin/env node

import { createRequire } from "node:module";

const require = createRequire(new URL("../apps/web/package.json", import.meta.url));
const { chromium } = require("playwright");

const baseUrl = process.env.VISUAL_QA_BASE_URL ?? "http://127.0.0.1:3110";
const route = "/chanlun?symbol=300308.SZ";
const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
];
const browser = await chromium.launch({ headless: true, channel: process.env.SMOKE_UI_CHANNEL ?? "chrome" });
const failures = [];

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  try {
    await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 45_000 });
    await page.waitForSelector(".tickflow-kline-chart", { timeout: 20_000 });
    await page.waitForTimeout(1_200);
    const metrics = await page.evaluate(() => {
      const chart = document.querySelector(".tickflow-kline-chart");
      const chartBox = chart?.getBoundingClientRect();
      const width = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
      const controls = [...document.querySelectorAll(".tickflow-kline-chart [role='toolbar'] > *")]
        .map((element) => element.getBoundingClientRect())
        .filter((box) => box.width > 0 && box.height > 0);
      const overlaps = controls.some((box, index) => controls.slice(index + 1).some((other) =>
        box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top,
      ));
      return {
        blank: !chartBox || chartBox.width < 100 || chartBox.height < 200 || !chart?.querySelector("canvas"),
        hasErrorOverlay: Boolean(document.querySelector("nextjs-portal, .nextjs-toast-errors-parent")),
        overflow: width > document.documentElement.clientWidth + 4,
        overlaps,
      };
    });
    await page.screenshot({ path: `/tmp/chanlun-${viewport.name}.png`, fullPage: true });
    for (const [key, failed] of Object.entries(metrics)) if (failed) failures.push(`${viewport.name}: ${key}`);
    for (const error of consoleErrors) failures.push(`${viewport.name}: console ${error}`);
  } catch (error) {
    failures.push(`${viewport.name}: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    await context.close();
  }
}

await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`visual-qa-chanlun passed at ${baseUrl}`);
