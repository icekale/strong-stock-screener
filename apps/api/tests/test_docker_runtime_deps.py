from pathlib import Path


def test_dockerfiles_install_lightgbm_openmp_runtime() -> None:
    repo_root = Path(__file__).parents[3]
    dockerfiles = [repo_root / "Dockerfile", repo_root / "apps/api/Dockerfile"]

    missing = [
        str(path.relative_to(repo_root))
        for path in dockerfiles
        if "libgomp1" not in path.read_text(encoding="utf-8")
    ]

    assert missing == []


def test_api_dependencies_pin_chanlun_runtime_packages() -> None:
    repo_root = Path(__file__).parents[3]
    content = (repo_root / "apps/api/pyproject.toml").read_text(encoding="utf-8")

    assert '"czsc==0.10.12"' in content
    assert '"mootdx==0.11.7"' in content
    assert '"httpx>=0.25.0,<0.26.0"' in content


def test_dockerfiles_import_chanlun_runtime_packages_during_build() -> None:
    repo_root = Path(__file__).parents[3]
    smoke_checks = {
        repo_root / "Dockerfile": "/opt/strong-stock-api-venv/bin/python -c \"import czsc, mootdx\"",
        repo_root / "apps/api/Dockerfile": 'python -c "import czsc, mootdx"',
    }

    for path, smoke_check in smoke_checks.items():
        assert smoke_check in path.read_text(encoding="utf-8")


def test_api_dockerfile_copies_artifacts_after_package_install() -> None:
    repo_root = Path(__file__).parents[3]
    content = (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")

    install_index = content.index("RUN python -m pip install --no-cache-dir --no-build-isolation .")
    artifacts_index = content.index("COPY artifacts ./artifacts")

    assert install_index < artifacts_index
