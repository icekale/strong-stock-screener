"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";
import {
  clampHeatmapViewport,
  createHeatmapDragState,
  heatmapWheelZoomFactor,
  moveHeatmapDragState,
  type HeatmapDragState,
  zoomHeatmapViewport,
} from "./heatmapCanvasInteraction";
import {
  heatmapChangeColor,
  hitTestHeatmap,
  layoutHeatmapTreemap,
  transformHeatmapPoint,
  type HeatmapStockRect,
  type HeatmapViewport,
} from "./heatmapTreemap";

export type HeatmapCanvasProps = {
  nodes: HeatmapBoardNode[];
  selectedStock: HeatmapStockNode | null;
  onHoverStock: (stock: HeatmapStockNode | null) => void;
  onSelectStock: (stock: HeatmapStockNode | null) => void;
  onOpenStock?: (stock: HeatmapStockNode) => void;
  resetKey: number;
};

type CanvasSize = { width: number; height: number };

const KEYBOARD_PAN_STEP = 44;
const KEYBOARD_ZOOM_FACTOR = 1.12;

export function HeatmapCanvas({
  nodes,
  selectedStock,
  onHoverStock,
  onSelectStock,
  onOpenStock,
  resetKey,
}: HeatmapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<HeatmapDragState | null>(null);
  const viewportRef = useRef<HeatmapViewport>({ scale: 1, offsetX: 0, offsetY: 0 });
  const [viewport, setViewport] = useState<HeatmapViewport>({ scale: 1, offsetX: 0, offsetY: 0 });
  const [canvasSize, setCanvasSize] = useState<CanvasSize>({ width: 0, height: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const layout = useMemo(() => layoutHeatmapTreemap(nodes, canvasSize), [canvasSize, nodes]);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const nextViewport = { scale: 1, offsetX: 0, offsetY: 0 };
    viewportRef.current = nextViewport;
    setViewport(nextViewport);
  }, [resetKey]);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) {
      return;
    }

    const updateSize = (width: number, height: number) => {
      setCanvasSize((current) => {
        const next = {
          width: Math.max(0, Math.floor(width)),
          height: Math.max(0, Math.floor(height)),
        };
        return current.width === next.width && current.height === next.height ? current : next;
      });
    };

    const rect = wrapper.getBoundingClientRect();
    updateSize(rect.width, rect.height);

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        updateSize(entry.contentRect.width, entry.contentRect.height);
      }
    });
    resizeObserver.observe(wrapper);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const displayWidth = Math.max(0, canvasSize.width);
    const displayHeight = Math.max(0, canvasSize.height);
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const backingWidth = Math.max(1, Math.floor(displayWidth * dpr));
    const backingHeight = Math.max(1, Math.floor(displayHeight * dpr));

    if (canvas.width !== backingWidth) {
      canvas.width = backingWidth;
    }
    if (canvas.height !== backingHeight) {
      canvas.height = backingHeight;
    }

    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, displayWidth, displayHeight);
    const background = context.createLinearGradient(0, 0, displayWidth, displayHeight);
    background.addColorStop(0, "#171b22");
    background.addColorStop(1, "#10141b");
    context.fillStyle = background;
    context.fillRect(0, 0, displayWidth, displayHeight);

    if (displayWidth <= 0 || displayHeight <= 0) {
      return;
    }

    context.save();
    context.translate(viewport.offsetX, viewport.offsetY);
    context.scale(viewport.scale, viewport.scale);

    for (const board of layout.boards) {
      if (board.width <= 0 || board.height <= 0) {
        continue;
      }
      context.fillStyle = "#20252d";
      context.fillRect(board.x, board.y, board.width, board.height);
      context.strokeStyle = "rgba(148, 163, 184, 0.48)";
      context.lineWidth = 1 / viewport.scale;
      context.strokeRect(board.x, board.y, board.width, board.height);

      if (board.titleHeight > 0) {
        context.fillStyle = board.changePct ? heatmapChangeColor(board.changePct).fill : "rgb(51, 58, 70)";
        context.fillRect(board.x, board.y, board.width, board.titleHeight);
        context.fillStyle = "rgba(248, 250, 252, 0.96)";
        context.font = heatmapFont(700, Math.max(10 / viewport.scale, 13 / viewport.scale));
        context.textBaseline = "top";
        context.textAlign = "left";
        context.fillText(board.board.name, board.x + 8 / viewport.scale, board.y + 5 / viewport.scale, Math.max(0, board.width - 16 / viewport.scale));
      }
    }

    for (const subBoard of layout.subBoards) {
      if (subBoard.width <= 0 || subBoard.height <= 0) {
        continue;
      }

      context.fillStyle = "rgba(18, 23, 31, 0.62)";
      context.fillRect(subBoard.x, subBoard.y, subBoard.width, subBoard.height);
      context.strokeStyle = "rgba(148, 163, 184, 0.3)";
      context.lineWidth = 1 / viewport.scale;
      context.strokeRect(subBoard.x, subBoard.y, subBoard.width, subBoard.height);

      if (subBoard.titleHeight > 0) {
        context.fillStyle = "rgba(203, 213, 225, 0.92)";
        context.textAlign = "left";
        context.textBaseline = "top";
        context.font = heatmapFont(650, 10 / viewport.scale);
        context.fillText(
          subBoard.name,
          subBoard.x + 5 / viewport.scale,
          subBoard.y + 3 / viewport.scale,
          Math.max(0, subBoard.width - 10 / viewport.scale),
        );
      }
    }

    for (const item of layout.stocks) {
      if (item.width <= 0 || item.height <= 0) {
        continue;
      }

      const color = heatmapChangeColor(item.stock.change_pct);
      context.fillStyle = color.fill;
      context.fillRect(item.x, item.y, item.width, item.height);
      context.strokeStyle = "rgba(15, 23, 42, 0.78)";
      context.lineWidth = 1 / viewport.scale;
      context.strokeRect(item.x, item.y, item.width, item.height);

      drawStockLabel(context, item, viewport.scale);

      if (selectedStock?.symbol === item.stock.symbol) {
        context.strokeStyle = "rgba(2, 6, 23, 0.92)";
        context.lineWidth = 2 / viewport.scale;
        context.strokeRect(item.x + 1, item.y + 1, Math.max(0, item.width - 2), Math.max(0, item.height - 2));
        context.strokeStyle = "#f8fafc";
        context.lineWidth = 1 / viewport.scale;
        context.strokeRect(item.x + 3, item.y + 3, Math.max(0, item.width - 6), Math.max(0, item.height - 6));
      }
    }

    context.restore();
  }, [canvasSize, layout, selectedStock, viewport]);

  const pointerToWorld = (event: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return { x: 0, y: 0 };
    }
    const rect = canvas.getBoundingClientRect();
    return transformHeatmapPoint(
      {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      },
      viewportRef.current,
    );
  };

  const hitTestPointer = (event: { clientX: number; clientY: number }) => {
    const hit = hitTestHeatmap(layout.stocks, pointerToWorld(event));
    return hit?.stock ?? null;
  };

  const updateViewport = (nextViewport: HeatmapViewport) => {
    viewportRef.current = nextViewport;
    setViewport(nextViewport);
  };

  const cursor = isDragging ? "grabbing" : "grab";

  return (
    <div ref={wrapperRef} className="relative h-full w-full touch-none">
      <canvas
        ref={canvasRef}
        aria-label="A 股市场热力图。方向键平移，+ 和 - 缩放，0 重置视图，Enter 选中视口中心股票。"
        className="block h-full w-full"
        role="application"
        style={{ cursor }}
        tabIndex={0}
        onPointerDown={(event) => {
          dragRef.current = createHeatmapDragState(event.pointerId, event.clientX, event.clientY);
          setIsDragging(true);
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          if (drag && drag.pointerId === event.pointerId) {
            const moved = moveHeatmapDragState(drag, event.clientX, event.clientY);
            dragRef.current = moved.drag;
            updateViewport(
              clampHeatmapViewport(
                {
                  ...viewportRef.current,
                  offsetX: viewportRef.current.offsetX + moved.deltaX,
                  offsetY: viewportRef.current.offsetY + moved.deltaY,
                },
                canvasSize,
              ),
            );
            return;
          }

          onHoverStock(hitTestPointer(event));
        }}
        onPointerUp={(event) => {
          const drag = dragRef.current;
          if (drag?.pointerId !== event.pointerId) {
            return;
          }
          if (!drag.moved) {
            onSelectStock(hitTestPointer(event));
          }
          dragRef.current = null;
          setIsDragging(false);
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
          }
        }}
        onPointerCancel={(event) => {
          if (dragRef.current?.pointerId === event.pointerId) {
            dragRef.current = null;
            setIsDragging(false);
            onHoverStock(null);
          }
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
          }
        }}
        onLostPointerCapture={(event) => {
          if (dragRef.current?.pointerId === event.pointerId) {
            dragRef.current = null;
            setIsDragging(false);
          }
        }}
        onPointerLeave={() => {
          if (!dragRef.current) {
            onHoverStock(null);
          }
        }}
        onWheel={(event) => {
          event.preventDefault();
          const canvas = canvasRef.current;
          if (!canvas) {
            return;
          }

          const rect = canvas.getBoundingClientRect();
          const screenPoint = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
          };
          const currentViewport = viewportRef.current;
          const worldPoint = transformHeatmapPoint(screenPoint, currentViewport);
          const zoomFactor = heatmapWheelZoomFactor(event.deltaY, event.deltaMode);
          updateViewport(zoomHeatmapViewport(currentViewport, screenPoint, worldPoint, zoomFactor, canvasSize));
        }}
        onDoubleClick={(event) => {
          const hit = hitTestPointer(event);
          if (hit) {
            onOpenStock?.(hit);
          }
        }}
        onKeyDown={(event) => {
          const handled = handleCanvasKeyDown(
            event,
            canvasSize,
            layout.stocks,
            viewportRef.current,
            updateViewport,
            onSelectStock,
          );
          if (handled) {
            event.preventDefault();
          }
        }}
      />
    </div>
  );
}

