import assert from "node:assert/strict";
import test from "node:test";

const {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatDirectionalShares,
  formatEvidenceStrength,
  formatPlainShares,
} = (await import(new URL("./capitalSignals.ts", import.meta.url).href)) as typeof import("./capitalSignals");

test("positive A-share values are red and retain an upward marker and plus sign", () => {
  assert.equal(directionTone(1), "rise");
  assert.equal(formatDirectionalPercent(1.2), "▲ +1.20%");
  assert.equal(formatDirectionalCny(180_000_000), "▲ +1.8亿");
});

test("negative A-share values are green and retain a downward marker and minus sign", () => {
  assert.equal(directionTone(-1), "fall");
  assert.equal(formatDirectionalPercent(-1.2), "▼ -1.20%");
  assert.equal(formatDirectionalCny(-180_000_000), "▼ -1.8亿");
});

test("zero values stay neutral and missing values stay visibly missing", () => {
  assert.equal(directionTone(0), "neutral");
  assert.equal(directionTone(null), "neutral");
  assert.equal(formatDirectionalPercent(0), "0.00%");
  assert.equal(formatDirectionalPercent(null), "--");
  assert.equal(formatDirectionalCny(0), "0");
  assert.equal(formatDirectionalCny(null), "--");
});

test("evidence strength is a score rather than a probability", () => {
  assert.equal(formatEvidenceStrength(72.25), "72.3");
  assert.equal(formatEvidenceStrength(null), "--");
});

test("share stock values stay unsigned while share changes keep direction", () => {
  assert.equal(formatPlainShares(37_425_000_000), "374.25亿份");
  assert.equal(formatDirectionalShares(2_778_000_000), "▲ +27.78亿份");
  assert.equal(formatDirectionalShares(-2_778_000_000), "▼ -27.78亿份");
  assert.equal(formatPlainShares(null), "--");
});
