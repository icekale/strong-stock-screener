import { describe, expect, it } from 'vitest';
import {
  closeChangeTone,
  factorStatusLabel,
  formatVolumeRatio,
  signalLevelLabel,
  signalTone
} from './etfThreeFactor';

describe('ETF three-factor display helpers', () => {
  it('labels every signal level and assigns a visual tone', () => {
    expect(signalLevelLabel('high')).toBe('高确信');
    expect(signalLevelLabel('medium')).toBe('中确信');
    expect(signalLevelLabel('low')).toBe('低确信');
    expect(signalLevelLabel('incomplete')).toBe('数据不全');
    expect(signalTone('high')).toBe('danger');
    expect(signalTone('medium')).toBe('warning');
    expect(signalTone('low')).toBe('info');
    expect(signalTone('incomplete')).toBe('neutral');
  });

  it('distinguishes all factor data states', () => {
    expect(factorStatusLabel('available')).toBe('可用');
    expect(factorStatusLabel('pending')).toBe('待盘后');
    expect(factorStatusLabel('missing')).toBe('不可用');
    expect(factorStatusLabel('stale')).toBe('已过期');
  });

  it('formats volume ratios while preserving missing data', () => {
    expect(formatVolumeRatio(3)).toBe('3.00倍');
    expect(formatVolumeRatio(0)).toBe('0.00倍');
    expect(formatVolumeRatio(null)).toBe('--');
  });

  it('uses A-share close-change semantics', () => {
    expect(closeChangeTone(1.2)).toBe('rise');
    expect(closeChangeTone(-1.2)).toBe('fall');
    expect(closeChangeTone(0)).toBe('flat');
    expect(closeChangeTone(null)).toBe('flat');
  });
});
