"""JSON/JSONL 文件存储基类：实例级锁 + 原子写（tmp+rename）+ 损坏兜底。

多个 store（ETF 三因子/资金信号/决策复盘等）各自复制了「写前 mkdir →
写 .tmp → replace」的原子写样板与「损坏 JSON 静默返回默认值」的读取兜底。
这里收敛为共享基类：子类只需在 __init__ 里设置存储路径并调用
write_bytes/write_text/load_list/load_model，方法级并发安全由 self._lock
保证（可传入模块级共享锁）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)


class JsonFileStore:
    def __init__(self, shared_lock: RLock | None = None) -> None:
        self._lock = shared_lock or RLock()

    def write_bytes(self, path: Path, payload: bytes) -> None:
        """原子写：先写同目录 .tmp 再 replace，避免半写文件被读到。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_bytes(payload)
        temp_path.replace(path)

    def write_text(self, path: Path, content: str) -> None:
        self.write_bytes(path, content.encode("utf-8"))

    def load_list(self, path: Path, adapter: TypeAdapter, *, label: str) -> list:
        """读 JSON 列表；文件缺失返回 []，损坏记录 warning 后返回 []。"""
        if not path.exists():
            return []
        try:
            return adapter.validate_json(path.read_bytes())
        except Exception:
            logger.warning("%s 历史损坏，忽略: %s", label, path)
            return []

    def load_model(self, path: Path, model: type[BaseModel], *, label: str) -> BaseModel | None:
        """读单个 JSON 模型；文件缺失返回 None，损坏记录 warning 后返回 None。"""
        if not path.exists():
            return None
        try:
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("%s 快照损坏，忽略: %s", label, path)
            return None
