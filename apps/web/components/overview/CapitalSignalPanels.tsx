import { BankOutlined, RadarChartOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import Link from "next/link";
import {
  directionTone,
  formatDirectionalCny,
  formatDirectionalPercent,
  formatEvidenceStrength,
} from "../../lib/capitalSignals";
import type { PanelState } from "../../lib/marketOverview";
import type { CapitalSummaryResponse } from "../../lib/types";
import { DataState } from "../workbench/DataState";

export function CapitalSignalPanels({
  capital,
  onRefresh,
}: {
  capital: PanelState<CapitalSummaryResponse> | null;
  onRefresh: () => void;
}) {
  const data = capital && capital.kind !== "error" ? capital.value : null;

  if (!data) {
    return (
      <div className="capital-signal-stack">
        <CapitalLoadingPanel kind={capital?.kind === "error" ? "error" : "loading"} onRefresh={onRefresh} subject="两融余额" />
        <CapitalLoadingPanel kind={capital?.kind === "error" ? "error" : "loading"} onRefresh={onRefresh} subject="宽基护盘雷达" />
      </div>
    );
  }

  return (
    <div className="capital-signal-stack">
      <FinancingPanel data={data} />
      <EtfRadarPanel data={data} />
      {capital?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="资金信号" /> : null}
    </div>
  );
}

function FinancingPanel({ data }: { data: CapitalSummaryResponse }) {
  const margin = data.margin;
  const changeTone = directionTone(margin.change_cny);

  return (
    <section aria-labelledby="financing-balance-title" className="compact-panel capital-signal-panel overflow-hidden">
      <div className="compact-panel__header">
        <div className="min-w-0">
          <h2 className="capital-signal-title" id="financing-balance-title">
            <BankOutlined aria-hidden="true" />
            两融余额
          </h2>
          <p className="m-0 truncate text-xs text-[var(--app-muted)]">
            {data.trade_date} · 沪深 {margin.available_markets}/{margin.expected_markets}
          </p>
        </div>
        <Tag color={margin.available_markets === margin.expected_markets ? "blue" : "gold"}>
          {margin.available_markets === margin.expected_markets ? "完整" : "部分"}
        </Tag>
      </div>
      <div className="capital-signal-body">
        <div className="capital-signal-primary">
          <span>融资融券余额</span>
          <strong>{formatPlainCny(margin.balance_cny)}</strong>
        </div>
        <div className="capital-signal-change">
          <span>较上一交易日</span>
          <strong className={toneClass(changeTone)}>{formatDirectionalCny(margin.change_cny)}</strong>
          <small className={toneClass(directionTone(margin.change_pct))}>{formatDirectionalPercent(margin.change_pct)}</small>
        </div>
        <div className="capital-signal-metrics">
          <Metric label="融资余额" value={formatPlainCny(margin.financing_balance_cny)} />
          <Metric label="当日融资买入" value={formatPlainCny(margin.financing_buy_cny)} />
        </div>
      </div>
    </section>
  );
}

function EtfRadarPanel({ data }: { data: CapitalSummaryResponse }) {
  const radar = data.etf_radar;
  const strength = radar.evidence_strength;
  const stage = data.signal_stage === "intraday" ? "盘中代理" : "盘后确认";

  return (
    <section aria-labelledby="etf-radar-summary-title" className="compact-panel capital-signal-panel overflow-hidden">
      <div className="compact-panel__header">
        <div className="min-w-0">
          <h2 className="capital-signal-title" id="etf-radar-summary-title">
            <RadarChartOutlined aria-hidden="true" />
            宽基护盘雷达
          </h2>
          <p className="m-0 truncate text-xs text-[var(--app-muted)]">{stage} · {data.model_version}</p>
        </div>
        <Link className="shrink-0 text-xs font-medium text-[var(--app-primary)] hover:underline" href="/etf-radar">
          查看详情
        </Link>
      </div>
      <div className="capital-signal-body">
        <div className="capital-evidence-row">
          <div className="capital-signal-primary">
            <span>证据强度</span>
            <strong>{formatEvidenceStrength(strength)}</strong>
          </div>
          <Tag color={evidenceTagColor(radar.evidence_level)}>{radar.evidence_level ?? "待确认"}</Tag>
        </div>
        <div aria-label={`证据强度 ${formatEvidenceStrength(strength)}`} className="capital-evidence-meter" role="img">
          <span style={{ width: `${Math.max(0, Math.min(100, strength ?? 0))}%` }} />
        </div>
        <div className="capital-signal-change">
          <span>估算净申购</span>
          <strong className={toneClass(directionTone(radar.estimated_subscription_cny))}>
            {formatDirectionalCny(radar.estimated_subscription_cny)}
          </strong>
          <small>有效ETF {radar.valid_etf_count}/{radar.expected_etf_count}</small>
        </div>
        {radar.evidence.length > 0 ? (
          <ul className="capital-evidence-list">
            {radar.evidence.slice(0, 2).map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : (
          <p className="capital-signal-empty">等待交易所份额形成可比记录</p>
        )}
      </div>
    </section>
  );
}

function CapitalLoadingPanel({
  kind,
  onRefresh,
  subject,
}: {
  kind: "error" | "loading";
  onRefresh: () => void;
  subject: string;
}) {
  return (
    <section className="compact-panel capital-signal-panel overflow-hidden">
      <div className="compact-panel__header"><h2 className="m-0 text-sm font-semibold">{subject}</h2></div>
      <DataState action={{ onClick: onRefresh }} kind={kind} subject={subject} />
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function toneClass(tone: "fall" | "neutral" | "rise"): string {
  if (tone === "rise") return "market-rise-text";
  if (tone === "fall") return "market-fall-text";
  return "text-[var(--app-ink)]";
}

function formatPlainCny(value: number | null): string {
  if (value === null) return "--";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  if (absolute >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}亿`;
  if (absolute >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}

function evidenceTagColor(level: CapitalSummaryResponse["etf_radar"]["evidence_level"]): string {
  if (level === "较强") return "red";
  if (level === "疑似") return "orange";
  if (level === "观察") return "gold";
  return "default";
}
