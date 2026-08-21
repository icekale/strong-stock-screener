"""后台循环采样器基类：统一 start/stop/stop_and_wait/running 生命周期与轮询循环。

各 sampler 的历史实现各自复制了一套 Event/Thread 样板（capital/etf/sentiment
还带「停止后重启」语义）。基类收敛这份样板，子类只需实现 sample_once 与
_wait_seconds（决定采样成功后与失败/空闲时的轮询间隔）。

注意：子类模块必须保留 `from threading import Event` 并传入 event_factory=Event
（运行时求值），测试通过 monkeypatch.setattr(子类模块, "Event", ...) 注入
虚拟时钟/即时停止事件时才能生效。
"""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _default_clock() -> datetime:
    return datetime.now(_SHANGHAI)


class BackgroundLoopSampler:
    def __init__(
        self,
        *,
        thread_name: str,
        clock: Callable[[], datetime] | None = None,
        retry_seconds: float | None = None,
        idle_seconds: float | None = None,
        poll_seconds: float | None = None,
        interval_seconds: float | None = None,
        event_factory: Callable[[], Event] | None = None,
        error_logger: logging.Logger | None = None,
        error_message: str | None = None,
    ) -> None:
        self._thread_name = thread_name
        self._clock = clock or _default_clock
        self._retry_seconds = retry_seconds
        self._idle_seconds = idle_seconds
        self._poll_seconds = poll_seconds
        self._interval_seconds = interval_seconds
        self._event_factory = event_factory or Event
        self._error_logger = error_logger or logger
        self._error_message = error_message or f"{thread_name} run failed"
        self._stop_event: Event | None = None
        self._thread: Thread | None = None
        self._lifecycle_lock = Lock()

    def start(self) -> None:
        while True:
            with self._lifecycle_lock:
                thread = self._thread
                stop_event = self._stop_event
                if thread is not None and thread.is_alive():
                    if stop_event is not None and not stop_event.is_set():
                        return
                    stopped_thread = thread
                else:
                    stop_event = self._event_factory()
                    thread = Thread(
                        target=self._run,
                        args=(stop_event,),
                        name=self._thread_name,
                        daemon=True,
                    )
                    self._stop_event = stop_event
                    self._thread = thread
                    thread.start()
                    return

            stopped_thread.join()

    def stop(self, *, timeout_seconds: float = 2) -> bool:
        with self._lifecycle_lock:
            thread = self._thread
            stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        if thread is None or not thread.is_alive():
            return True
        thread.join(timeout=max(0, timeout_seconds))
        return not thread.is_alive()

    def stop_and_wait(self) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join()

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def interval_seconds(self) -> float | None:
        return self._interval_seconds

    @property
    def idle_seconds(self) -> float | None:
        return self._idle_seconds

    def _run(self, stop_event: Event | None = None) -> None:
        active_stop_event = stop_event or self._stop_event
        if active_stop_event is None:
            return
        while not active_stop_event.is_set():
            try:
                sampled = self.sample_once()
            except Exception:
                self._error_logger.exception(self._error_message)
                # 失败按重试节奏等待（无 retry 时退回 poll），比空闲等待更激进。
                active_stop_event.wait(
                    max(0.0, self._retry_seconds if self._retry_seconds is not None else (self._poll_seconds or 0.0))
                )
                continue
            active_stop_event.wait(max(0.0, self._wait_seconds(sampled)))

    def _wait_seconds(self, sampled: bool) -> float:
        """采样后的轮询间隔。默认：轮询模式固定 poll；否则采样成功用 retry/interval，
        空闲用 idle（无 idle 时退回 retry）。子类可覆写特殊等待逻辑。"""
        if self._poll_seconds is not None:
            return self._poll_seconds
        if sampled:
            return self._interval_seconds if self._interval_seconds is not None else (self._retry_seconds or 0.0)
        return self._idle_seconds if self._idle_seconds is not None else (self._retry_seconds or 0.0)