function handleCanvasKeyDown(
  event: React.KeyboardEvent<HTMLCanvasElement>,
  canvasSize: CanvasSize,
  stocks: HeatmapStockRect[],
  viewport: HeatmapViewport,
  updateViewport: (nextViewport: HeatmapViewport) => void,
  onSelectStock: (stock: HeatmapStockNode | null) => void,
): boolean {
  const isArrowKey =
    event.key === "ArrowLeft" ||
    event.key === "ArrowRight" ||
    event.key === "ArrowUp" ||
    event.key === "ArrowDown";

  if (isArrowKey) {
    const offsetX =
      event.key === "ArrowLeft" ? KEYBOARD_PAN_STEP : event.key === "ArrowRight" ? -KEYBOARD_PAN_STEP : 0;
    const offsetY =
      event.key === "ArrowUp" ? KEYBOARD_PAN_STEP : event.key === "ArrowDown" ? -KEYBOARD_PAN_STEP : 0;
    updateViewport(
      clampHeatmapViewport(
        { ...viewport, offsetX: viewport.offsetX + offsetX, offsetY: viewport.offsetY + offsetY },
        canvasSize,
      ),
    );
    return true;
  }

  if (event.key === "+" || event.key === "=" || event.key === "-") {
    const screenPoint = { x: canvasSize.width / 2, y: canvasSize.height / 2 };
    const worldPoint = transformHeatmapPoint(screenPoint, viewport);
    const zoomFactor = event.key === "-" ? 1 / KEYBOARD_ZOOM_FACTOR : KEYBOARD_ZOOM_FACTOR;
    updateViewport(zoomHeatmapViewport(viewport, screenPoint, worldPoint, zoomFactor, canvasSize));
    return true;
  }

  if (event.key === "0" || event.key === "Home") {
    updateViewport({ scale: 1, offsetX: 0, offsetY: 0 });
    return true;
  }

  if (event.key === "Enter" || event.key === " ") {
    const centerPoint = transformHeatmapPoint({ x: canvasSize.width / 2, y: canvasSize.height / 2 }, viewport);
    onSelectStock(hitTestHeatmap(stocks, centerPoint)?.stock ?? null);
    return true;
  }

  if (event.key === "Escape") {
    onSelectStock(null);
    return true;
  }

  return false;
}

