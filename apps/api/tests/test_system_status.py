from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import MARKET_OVERVIEW_CACHE, STOCK_KLINE_CACHE, _clear_data_source_caches, app


class RaisingStatusService:
    @property
    def status(self):
        raise RuntimeError("status unavailable")


class RaisingThreadService:
    @property
    def _thread(self):
        raise RuntimeError("thread unavailable")


def test_system_cache_api_lists_registered_caches() -> None:
    client = TestClient(app)

    response = client.get("/api/system/cache")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    names = {item["name"] for item in payload["items"]}
    assert "market_overview" in names


def test_system_cache_clear_requires_group_or_all() -> None:
    client = TestClient(app)

    response = client.post("/api/system/cache/clear")

    assert response.status_code == 400
    assert response.json()["detail"] == "必须指定 group 或 all=true"


def test_system_cache_clear_rejects_unknown_group() -> None:
    client = TestClient(app)

    response = client.post("/api/system/cache/clear?group=unknown")

    assert response.status_code == 400
    assert response.json()["detail"] == "未知缓存分组: unknown"


def test_system_cache_clear_rejects_group_and_all_together() -> None:
    client = TestClient(app)

    response = client.post("/api/system/cache/clear?group=home&all=true")

    assert response.status_code == 400
    assert response.json()["detail"] == "group 和 all=true 不能同时使用"


def test_system_cache_clear_all_clears_registered_caches() -> None:
    client = TestClient(app)
    _clear_data_source_caches()
    MARKET_OVERVIEW_CACHE.get_or_set("unit-test-all", lambda: object())
    STOCK_KLINE_CACHE.get_or_set("unit-test-all", lambda: object())

    response = client.post("/api/system/cache/clear?all=true")

    assert response.status_code == 200
    cleared = response.json()["cleared"]
    assert "market_overview" in cleared
    assert "stock_kline" in cleared
    assert MARKET_OVERVIEW_CACHE.snapshot()["size"] == 0
    assert STOCK_KLINE_CACHE.snapshot()["size"] == 0


def test_system_cache_clear_valid_group_clears_only_that_group() -> None:
    client = TestClient(app)
    _clear_data_source_caches()
    MARKET_OVERVIEW_CACHE.get_or_set("unit-test-home", lambda: object())
    STOCK_KLINE_CACHE.get_or_set("unit-test-stock", lambda: object())

    try:
        response = client.post("/api/system/cache/clear?group=home")

        assert response.status_code == 200
        cleared = response.json()["cleared"]
        assert "market_overview" in cleared
        assert "stock_kline" not in cleared
        assert MARKET_OVERVIEW_CACHE.snapshot()["size"] == 0
        assert STOCK_KLINE_CACHE.snapshot()["size"] == 1
    finally:
        _clear_data_source_caches()


def test_clear_data_source_caches_clears_registered_cache() -> None:
    _clear_data_source_caches()
    MARKET_OVERVIEW_CACHE.get_or_set("unit-test-helper", lambda: object())

    _clear_data_source_caches()

    assert MARKET_OVERVIEW_CACHE.snapshot()["size"] == 0


def test_system_status_exposes_jobs_and_cache_summary() -> None:
    client = TestClient(app)

    response = client.get("/api/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "generated_at" in payload
    assert payload["cache"]["total"] >= 1
    job_names = {job["name"] for job in payload["jobs"]}
    assert "auction_sampler" in job_names
    assert "sector_workbench_sampler" in job_names
    assert "sentiment_monitor" in job_names
    assert "gsgf_auto_review" in job_names


def test_system_status_tolerates_sentiment_monitor_with_raising_status_property() -> None:
    had_monitor = hasattr(app.state, "sentiment_monitor")
    previous_monitor = getattr(app.state, "sentiment_monitor", None)
    app.state.sentiment_monitor = RaisingStatusService()
    client = TestClient(app)

    try:
        response = client.get("/api/system/status")
    finally:
        if had_monitor:
            app.state.sentiment_monitor = previous_monitor
        else:
            delattr(app.state, "sentiment_monitor")

    assert response.status_code == 200
    sentiment_job = next(job for job in response.json()["jobs"] if job["name"] == "sentiment_monitor")
    assert sentiment_job["running"] is False
    assert "状态不可用" in sentiment_job["detail"]


def test_system_status_tolerates_services_with_raising_thread_property() -> None:
    had_auction = hasattr(app.state, "auction_sampler")
    had_gsgf = hasattr(app.state, "gsgf_auto_review_service")
    previous_auction = getattr(app.state, "auction_sampler", None)
    previous_gsgf = getattr(app.state, "gsgf_auto_review_service", None)
    app.state.auction_sampler = RaisingThreadService()
    app.state.gsgf_auto_review_service = RaisingThreadService()
    client = TestClient(app)

    try:
        response = client.get("/api/system/status")
    finally:
        if had_auction:
            app.state.auction_sampler = previous_auction
        else:
            delattr(app.state, "auction_sampler")
        if had_gsgf:
            app.state.gsgf_auto_review_service = previous_gsgf
        else:
            delattr(app.state, "gsgf_auto_review_service")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    jobs = {job["name"]: job for job in response.json()["jobs"]}
    assert jobs["auction_sampler"]["running"] is False
    assert jobs["gsgf_auto_review"]["running"] is False
    assert "状态不可用" in jobs["auction_sampler"]["detail"]
    assert "状态不可用" in jobs["gsgf_auto_review"]["detail"]


def test_system_status_uses_current_cache_error_state_not_historical_count() -> None:
    client = TestClient(app)
    _clear_data_source_caches()

    def failing_factory() -> object:
        raise RuntimeError("provider down")

    try:
        MARKET_OVERVIEW_CACHE.get_or_set("unit-test-cache-recovery", failing_factory)
    except RuntimeError:
        pass

    MARKET_OVERVIEW_CACHE.get_or_set("unit-test-cache-recovery", lambda: object())

    response = client.get("/api/system/status")

    assert response.status_code == 200
    payload = response.json()
    market_overview = next(
        item for item in payload["cache"]["items"] if item["name"] == "market_overview"
    )
    assert market_overview["refresh_error_count"] > 0
    assert market_overview["last_error"] is None
    assert payload["status"] == "ok"
