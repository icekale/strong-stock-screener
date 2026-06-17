"use client";

import { useEffect, useMemo, useState } from "react";
import { checkRuntimeSettingsHealth, getRuntimeSettings, saveRuntimeSettings } from "../../lib/api";
import type { RuntimeSettingsConfig, RuntimeSettingsHealthProbe } from "../../lib/types";

type SettingsDraft = {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key: string;
  tickflow_base_url: string;
  ifind_api_key: string;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  provider_timeout_seconds: number;
};

const DEFAULT_DRAFT: SettingsDraft = {
  candidate_provider: "recent_limit_up",
  kline_provider: "tickflow",
  quote_provider: "tickflow",
  tickflow_api_key: "",
  tickflow_base_url: "https://api.tickflow.org",
  ifind_api_key: "",
  ifind_base_url: "https://api-mcp.51ifind.com:8643",
  ifind_service_id: "hexin-ifind-ds-stock-mcp",
  provider_timeout_seconds: 12,
};

export default function SettingsPage() {
  const [draft, setDraft] = useState<SettingsDraft>(DEFAULT_DRAFT);
  const [config, setConfig] = useState<RuntimeSettingsConfig | null>(null);
  const [probes, setProbes] = useState<RuntimeSettingsHealthProbe[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningHealth, setRunningHealth] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const response = await getRuntimeSettings();
      setConfig(response.config);
      setDraft({
        candidate_provider: response.config.candidate_provider,
        kline_provider: response.config.kline_provider,
        quote_provider: response.config.quote_provider,
        tickflow_api_key: "",
        tickflow_base_url: response.config.tickflow_base_url,
        ifind_api_key: "",
        ifind_base_url: response.config.ifind_base_url,
        ifind_service_id: response.config.ifind_service_id,
        provider_timeout_seconds: response.config.provider_timeout_seconds,
      });
      setMessage("已读取当前设置");
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取设置失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await saveRuntimeSettings({
        candidate_provider: draft.candidate_provider,
        kline_provider: draft.kline_provider,
        quote_provider: draft.quote_provider,
        tickflow_api_key: draft.tickflow_api_key.trim() || undefined,
        tickflow_base_url: draft.tickflow_base_url.trim(),
        ifind_api_key: draft.ifind_api_key.trim() || undefined,
        ifind_base_url: draft.ifind_base_url.trim(),
        ifind_service_id: draft.ifind_service_id,
        provider_timeout_seconds: draft.provider_timeout_seconds,
      });
      setConfig(response.config);
      setDraft((current) => ({
        ...current,
        tickflow_api_key: "",
        tickflow_base_url: response.config.tickflow_base_url,
        ifind_api_key: "",
        ifind_base_url: response.config.ifind_base_url,
        ifind_service_id: response.config.ifind_service_id,
        provider_timeout_seconds: response.config.provider_timeout_seconds,
      }));
      setMessage("设置已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleHealthCheck() {
    setRunningHealth(true);
    setError(null);
    setMessage(null);
    try {
      const response = await checkRuntimeSettingsHealth();
      setConfig(response.config);
      setProbes(response.probes);
      setMessage("健康检查完成");
    } catch (err) {
      setError(err instanceof Error ? err.message : "健康检查失败");
    } finally {
      setRunningHealth(false);
    }
  }

  const summary = useMemo(() => {
    if (!config) {
      return "未读取";
    }
    return `${config.candidate_provider} / ${config.kline_provider} / ${config.quote_provider}`;
  }, [config]);

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-[1280px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        <header className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">Settings</p>
              <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-950">数据源配置</h1>
              <p className="mt-1 text-sm font-medium text-slate-500">独立选股工作台的行情源、候选源和 iFinD 研究增强配置。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a className="inline-flex min-h-[36px] items-center rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100" href="/">
                返回工作台
              </a>
              <button className="min-h-[36px] rounded-md bg-white px-3 text-xs font-bold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:bg-slate-100" disabled={loading || runningHealth} onClick={() => void loadSettings()} type="button">
                重新读取
              </button>
              <button className="min-h-[36px] rounded-md bg-slate-950 px-3 text-xs font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300" disabled={saving} onClick={() => void handleSave()} type="button">
                {saving ? "保存中..." : "保存设置"}
              </button>
            </div>
          </div>
        </header>

        {error && <div className="rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</div>}
        {message && <div className="rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{message}</div>}

        <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
          <section className="space-y-4">
            <Panel title="当前状态" subtitle={summary}>
              <div className="grid gap-3 sm:grid-cols-3">
                <StatusPill label="候选源" value={config?.candidate_provider ?? "未读取"} />
                <StatusPill label="K线源" value={config?.kline_provider ?? "未读取"} />
                <StatusPill label="行情源" value={config?.quote_provider ?? "未读取"} />
                <StatusPill label="TickFlow Key" value={config?.tickflow_api_key_configured ? "已配置" : "未配置"} />
                <StatusPill label="iFinD Key" value={config?.ifind_api_key_configured ? "已配置" : "未配置"} />
                <StatusPill label="iFinD 服务" value={config?.ifind_service_id ?? "未读取"} />
                <StatusPill label="超时" value={config ? `${config.provider_timeout_seconds}s` : "未读取"} />
              </div>
            </Panel>

            <Panel title="行情与候选源" subtitle="TickFlow 继续负责 K 线、分钟线和实时行情">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="候选源">
                  <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.candidate_provider} onChange={(event) => setDraft({ ...draft, candidate_provider: event.target.value as SettingsDraft["candidate_provider"] })}>
                    <option value="recent_limit_up">recent_limit_up</option>
                    <option value="thsdk">thsdk</option>
                  </select>
                </Field>
                <Field label="K线源">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm" value="tickflow" readOnly />
                </Field>
                <Field label="行情源">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm" value="tickflow" readOnly />
                </Field>
                <Field label="TickFlow Base URL">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.tickflow_base_url} onChange={(event) => setDraft({ ...draft, tickflow_base_url: event.target.value })} />
                </Field>
                <Field label="TickFlow API Key">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" placeholder={config?.tickflow_api_key_configured ? "留空表示沿用已保存 Key" : "请输入 TickFlow API Key"} value={draft.tickflow_api_key} onChange={(event) => setDraft({ ...draft, tickflow_api_key: event.target.value })} />
                </Field>
                <Field label="请求超时（秒）">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" type="number" min={1} max={60} step={0.5} value={draft.provider_timeout_seconds} onChange={(event) => setDraft({ ...draft, provider_timeout_seconds: Number(event.target.value) || 12 })} />
                </Field>
              </div>
            </Panel>

            <Panel title="iFinD 研究增强" subtitle="用于行业板块、公告新闻、财务估值和风险事件；不替代 TickFlow 行情">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="iFinD Base URL">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.ifind_base_url} onChange={(event) => setDraft({ ...draft, ifind_base_url: event.target.value })} />
                </Field>
                <Field label="默认 MCP 服务">
                  <select className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" value={draft.ifind_service_id} onChange={(event) => setDraft({ ...draft, ifind_service_id: event.target.value as SettingsDraft["ifind_service_id"] })}>
                    <option value="hexin-ifind-ds-stock-mcp">A股数据</option>
                    <option value="hexin-ifind-ds-news-mcp">新闻公告</option>
                    <option value="hexin-ifind-ds-index-mcp">指数板块</option>
                  </select>
                </Field>
                <Field label="iFinD MCP Key">
                  <input className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" placeholder={config?.ifind_api_key_configured ? "留空表示沿用已保存 Key" : "请输入 iFinD MCP Key"} value={draft.ifind_api_key} onChange={(event) => setDraft({ ...draft, ifind_api_key: event.target.value })} />
                </Field>
                <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="text-xs font-semibold text-slate-500">Key 来源</div>
                  <div className="mt-1 text-sm font-black text-slate-950">{config?.ifind_api_key_source ?? "未读取"}</div>
                  <div className="mt-1 text-xs text-slate-500">{config?.ifind_api_key_preview || "未配置"}</div>
                </div>
              </div>
            </Panel>
          </section>

          <aside className="space-y-4">
            <Panel title="手动健康检查" subtitle="不在页面加载时自动刷接口">
              <button className="min-h-[40px] w-full rounded-lg bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300" disabled={runningHealth} onClick={() => void handleHealthCheck()} type="button">
                {runningHealth ? "检查中..." : "运行健康检查"}
              </button>
              <div className="mt-3 space-y-2">
                {probes.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无健康检查结果。</p>
                ) : (
                  probes.map((probe) => (
                    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2" key={probe.name}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-bold text-slate-950">{probe.name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-black ${probe.status === "success" ? "bg-emerald-50 text-emerald-700" : probe.status === "missing_key" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"}`}>
                          {probe.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{probe.latency_ms} ms · {probe.detail}</p>
                    </div>
                  ))
                )}
              </div>
            </Panel>
          </aside>
        </div>
      </div>
    </main>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4">
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="mt-2">{children}</div>
    </label>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-black text-slate-950">{value}</div>
    </div>
  );
}