function drawStockLabel(
  context: CanvasRenderingContext2D,
  item: HeatmapStockRect,
  scale: number,
) {
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1;
  const displayWidth = item.width * safeScale;
  const displayHeight = item.height * safeScale;
  const screenUnit = 1 / safeScale;
  const clipPaddingPx = displayWidth > 110 ? 5 : displayWidth > 54 ? 3 : 2;
  const textInsetXPx = displayWidth > 110 ? 6 : displayWidth > 54 ? 4 : 3;
  const textInsetYPx = displayHeight > 56 ? 4.5 : displayHeight > 26 ? 3 : 2;
  const clipPadding = clipPaddingPx * screenUnit;
  const textInsetX = textInsetXPx * screenUnit;
  const textInsetY = textInsetYPx * screenUnit;
  const clipWidth = Math.max(0, item.width - clipPadding * 2);
  const clipHeight = Math.max(0, item.height - clipPadding * 2);

  if (displayWidth < 16 || displayHeight < 8 || clipWidth <= 2 || clipHeight <= 2) {
    return;
  }

  const hasLargeLabel = displayWidth >= 108 && displayHeight >= 58;
  const hasStackedLabel = displayWidth >= 28 && displayHeight >= 20;
  const hasInlineLabel = displayWidth >= 24 && displayHeight >= 10;

  context.save();
  try {
    context.fillStyle = "rgba(247, 250, 252, 0.96)";
    context.shadowColor = "rgba(0, 0, 0, 0.42)";
    context.shadowBlur = (displayHeight < 14 ? 0.45 : 1.2) * screenUnit;
    context.shadowOffsetY = 0.6 * screenUnit;

    if (hasLargeLabel) {
      const preferredTitleSize =
        clamp(Math.floor(Math.min(displayWidth, displayHeight) * 0.26), 15, 30) * screenUnit;
      const titleSize = fitFontSizeToWidth(
        context,
        item.stock.name,
        700,
        preferredTitleSize,
        Math.max(12 * screenUnit, preferredTitleSize * 0.66),
        clipWidth,
      );
      const detailSize = Math.min(
        clamp(Math.floor(Math.min(displayWidth, displayHeight) * 0.19), 11, 23) * screenUnit,
        titleSize * 1.08,
      );
      const centerX = item.x + item.width / 2;
      const centerY = item.y + item.height / 2;

      context.textAlign = "center";
      context.textBaseline = "middle";
      context.font = heatmapFont(700, titleSize);
      drawClippedText(
        context,
        fitTextToWidth(context, item.stock.name, clipWidth),
        centerX,
        centerY - titleSize * 0.62,
        item.x + clipPadding,
        item.y + clipPadding,
        clipWidth,
        clipHeight,
      );

      context.font = heatmapFont(650, detailSize);
      drawClippedText(
        context,
        formatChangePct(item.stock.change_pct),
        centerX,
        centerY + detailSize * 0.3,
        item.x + clipPadding,
        item.y + clipPadding,
        clipWidth,
        clipHeight,
      );

      if (displayWidth > 180 && displayHeight > 100) {
        context.font = heatmapFont(550, Math.max(11 * screenUnit, detailSize - 1 * screenUnit));
        drawClippedText(
          context,
          formatPrice(item.stock.price),
          centerX,
          centerY + detailSize * 1.35,
          item.x + clipPadding,
          item.y + clipPadding,
          clipWidth,
          clipHeight,
        );
      }
      return;
    }

    if (hasStackedLabel) {
      const preferredTitleSize =
        clamp(Math.floor(Math.min(displayWidth * 0.19, displayHeight * 0.43)), 7.5, 16) * screenUnit;
      const titleSize = fitFontSizeToWidth(
        context,
        item.stock.name,
        700,
        preferredTitleSize,
        Math.max(6.5 * screenUnit, preferredTitleSize * 0.72),
        clipWidth - (textInsetX - clipPadding),
      );
      const detailSize = Math.min(clamp(Math.floor(displayHeight * 0.33), 7, 13) * screenUnit, titleSize * 1.08);

      context.textAlign = "left";
      context.textBaseline = "alphabetic";
      context.font = heatmapFont(700, titleSize);
      drawClippedText(
        context,
        fitTextToWidth(context, item.stock.name, clipWidth - (textInsetX - clipPadding)),
        item.x + textInsetX,
        item.y + textInsetY + titleSize,
        item.x + clipPadding,
        item.y + clipPadding,
        clipWidth,
        clipHeight,
      );

      context.font = heatmapFont(650, detailSize);
      drawClippedText(
        context,
        displayWidth >= 58 ? formatChangePct(item.stock.change_pct) : formatCompactChangePct(item.stock.change_pct),
        item.x + textInsetX,
        item.y + textInsetY + titleSize + detailSize + 1.5 * screenUnit,
        item.x + clipPadding,
        item.y + clipPadding,
        clipWidth,
        clipHeight,
      );
      return;
    }

    if (hasInlineLabel) {
      const fontSize = clamp(Math.floor(Math.min(displayWidth * 0.18, displayHeight * 0.68)), 6.5, 11) * screenUnit;
      const changeText = formatCompactChangePct(item.stock.change_pct);
      const gap = 3 * screenUnit;

      context.textAlign = "left";
      context.textBaseline = "middle";
      context.font = heatmapFont(650, fontSize);

      const changeWidth = context.measureText(changeText).width;
      const canShowChange = displayWidth >= 32 && changeWidth + gap < clipWidth * 0.72;
      const nameMaxWidth = canShowChange ? Math.max(0, clipWidth - changeWidth - gap) : clipWidth;
      const fittedName = fitTextToWidth(context, item.stock.name, nameMaxWidth);
      const labelY = item.y + item.height / 2 + fontSize * 0.06;

      if (fittedName) {
        drawClippedText(
          context,
          fittedName,
          item.x + textInsetX,
          labelY,
          item.x + clipPadding,
          item.y + clipPadding,
          clipWidth,
          clipHeight,
        );
      }

      if (canShowChange) {
        context.textAlign = "right";
        drawClippedText(
          context,
          changeText,
          item.x + item.width - textInsetX,
          labelY,
          item.x + clipPadding,
          item.y + clipPadding,
          clipWidth,
          clipHeight,
        );
      }
    }
  } finally {
    context.restore();
  }
}

