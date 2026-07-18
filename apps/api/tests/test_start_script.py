from pathlib import Path


def test_single_container_starts_web_after_api_healthcheck() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = (repo_root / "scripts" / "start-single-container.sh").read_text(encoding="utf-8")

    wait_pos = script.find("wait_for_api_ready")
    web_pos = script.find("node server.mjs")

    assert wait_pos != -1
    assert web_pos != -1
    assert wait_pos < web_pos
    assert "http://127.0.0.1:8010/health" in script
