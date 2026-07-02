from __future__ import annotations

from datetime import datetime, time, timedelta
from threading import Event, RLock, Thread
from typing import Callable, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.models import (
    MarketEmotionSample,
    MarketEmotionSnapshotResponse,
    ShortTermAlertSeverity,
    ShortTermSentimentResponse,
)

SentimentMonitorInterval = Literal[1, 2, 3]


class SentimentMonitorConfig(BaseModel):
    enabled: bool = False
    interval_minutes: SentimentMonitorInterval = 3
    cooldown_minutes: int = Field(default=15, ge=1, le=120)
    limit: int = Field(default=80, ge=1, le=100)
    emotion_score_change_threshold: float = Field(default=12, ge=1, le=100)
    emotion_score_15m_threshold: float = Field(default=18, ge=1, le=100)
    break_board_jump_threshold: int = Field(default=8, ge=1, le=200)
    limit_down_jump_threshold: int = Field(default=5, ge=1, le=200)
    seal_rate_drop_threshold: float = Field(default=15, ge=1, le=100)
    limit_up_jump_threshold: int = Field(default=10, ge=1, le=200)
    losing_effect_jump_threshold: float = Field(default=15, ge=1, le=100)


class SentimentMutationAlert(BaseModel):
    type: str
    severity: ShortTermAlertSeverity
    title: str
    message: str
    previous_value: float | int | None = None
    current_value: float | int | None = None
    threshold: float | int
    generated_at: str


class SentimentMonitorStatus(BaseModel):
    enabled: bool
    running: bool = False
    in_trading_session: bool = False
    config: SentimentMonitorConfig = Field(default_factory=SentimentMonitorConfig)
    last_sampled_at: str | None = None
    last_trade_date: str | None = None
    last_emotion_score: float | None = None
    last_notification_at: str | None = None
    last_error: str | None = None
    last_alerts: list[SentimentMutationAlert] = Field(default_factory=list)


SnapshotBuilder = Callable[[str, int], tuple[ShortTermSentimentResponse, MarketEmotionSnapshotResponse]]
ConfigLoader = Callable[[], SentimentMonitorConfig]
Notifier = Callable[[str, str], object]
NowFactory = Callable[[], datetime]


def is_trading_session(now: datetime | None = None) -> bool:
    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    local = current.astimezone(ZoneInfo("Asia/Shanghai"))
    current_time = local.time()
    return (
        time(9, 25) <= current_time <= time(11, 30)
        or time(13, 0) <= current_time <= time(15, 5)
    )


def sentiment_timeline_label(hhmm: str) -> str:
    if hhmm <= "09:25":
        return "竞价定调"
    if hhmm <= "09:35":
        return "开盘承接"
    if hhmm <= "10:00":
        return "情绪确认"
    if hhmm <= "11:30":
        return "上午定性"
    if hhmm <= "14:30":
        return "尾盘风险"
    return "收盘复盘"


