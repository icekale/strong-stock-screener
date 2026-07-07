#!/usr/bin/env node

const baseUrl = process.env.SMOKE_UI_BASE_URL ?? "http://127.0.0.1:3110";
const routes = ["/", "/auction", "/sectors", "/heatmap", "/watchlist", "/stock/002080.SZ", "/settings", "/sentiment"];
const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.warn("smoke:ui skipped: Playwright is not installed in this workspace.");
  process.exit(0);
}

const browser = await chromium.launch({ headless: true, channel: process.env.SMOKE_UI_CHANNEL ?? "chrome" });
const failures = [];

for (const viewport of viewports) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
  });

  for (const route of routes) {
    const page = await context.newPage();
    const failedResponses = [];
    const consoleErrors = [];

    page.on("response", (response) => {
      if (response.status() >= 400) {
        failedResponses.push(`${response.status()} ${response.url().replace(baseUrl, "")}`);
      }
    });
    page.on("console", (message) => {
      const text = message.text();
      if (message.type() === "error" || /warning|error|failed|404|500/i.test(text)) {
        consoleErrors.push(text.slice(0, 240));
      }
    });

    try {
      const response = await page.goto(`${baseUrl}${route}`, {
        waitUntil: "domcontentloaded",
        timeout: 45_000,
      });
      await page.waitForTimeout(route === "/sentiment" ? 2500 : 1200);

      const metrics = await page.evaluate(() => {
        const width = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
        const clientWidth = document.documentElement.clientWidth;
        return {
          hasNextError: Boolean(document.querySelector("nextjs-portal, .nextjs-toast-errors-parent")),
          hasHorizontalOverflow: width > clientWidth + 4,
          width,
          clientWidth,
        };
      });

      if (!response || response.status() >= 400) {
        failures.push(`${viewport.name} ${route}: navigation failed with ${response?.status() ?? "no response"}`);
      }
      if (metrics.hasNextError) {
        failures.push(`${viewport.name} ${route}: Next.js error overlay detected`);
      }
      if (metrics.hasHorizontalOverflow) {
        failures.push(`${viewport.name} ${route}: horizontal overflow ${metrics.width}/${metrics.clientWidth}`);
      }
      if (failedResponses.length > 0) {
        failures.push(`${viewport.name} ${route}: failed responses: ${failedResponses.join("; ")}`);
      }
      if (consoleErrors.length > 0) {
        failures.push(`${viewport.name} ${route}: console issues: ${consoleErrors.join("; ")}`);
      }
    } catch (error) {
      failures.push(`${viewport.name} ${route}: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      await page.close();
    }
  }

  await context.close();
}

await browser.close();

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log(`smoke:ui passed for ${routes.length} routes on ${viewports.length} viewports at ${baseUrl}`);
