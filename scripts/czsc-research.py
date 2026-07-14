#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps/api"))

from app.config import get_settings  # noqa: E402
from app.services.chanlun.research_dataset import ResearchDatasetBuilder  # noqa: E402
from app.services.chanlun.research_history import FreeStockDbResearchSource  # noqa: E402
from app.services.chanlun.research_report import verify_dataset_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="CZSC 历史研究数据与验证工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-dataset", help="构建冻结 Parquet 数据集")
    build.add_argument("--start", required=True)
    build.add_argument("--end", required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--free-stockdb-base-url", default=None)
    validate = subparsers.add_parser("validate", help="校验冻结数据集")
    validate.add_argument("--dataset", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    validate.add_argument("--round-trip-cost-bps", type=float, default=20)
    validate.add_argument("--worker-python", default=None)
    args = parser.parse_args()
    if args.command == "build-dataset":
        return _build_dataset(args)
    return _validate(args)


def _build_dataset(args: argparse.Namespace) -> int:
    settings = get_settings()
    source = FreeStockDbResearchSource(
        base_url=args.free_stockdb_base_url or settings.auction_model_free_stockdb_base_url,
        timeout_seconds=settings.auction_model_timeout_seconds,
    )
    manifest = ResearchDatasetBuilder(source=source).build(
        start=args.start,
        end=args.end,
        output=args.output,
    )
    print(json.dumps({"dataset_id": manifest.dataset_id, "root": str(manifest.root)}, ensure_ascii=False))
    return 0


def _validate(args: argparse.Namespace) -> int:
    verify_dataset_manifest(args.dataset / "manifest.json")
    args.output.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"status": "checksum_verified", "generated_at": datetime.now().isoformat()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