def detect_sentiment_mutations(
    samples: list[MarketEmotionSample],
    config: SentimentMonitorConfig,
) -> list[SentimentMutationAlert]:
    if len(samples) < 2:
        return []
    previous = samples[-2]
    current = samples[-1]
    generated_at = current.sampled_at
    alerts: list[SentimentMutationAlert] = []

    score_delta = current.emotion_score - previous.emotion_score
    if abs(score_delta) >= config.emotion_score_change_threshold:
        is_drop = score_delta < 0
        alerts.append(
            SentimentMutationAlert(
                type="emotion_score_drop" if is_drop else "emotion_score_jump",
                severity="high" if is_drop else "medium",
                title="情绪分突变",
                message=(
                    f"情绪分从 {previous.emotion_score:.0f} 变为 {current.emotion_score:.0f}，"
                    f"单次变化 {score_delta:+.0f}。"
                ),
                previous_value=previous.emotion_score,
                current_value=current.emotion_score,
                threshold=config.emotion_score_change_threshold,
                generated_at=generated_at,
            )
        )

    base_15m = _sample_at_or_before(samples[:-1], current.sampled_at, minutes=15)
    if base_15m is not None:
        score_15m_delta = current.emotion_score - base_15m.emotion_score
        if abs(score_15m_delta) >= config.emotion_score_15m_threshold:
            alerts.append(
                SentimentMutationAlert(
                    type="emotion_score_15m_drop" if score_15m_delta < 0 else "emotion_score_15m_jump",
                    severity="high" if score_15m_delta < 0 else "medium",
                    title="15分钟情绪突变",
                    message=(
                        f"15分钟情绪分从 {base_15m.emotion_score:.0f} 变为 {current.emotion_score:.0f}，"
                        f"变化 {score_15m_delta:+.0f}。"
                    ),
                    previous_value=base_15m.emotion_score,
                    current_value=current.emotion_score,
                    threshold=config.emotion_score_15m_threshold,
                    generated_at=generated_at,
                )
            )

    break_board_delta = current.break_board_count - previous.break_board_count
    if break_board_delta >= config.break_board_jump_threshold:
        alerts.append(
            SentimentMutationAlert(
                type="break_board_jump",
                severity="high",
                title="炸板快速增加",
                message=f"炸板数从 {previous.break_board_count} 增至 {current.break_board_count}，增加 {break_board_delta} 只。",
                previous_value=previous.break_board_count,
                current_value=current.break_board_count,
                threshold=config.break_board_jump_threshold,
                generated_at=generated_at,
            )
        )

    previous_limit_down = previous.limit_down_count or 0
    current_limit_down = current.limit_down_count or 0
    limit_down_delta = current_limit_down - previous_limit_down
    if limit_down_delta >= config.limit_down_jump_threshold:
        alerts.append(
            SentimentMutationAlert(
                type="limit_down_jump",
                severity="high",
                title="跌停快速增加",
                message=f"跌停数从 {previous_limit_down} 增至 {current_limit_down}，风险扩散。",
                previous_value=previous_limit_down,
                current_value=current_limit_down,
                threshold=config.limit_down_jump_threshold,
                generated_at=generated_at,
            )
        )

    if previous.seal_rate_pct is not None and current.seal_rate_pct is not None:
        seal_rate_delta = current.seal_rate_pct - previous.seal_rate_pct
        if seal_rate_delta <= -config.seal_rate_drop_threshold:
            alerts.append(
                SentimentMutationAlert(
                    type="seal_rate_drop",
                    severity="high",
                    title="封板率快速下滑",
                    message=(
                        f"封板率从 {previous.seal_rate_pct:.0f}% 降至 {current.seal_rate_pct:.0f}% ，"
                        f"下降 {abs(seal_rate_delta):.0f} 个百分点。"
                    ),
                    previous_value=previous.seal_rate_pct,
                    current_value=current.seal_rate_pct,
                    threshold=config.seal_rate_drop_threshold,
                    generated_at=generated_at,
                )
            )

    limit_up_delta = current.limit_up_count - previous.limit_up_count
    if limit_up_delta >= config.limit_up_jump_threshold:
        alerts.append(
            SentimentMutationAlert(
                type="limit_up_jump",
                severity="medium",
                title="涨停快速增加",
                message=f"涨停数从 {previous.limit_up_count} 增至 {current.limit_up_count}，情绪回暖。",
                previous_value=previous.limit_up_count,
                current_value=current.limit_up_count,
                threshold=config.limit_up_jump_threshold,
                generated_at=generated_at,
            )
        )

    previous_losing = previous.losing_effect_score or 0
    current_losing = current.losing_effect_score or 0
    losing_delta = current_losing - previous_losing
    if losing_delta >= config.losing_effect_jump_threshold:
        alerts.append(
            SentimentMutationAlert(
                type="losing_effect_jump",
                severity="high",
                title="亏钱效应扩散",
                message=f"亏钱效应从 {previous_losing:.0f} 升至 {current_losing:.0f}，短线风险升温。",
                previous_value=previous_losing,
                current_value=current_losing,
                threshold=config.losing_effect_jump_threshold,
                generated_at=generated_at,
            )
        )

    permission_hint = _trade_permission_hint(current)
    return [
        alert.model_copy(update={"message": f"{alert.message} {permission_hint}"})
        for alert in alerts
    ]


def _trade_permission_hint(current: MarketEmotionSample) -> str:
    if current.emotion_score < 25 or (current.limit_down_count or 0) >= 20:
        return "交易许可：空仓等待。"
    if current.break_board_count >= 15 or (current.seal_rate_pct or 100) < 60:
        return "交易许可：只低吸，不追高。"
    if current.emotion_score >= 78:
        return "交易许可：只卖不追。"
    if current.emotion_score >= 60:
        return "交易许可：轻仓进攻。"
    return "交易许可：轻仓试错。"


