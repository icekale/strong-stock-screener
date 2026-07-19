import { describe, expect, it } from 'vitest';
import {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatDirectionalShares,
  formatEvidenceStrength,
  formatPlainCny,
  formatPlainShares,
  stageLabel
} from './capitalSignals';

describe('capital signal formatting', () => {
  it('uses A-share rise semantics with an upward marker and plus sign', () => {
    expect(directionTone(1)).toBe('rise');
    expect(formatDirectionalPercent(1.2)).toBe('▲ +1.20%');
    expect(formatDirectionalCny(180_000_000)).toBe('▲ +1.8亿');
    expect(formatDirectionalShares(2_778_000_000)).toBe('▲ +27.78亿份');
  });

  it('uses A-share fall semantics with a downward marker and minus sign', () => {
    expect(directionTone(-1)).toBe('fall');
    expect(formatDirectionalPercent(-1.2)).toBe('▼ -1.20%');
    expect(formatDirectionalCny(-180_000_000)).toBe('▼ -1.8亿');
    expect(formatDirectionalShares(-2_778_000_000)).toBe('▼ -27.78亿份');
  });

  it('keeps zero neutral and missing values visible', () => {
    expect(directionTone(0)).toBe('neutral');
    expect(directionTone(null)).toBe('neutral');
    expect(formatDirectionalPercent(0)).toBe('0.00%');
    expect(formatDirectionalCny(0)).toBe('0');
    expect(formatDirectionalShares(0)).toBe('0份');
    expect(formatDirectionalPercent(null)).toBe('--');
    expect(formatDirectionalCny(null)).toBe('--');
    expect(formatDirectionalShares(null)).toBe('--');
  });

  it('formats plain financial values without directional markers', () => {
    expect(formatPlainCny(1_800_000_000)).toBe('18.0亿');
    expect(formatPlainShares(37_425_000_000)).toBe('374.25亿份');
    expect(formatPlainCny(null)).toBe('--');
    expect(formatPlainShares(null)).toBe('--');
  });

  it('formats evidence strength as a score and translates every signal stage', () => {
    expect(formatEvidenceStrength(72.25)).toBe('72.3');
    expect(formatEvidenceStrength(null)).toBe('--');
    expect(stageLabel('intraday')).toBe('盘中代理');
    expect(stageLabel('post_close')).toBe('盘后确认');
    expect(stageLabel('disclosure')).toBe('定期披露');
  });
});
