# ruff: noqa: F401,F403,F405
"""强势股选股 API 应用入口。

路由按域拆分到 app/routers/*.py，装配层在 app/deps.py，共享辅助在 app/helpers.py，
生命周期在 app/lifespan.py，跨模块转发在 app/compat.py。本文件只负责：
  1) 创建 FastAPI 实例并注册中间件与路由
  2) 向后兼容再导出（测试与历史调用点依赖 app.main 命名空间）
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.compat import *  # noqa: F401,F403  # 装配层/共享辅助/缓存常量
from app.lifespan import (
    _clear_data_source_caches,
    lifespan,
    shutdown_auction_sampler,
    shutdown_capital_signal_sampler,
    shutdown_chanlun_research,
    shutdown_etf_three_factor_sampler,
    shutdown_sector_workbench_sampler,
    startup_auction_sampler,
    startup_capital_signal_sampler,
    startup_etf_three_factor_sampler,
    startup_sector_workbench_sampler,
)
from app.routers import (
    auction as _auction_router,
    chanlun as _chanlun_router,
    etf as _etf_router,
    gsgf as _gsgf_router,
    market as _market_router,
    screen as _screen_router,
    sectors as _sectors_router,
    sentiment as _sentiment_router,
    stocks as _stocks_router,
    system as _system_router,
    watchlist as _watchlist_router,
)

app = FastAPI(title="强势股选股 API", version="0.1.0", lifespan=lifespan)
bind_app(app)
logger = logging.getLogger(__name__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_origin_regex=_cors_allow_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router in (
    _system_router.router,
    _sentiment_router.router,
    _screen_router.router,
    _gsgf_router.router,
    _market_router.router,
    _etf_router.router,
    _auction_router.router,
    _sectors_router.router,
    _stocks_router.router,
    _chanlun_router.router,
    _watchlist_router.router,
):
    app.include_router(_router)


# ---------------------------------------------------------------------------
# 向后兼容转发：update_runtime_settings 现属 system 域路由
# ---------------------------------------------------------------------------

def update_runtime_settings(request):
    return _system_router.update_runtime_settings(request)
