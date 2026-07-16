import { describe, expect, it } from 'vitest';
import { useTradeDate } from './useTradeDate';

describe('useTradeDate', () => {
  it('uses the explicit date and can switch dates', () => {
    const state = useTradeDate('2026-07-16');

    expect(state.tradeDate.value).toBe('2026-07-16');
    state.setTradeDate('2026-07-17');
    expect(state.tradeDate.value).toBe('2026-07-17');
  });
});
