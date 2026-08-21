import ast
from pathlib import Path


def test_static_server_proxy_timeout_covers_etf_history_refresh() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source = (repo_root / "apps" / "web-vue" / "static_server.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    timeout = next(
        node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "PROXY_TIMEOUT_SECONDS"
        if isinstance(node.value, ast.Constant)
    )

    assert timeout >= 120


def test_single_container_starts_web_after_api_healthcheck() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = (repo_root / "scripts" / "start-single-container.sh").read_text(encoding="utf-8")

    wait_pos = script.find("wait_for_api_ready")
    web_pos = script.find("/opt/strong-stock-api-venv/bin/python static_server.py")

    assert wait_pos != -1
    assert web_pos != -1
    assert wait_pos < web_pos
    assert "http://127.0.0.1:8010/health" in script
