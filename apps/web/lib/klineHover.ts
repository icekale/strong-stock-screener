export function resolveKlineHoverIndex(
  clientX: number,
  boundsWidth: number,
  chartWidth: number,
  plotLeft: number,
  plotRight: number,
  barCount: number,
): number | null {
  if (barCount <= 0 || boundsWidth <= 0) {
    return null;
  }
  const chartX = (clientX / boundsWidth) * chartWidth;
  if (chartX < plotLeft || chartX > plotRight) {
    return null;
  }
  const slot = (plotRight - plotLeft) / barCount;
  return Math.max(0, Math.min(barCount - 1, Math.floor((chartX - plotLeft) / Math.max(slot, 1))));
}

export function resolveCurrentPriceLabelX(chartWidth: number, plotRight: number, labelWidth: number): number {
  const gutterX = plotRight + 8;
  if (gutterX + labelWidth <= chartWidth - 4) {
    return gutterX;
  }
  return Math.max(4, chartWidth - labelWidth - 28);
}

export function formatKlineHoverDate(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length >= 8) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
  }
  return value;
}