class SentimentMonitor:
    def __init__(
        self,
        snapshot_builder: SnapshotBuilder,
        config_loader: ConfigLoader | None = None,
        notifier: Notifier | None = None,
        now_fn: NowFactory | None = None,
    ) -> None:
        self._snapshot_builder = snapshot_builder
        self._config_loader = config_loader or SentimentMonitorConfig
        self._notifier = notifier or (lambda _title, _message: None)
        self._now = now_fn or _now
        self._stop_event = Event()
        self._lock = RLock()
        self._thread: Thread | None = None
        self._samples_by_trade_date: dict[str, list[MarketEmotionSample]] = {}
        self._last_notification_by_type: dict[str, datetime] = {}
        self._last_sampled_at: str | None = None
        self._last_trade_date: str | None = None
        self._last_emotion_score: float | None = None
        self._last_notification_at: str | None = None
        self._last_error: str | None = None
        self._last_alerts: list[SentimentMutationAlert] = []

    def start(self) -> SentimentMonitorStatus:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop_event.clear()
                self._thread = Thread(target=self._loop, name="sentiment-monitor", daemon=True)
                self._thread.start()
        return self.status()

    def stop(self) -> SentimentMonitorStatus:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        return self.status()

    def run_once(self, trade_date: str | None = None) -> SentimentMonitorStatus:
        config = self._config_loader()
        current_trade_date = trade_date or self._now().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
        try:
            _sentiment, market_emotion = self._snapshot_builder(current_trade_date, config.limit)
            samples = self._merge_samples(current_trade_date, market_emotion)
            alerts = detect_sentiment_mutations(samples, config)
            alerts_to_notify = self._alerts_after_cooldown(alerts, config)
            if alerts_to_notify:
                self._notifier(
                    f"短线情绪突变提醒 · {current_trade_date}",
                    _format_alert_message(alerts_to_notify, market_emotion),
                )
                now = self._now()
                with self._lock:
                    for alert in alerts_to_notify:
                        self._last_notification_by_type[alert.type] = now
                    self._last_notification_at = now.isoformat(timespec="seconds")
            with self._lock:
                self._last_sampled_at = market_emotion.generated_at
                self._last_trade_date = current_trade_date
                self._last_emotion_score = market_emotion.metrics.emotion_score
                self._last_alerts = alerts
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
        return self.status()

    def status(self) -> SentimentMonitorStatus:
        config = self._config_loader()
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            return SentimentMonitorStatus(
                enabled=config.enabled,
                running=running,
                in_trading_session=is_trading_session(self._now()),
                config=config,
                last_sampled_at=self._last_sampled_at,
                last_trade_date=self._last_trade_date,
                last_emotion_score=self._last_emotion_score,
                last_notification_at=self._last_notification_at,
                last_error=self._last_error,
                last_alerts=list(self._last_alerts),
            )

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            config = self._config_loader()
            if config.enabled and is_trading_session(self._now()):
                self.run_once()
                wait_seconds = config.interval_minutes * 60
            else:
                wait_seconds = min(config.interval_minutes * 60, 30)
            self._stop_event.wait(wait_seconds)

    def _merge_samples(
        self,
        trade_date: str,
        market_emotion: MarketEmotionSnapshotResponse,
    ) -> list[MarketEmotionSample]:
        incoming = list(market_emotion.samples) or [_sample_from_snapshot(market_emotion)]
        with self._lock:
            existing = self._samples_by_trade_date.get(trade_date, [])
            if len(incoming) > len(existing):
                samples = incoming
            else:
                samples = [*existing, _sample_from_snapshot(market_emotion)]
            self._samples_by_trade_date[trade_date] = samples[-240:]
            return list(self._samples_by_trade_date[trade_date])

    def _alerts_after_cooldown(
        self,
        alerts: list[SentimentMutationAlert],
        config: SentimentMonitorConfig,
    ) -> list[SentimentMutationAlert]:
        now = self._now()
        cooldown = timedelta(minutes=config.cooldown_minutes)
        with self._lock:
            return [
                alert
                for alert in alerts
                if alert.type not in self._last_notification_by_type
                or now - self._last_notification_by_type[alert.type] >= cooldown
            ]


def _format_alert_message(
    alerts: list[SentimentMutationAlert],
    market_emotion: MarketEmotionSnapshotResponse,
) -> str:
    metrics = market_emotion.metrics
    lines = [
        f"情绪分：{metrics.emotion_score:.0f} · {metrics.emotion_level}",
        f"涨停：{metrics.limit_up_count} 只，炸板：{metrics.break_board_count} 只，跌停：{metrics.limit_down_count or 0} 只",
    ]
    if metrics.seal_rate_pct is not None:
        lines.append(f"封板率：{metrics.seal_rate_pct:.0f}%")
    lines.append("")
    lines.extend(f"- {alert.title}：{alert.message}" for alert in alerts)
    lines.append("")
    lines.append("仅供复盘与盯盘提醒，不构成投资建议。")
    return "\n".join(lines)


def _sample_from_snapshot(snapshot: MarketEmotionSnapshotResponse) -> MarketEmotionSample:
    metrics = snapshot.metrics
    return MarketEmotionSample(
        trade_date=snapshot.trade_date,
        sampled_at=snapshot.generated_at,
        emotion_score=metrics.emotion_score,
        emotion_level=metrics.emotion_level,
        limit_up_count=metrics.limit_up_count,
        break_board_count=metrics.break_board_count,
        limit_down_count=metrics.limit_down_count,
        losing_effect_score=metrics.losing_effect_score,
        max_consecutive_boards=metrics.max_consecutive_boards,
        advance_count=metrics.advance_count,
        decline_count=metrics.decline_count,
        seal_rate_pct=metrics.seal_rate_pct,
        turnover_cny=metrics.turnover_cny,
        turnover_change_pct=metrics.turnover_change_pct,
    )


def _sample_at_or_before(
    samples: list[MarketEmotionSample],
    current_sampled_at: str,
    minutes: int,
) -> MarketEmotionSample | None:
    current_time = _parse_datetime(current_sampled_at)
    if current_time is None:
        return samples[0] if samples else None
    target = current_time - timedelta(minutes=minutes)
    parsed: list[tuple[datetime, MarketEmotionSample]] = []
    for sample in samples:
        sample_time = _parse_datetime(sample.sampled_at)
        if sample_time is not None:
            parsed.append((sample_time, sample))
    eligible = [item for item in parsed if item[0] <= target]
    if eligible:
        return max(eligible, key=lambda item: item[0])[1]
    return samples[0] if samples else None


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai"))
