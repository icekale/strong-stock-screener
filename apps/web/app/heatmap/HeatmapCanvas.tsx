"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";
import {
  createHeatmapDragState,
  heatmapStockLabelLevel,
  heatmapWheelZoomFactor,
  moveHeatmapDragState,
  type HeatmapDragState,
  type HeatmapStockLabelLevel,
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
    context.fillStyle = "#171512";
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
      context.fillStyle = "#211e19";
      context.fillRect(board.x, board.y, board.width, board.height);
      context.strokeStyle = "#34302a";
      context.lineWidth = 1 / viewport.scale;
      context.strokeRect(board.x, board.y, board.width, board.height);

      if (board.width >= 96 && board.height >= 44) {
        context.fillStyle = "#c8bda9";
        context.font = "600 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif";
        context.textBaseline = "top";
        context.fillText(board.board.name, board.x + 10, board.y + 8, Math.max(0, board.width - 20));
      }
    }

    for (const item of layout.stocks) {
      if (item.width <= 0 || item.height <= 0) {
        continue;
      }

      const color = heatmapChangeColor(item.stock.change_pct);
      context.fillStyle = color.fill;
      context.fillRect(item.x, item.y, item.width, item.height);
      context.strokeStyle = "#171512";
      context.lineWidth = 1 / viewport.scale;
      context.strokeRect(item.x, item.y, item.width, item.height);

      const labelLevel = heatmapStockLabelLevel(item, viewport.scale);
      if (labelLevel !== "none") {
        drawStockText(context, item, color.text, viewport.scale, labelLevel);
      }

      if (selectedStock?.symbol === item.stock.symbol) {
        context.strokeStyle = "#fffaf2";
        context.lineWidth = 2 / viewport.scale;
        context.strokeRect(item.x + 1, item.y + 1, Math.max(0, item.width - 2), Math.max(0, item.height - 2));
      }
    }

    context.restore();
  }, [canvasSize, layout, selectedStock, viewport]);

  const pointerToWorld = (event: React.PointerEvent<HTMLCanvasElement>) => {
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

  const hitTestPointer = (event: React.PointerEvent<HTMLCanvasElement>) => {
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
            updateViewport({
              ...viewportRef.current,
              offsetX: viewportRef.current.offsetX + moved.deltaX,
              offsetY: viewportRef.current.offsetY + moved.deltaY,
            });
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
          updateViewport(zoomHeatmapViewport(currentViewport, screenPoint, worldPoint, zoomFactor));
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
    updateViewport({ ...viewport, offsetX: viewport.offsetX + offsetX, offsetY: viewport.offsetY + offsetY });
    return true;
  }

  if (event.key === "+" || event.key === "=" || event.key === "-") {
    const screenPoint = { x: canvasSize.width / 2, y: canvasSize.height / 2 };
    const worldPoint = transformHeatmapPoint(screenPoint, viewport);
    const zoomFactor = event.key === "-" ? 1 / KEYBOARD_ZOOM_FACTOR : KEYBOARD_ZOOM_FACTOR;
    updateViewport(zoomHeatmapViewport(viewport, screenPoint, worldPoint, zoomFactor));
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

function drawStockText(
  context: CanvasRenderingContext2D,
  item: HeatmapStockRect,
  textColor: string,
  scale: number,
  labelLevel: HeatmapStockLabelLevel,
) {
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1;
  const displayedWidth = item.width * safeScale;
  const padding = (labelLevel === "name" && displayedWidth < 48 ? 4 : 6) / safeScale;
  const nameFontSize = (labelLevel === "name" && displayedWidth < 48 ? 10 : 12) / safeScale;
  const detailFontSize = 11 / safeScale;
  const lineHeight = 16 / safeScale;
  const maxWidth = Math.max(0, item.width - padding * 2);
  const x = item.x + padding;
  let y = item.y + padding;

  context.fillStyle = textColor;
  context.textBaseline = "top";
  context.font = `600 ${nameFontSize}px system-ui, -apple-system, BlinkMacSystemFont, sans-serif`;
  context.fillText(item.stock.name, x, y, maxWidth);

  if (labelLevel === "code" || labelLevel === "change") {
    y += lineHeight;
    context.font = `${detailFontSize}px system-ui, -apple-system, BlinkMacSystemFont, sans-serif`;
    context.fillText(item.stock.code, x, y, maxWidth);
  }

  if (labelLevel === "change") {
    y += lineHeight;
    context.font = `600 ${nameFontSize}px system-ui, -apple-system, BlinkMacSystemFont, sans-serif`;
    context.fillText(`${formatChangePct(item.stock.change_pct)}%`, x, y, maxWidth);
  }
}

function formatChangePct(value: number): string {
  if (!Number.isFinite(value)) {
    return "0.00";
  }
  return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
}