function formatChangePct(value: number): string {
  if (!Number.isFinite(value)) {
    return "0.00";
  }
  return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
}

function formatCompactChangePct(value: number): string {
  if (!Number.isFinite(value)) {
    return "0%";
  }
  const absValue = Math.abs(value);
  const digits = absValue >= 10 ? 1 : 2;
  const text = value.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
  return value > 0 ? `+${text}%` : `${text}%`;
}

function formatPrice(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(value >= 100 ? 1 : 2);
}

const heatmapFontStack = `"Avenir Next Condensed", "DIN Condensed", "PingFang SC", "Microsoft YaHei", Arial, sans-serif`;

function heatmapFont(weight: number, size: number): string {
  return `${weight} ${size}px ${heatmapFontStack}`;
}

function drawClippedText(
  context: CanvasRenderingContext2D,
  text: string,
  textX: number,
  textY: number,
  clipX: number,
  clipY: number,
  clipWidth: number,
  clipHeight: number,
) {
  context.save();
  context.beginPath();
  context.rect(clipX, clipY, clipWidth, clipHeight);
  context.clip();
  context.fillText(text, textX, textY);
  context.restore();
}

function fitTextToWidth(context: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (maxWidth <= 0 || text.length === 0) {
    return "";
  }
  if (context.measureText(text).width <= maxWidth) {
    return text;
  }

  let low = 1;
  let high = text.length;
  let best = "";
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const candidate = text.slice(0, mid);
    if (context.measureText(candidate).width <= maxWidth) {
      best = candidate;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return best;
}

function fitFontSizeToWidth(
  context: CanvasRenderingContext2D,
  text: string,
  weight: number,
  preferredSize: number,
  minSize: number,
  maxWidth: number,
): number {
  if (maxWidth <= 0 || text.length === 0) {
    return preferredSize;
  }
  context.font = heatmapFont(weight, preferredSize);
  const preferredWidth = context.measureText(text).width;
  if (preferredWidth <= maxWidth) {
    return preferredSize;
  }
  return clamp((preferredSize * maxWidth) / preferredWidth, minSize, preferredSize);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
