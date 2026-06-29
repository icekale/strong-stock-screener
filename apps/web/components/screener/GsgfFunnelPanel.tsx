"use client";

import { Button, Tag } from "antd";
import Link from "next/link";
import { useMemo } from "react";
import type { StrongStockScreeningItem, StrongStockScreeningResponse, WatchlistPoolItem } from "../../lib/types";
import { industryStrengthCopy } from "./types";
import { gsgfLabel } from "./screenerUtils";

export function GsgfFunnelPanel({
  onAddToWatchlist,
  result,
  running,
  watchlistPoolItems,
}: {
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  result: StrongStockScreeningResponse | null;
  running: boolean;
  watchlistPoolItems: WatchlistPoolItem[];
}) {
  const funnel = result?.gsgf_funnel ?? null;
  const observationItems = result?.gsgf_observation_items ?? [];
  const watchlistSymbols = useMemo(
    () => new Set(watchlistPoolItems.map((item) => item.symbol)),
    [watchlistPoolItems],
  );
  const scanCoverage =
    funnel && funnel.candidate_pool_count > 0
      ? (funnel.scan_limit_count / funnel.candidate_pool_count) * 100
      : null;
  const funnelRows = funnel
    ? [
        ["候选池", funnel.candidate_pool_count],
        ["静态过滤后", funnel.after_static_filters_count],
        ["进入扫描", funnel.scan_limit_count],
        ["K线成功", funnel.kline_success_count],
        ["数据不足", funnel.data_incomplete_count],
        ["KDJ过滤", funnel.kdj_filtered_count],
        ["结构命中", funnel.gsgf_structure_hit_count],
        ["确认买点", funnel.confirmed_buy_count],
        ["低吸观察", funnel.low_buy_count],
        ["B区A点", funnel.b_zone_a_point_count],
        ["放量突破", funnel.volume_breakout_count],
        ["硬风险过滤", funnel.hard_risk_filtered_count],
        ["最终展示", funnel.final_displayed_count],
      ]
    : [];

  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-4 py-3">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-black text-[#11100e]">漏斗诊断</h2>
          <p className="mt-1 text-xs font-medium text-[#7b756d]">
            早期观察池不进入最终买点列表，用来跟踪 B区A点等未确认结构
          </p>
        </div>
        <Tag className="m-0" color={funnel ? "green" : running ? "processing" : "default"}>
          {funnel
            ? `扫描覆盖 ${funnel.scan_limit_count}/${funnel.candidate_pool_count} · ${scanCoverage?.toFixed(1) ?? "0.0"}%`
            : running ? "筛选中" : "待运行"}
        </Tag>
      </div>

      {funnel ? (
        <div className="mt-3 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(420px,1.2fr)]">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
            {funnelRows.map(([label, value]) => (
              <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2" key={label}>
                <div className="text-[11px] font-black text-[#7b756d]">{label}</div>
                <div className="mt-1 text-xl font-black tabular-nums text-[#11100e]">{value}</div>
              </div>
            ))}
          </div>

          <div className="min-w-0 rounded-lg border border-[#ddd8d0] bg-[#f5f3f0]">
            <div className="flex items-center justify-between gap-2 border-b border-[#ddd8d0] px-3 py-2">
              <h3 className="text-sm font-black text-[#11100e]">早期观察池</h3>
              <Tag className="m-0">{observationItems.length}</Tag>
            </div>
            {observationItems.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-[#ddd8d0] text-left text-xs">
                  <thead className="bg-[#f5f3f0] text-[#7b756d]">
                    <tr>
                      <th className="px-3 py-2 font-black">股票</th>
                      <th className="px-3 py-2 font-black">结构</th>
                      <th className="px-3 py-2 font-black">分数</th>
                      <th className="px-3 py-2 font-black">板块</th>
                      <th className="px-3 py-2 text-right font-black">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e0d8] bg-white">
                    {observationItems.slice(0, 8).map((item) => {
                      const alreadyAdded = watchlistSymbols.has(item.symbol);
                      return (
                        <tr key={item.symbol}>
                          <td className="px-3 py-2">
                            <Link className="font-black text-[#11100e] hover:text-[#f04438]" href={`/stock/${item.symbol}`}>
                              {item.name}
                            </Link>
                            <div className="mt-0.5 text-[11px] font-semibold text-[#7b756d]">{item.symbol}</div>
                          </td>
                          <td className="px-3 py-2 text-[#7b756d]">
                            {gsgfLabel(item.gsgf?.setup_type ?? item.gsgf?.zone)}
                            <div className="mt-0.5 text-[11px]">{item.gsgf?.final_status ?? "--"}</div>
                          </td>
                          <td className="px-3 py-2 font-black tabular-nums text-[#11100e]">
                            {item.gsgf?.total_score ?? item.score}
                          </td>
                          <td className="px-3 py-2 text-[#7b756d]">
                            {item.industry ?? "--"}
                            <div className="mt-0.5 text-[11px]">{item.industry_strength ? industryStrengthCopy[item.industry_strength].label : "--"}</div>
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Button
                              disabled={alreadyAdded}
                              onClick={() => onAddToWatchlist(item, "早期观察", ["GSGF", "B区A点"])}
                              size="small"
                            >
                              {alreadyAdded ? "已在自选" : "加入"}
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-3 py-5 text-sm font-medium text-[#7b756d]">本轮没有未确认的 B区A点观察项。</p>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-[#f5f3f0] px-3 py-2 text-sm text-[#7b756d]">
          运行筛选后会显示从候选池到最终展示的逐层数量。
        </p>
      )}
    </section>
  );
}
