from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.models import (
    ModelMaintenancePacket,
    ModelMaintenanceReport,
    ModelMaintenanceRuleDiagnostic,
    ModelMaintenanceSuggestion,
)
from app.services.model_maintenance_store import new_model_maintenance_id
from app.services.runtime_settings import EffectiveAiAnalysisSettings


def analyze_model_maintenance_packet(
    packet: ModelMaintenancePacket,
    config: EffectiveAiAnalysisSettings,
    *,
    http_client: Any | None = None,
) -> ModelMaintenanceReport:
    if not config.enabled or not config.api_key:
        return build_offline_model_maintenance_report(packet)

    client = http_client or httpx.Client(timeout=45)
    should_close = http_client is None
    try:
        response = client.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是A股选股模型维护助手。只分析模型表现和数据质量，不给交易指令。"
                            "重点检查 model_sections.gsgf、model_sections.auction_top3、"
                            "model_sections.auction_top3_training。竞价 Top3 的训练样本和模拟收益"
                            "只用于模型维护与复盘，不代表真实收益，不自动调参。"
                            "请只返回一个 JSON 对象，字段包含 health_status, summary, key_findings,"
                            " rule_diagnostics, suggestions。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(packet.model_dump(mode="json"), ensure_ascii=False),
                    },
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = extract_chat_content(payload)
        report_payload = extract_json_object(content)
        return _report_from_ai_payload(packet, config, report_payload)
    except Exception:
        return build_offline_model_maintenance_report(packet)
    finally:
        if should_close and hasattr(client, "close"):
            client.close()


def build_offline_model_maintenance_report(packet: ModelMaintenancePacket) -> ModelMaintenanceReport:
    record_count = int(packet.review_summary.get("record_count") or 0)
    data_unreliable = bool(packet.data_quality_notes)

    if data_unreliable:
        health_status = "data_unreliable"
        summary = "数据源存在异常，建议优先检查数据质量，再判断模型表现。"
        suggestion_type = "data_check"
        title = "检查模型维护数据源"
        confidence = 0.7
    elif record_count < 5:
        health_status = "insufficient_sample"
        summary = "模型维护样本不足，当前只适合观察，不建议调整参数。"
        suggestion_type = "observe"
        title = "继续积累模型维护样本"
        confidence = 0.5
    else:
        health_status = "watch"
        summary = "模型样本已可观察，建议结合规则分桶继续跟踪。"
        suggestion_type = "observe"
        title = "观察近期规则分桶表现"
        confidence = 0.6

    return ModelMaintenanceReport(
        report_id=new_model_maintenance_id("report"),
        packet_id=packet.packet_id,
        provider="openai_compatible",
        model="offline-rule-summary",
        health_status=health_status,
        summary=summary,
        key_findings=[summary, *_auction_top3_findings(packet)],
        suggestions=[
            ModelMaintenanceSuggestion(
                suggestion_id=new_model_maintenance_id("suggestion"),
                type=suggestion_type,
                title=title,
                reason=summary,
                evidence_refs=[packet.packet_id],
                confidence=confidence,
                suggested_action="先观察，不自动修改模型参数。",
            )
        ],
    )


def _auction_top3_findings(packet: ModelMaintenancePacket) -> list[str]:
    sections = packet.model_sections or {}
    auction_top3 = sections.get("auction_top3")
    training = sections.get("auction_top3_training")
    findings: list[str] = []

    if isinstance(auction_top3, dict):
        if auction_top3.get("available"):
            findings.append(
                "竞价 Top3：当前可用，入选 "
                f"{_int_value(auction_top3.get('top_count'))} 只，观察 "
                f"{_int_value(auction_top3.get('watch_count'))} 只。"
            )
        else:
            notes = auction_top3.get("notes")
            note = notes[0] if isinstance(notes, list) and notes else "暂无可用缓存。"
            findings.append(f"竞价 Top3：{note}")

    if isinstance(training, dict):
        signal_count = _int_value(training.get("signal_sample_count"))
        simulated_count = _int_value(training.get("simulated_trade_sample_count"))
        manual_count = _int_value(training.get("manual_trade_sample_count"))
        profit = training.get("simulated_profit_summary")
        return_pct = profit.get("cumulative_return_pct") if isinstance(profit, dict) else None
        suffix = f"，模拟收益 {_number_text(return_pct)}%" if isinstance(return_pct, int | float) else ""
        quality_note = _first_text(training.get("quality_notes"))
        note_suffix = f"；{quality_note}" if quality_note else ""
        findings.append(
            "竞价 Top3训练：训练样本 "
            f"{signal_count}，模拟交易 {simulated_count}，人工样本 {manual_count}{suffix}{note_suffix}。"
        )

    return findings


def extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("AI response missing choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI response missing content")
    return content


def extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI response content is not JSON")
        stripped = stripped[start : end + 1]
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("AI response JSON must be an object")
    return payload


def _report_from_ai_payload(
    packet: ModelMaintenancePacket,
    config: EffectiveAiAnalysisSettings,
    payload: dict[str, Any],
) -> ModelMaintenanceReport:
    suggestions = [
        _suggestion_from_payload(item)
        for item in _safe_list(payload.get("suggestions"))
        if isinstance(item, dict)
    ]
    if not suggestions:
        suggestions = build_offline_model_maintenance_report(packet).suggestions

    return ModelMaintenanceReport(
        report_id=new_model_maintenance_id("report"),
        packet_id=packet.packet_id,
        provider=config.provider,
        model=config.model,
        health_status=payload.get("health_status") or "watch",
        summary=str(payload.get("summary") or "AI 已完成模型维护分析。"),
        key_findings=[str(item) for item in _safe_list(payload.get("key_findings"))],
        rule_diagnostics=[
            _rule_diagnostic_from_payload(item)
            for item in _safe_list(payload.get("rule_diagnostics"))
            if isinstance(item, dict)
        ],
        suggestions=suggestions,
    )


def _rule_diagnostic_from_payload(payload: dict[str, Any]) -> ModelMaintenanceRuleDiagnostic:
    return ModelMaintenanceRuleDiagnostic(
        rule_name=str(payload.get("rule_name") or "未命名规则"),
        status=payload.get("status") or "neutral",
        evidence=[str(item) for item in _safe_list(payload.get("evidence"))],
        confidence=_bounded_confidence(payload.get("confidence")),
    )


def _suggestion_from_payload(payload: dict[str, Any]) -> ModelMaintenanceSuggestion:
    return ModelMaintenanceSuggestion(
        suggestion_id=str(payload.get("suggestion_id") or new_model_maintenance_id("suggestion")),
        type=payload.get("type") or "observe",
        title=str(payload.get("title") or "继续观察模型表现"),
        reason=str(payload.get("reason") or "AI 未提供详细原因。"),
        evidence_refs=[str(item) for item in _safe_list(payload.get("evidence_refs"))],
        risk=str(payload.get("risk") or "仅供模型维护参考，不构成投资建议。"),
        confidence=_bounded_confidence(payload.get("confidence")),
        suggested_action=str(payload.get("suggested_action") or "观察，不自动调整。"),
        status=payload.get("status") or "pending",
    )


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(value: Any) -> str:
    for item in _safe_list(value):
        text = str(item).strip()
        if text:
            return text
    return ""


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return int(value)
    return 0


def _number_text(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _bounded_confidence(value: Any) -> float:
    if isinstance(value, int | float):
        return max(0, min(1, float(value)))
    return 0
