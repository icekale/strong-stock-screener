import subprocess
import sys
import tomllib
from pathlib import Path


def _docker_instructions(content: str) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    current: list[str] = []
    instruction = ""

    for line in content.splitlines():
        stripped = line.strip()
        if current:
            current.append(stripped.removesuffix("\\").strip())
            if not stripped.endswith("\\"):
                instructions.append((instruction, "\n".join(current)))
                current = []
            continue

        if " " not in stripped:
            continue

        candidate, body = stripped.split(" ", maxsplit=1)
        if candidate not in {"COPY", "FROM", "RUN"}:
            continue

        instruction = candidate
        current = [body.removesuffix("\\").strip()]
        if not stripped.endswith("\\"):
            instructions.append((instruction, "\n".join(current)))
            current = []

    return instructions


def _docker_stages(content: str) -> dict[str, list[tuple[str, str]]]:
    stages: dict[str, list[tuple[str, str]]] = {}
    current_stage = ""

    for instruction, body in _docker_instructions(content):
        if instruction == "FROM":
            tokens = body.split()
            assert len(tokens) >= 3 and tokens[-2].upper() == "AS"
            current_stage = tokens[-1]
            stages[current_stage] = []
        elif current_stage:
            stages[current_stage].append((instruction, body))

    return stages


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


def test_rc8_worker_has_an_independent_locked_project() -> None:
    repo_root = Path(__file__).parents[3]
    with (repo_root / "apps/api/rc8-worker/pyproject.toml").open("rb") as file:
        project = tomllib.load(file)

    assert project["project"]["dependencies"] == ["czsc==1.0.0rc8"]
    assert (repo_root / "apps/api/rc8-worker/uv.lock").exists()


def test_rc8_builders_use_independent_locked_projects_and_pinned_bootstrap() -> None:
    repo_root = Path(__file__).parents[3]
    dockerfiles = {
        repo_root / "Dockerfile": (
            "apps/api/rc8-worker/pyproject.toml apps/api/rc8-worker/uv.lock ./"
        ),
        repo_root / "apps/api/Dockerfile": (
            "rc8-worker/pyproject.toml rc8-worker/uv.lock ./"
        ),
    }
    rc8_import_smoke = (
        '/opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; '
        "assert importlib.metadata.version('czsc') == '1.0.0rc8'\""
    )

    for path, project_copy in dockerfiles.items():
        rc8_builder = _docker_stages(path.read_text(encoding="utf-8"))["rc8-builder"]
        project_copy_indices = [
            index
            for index, (instruction, body) in enumerate(rc8_builder)
            if instruction == "COPY" and body == project_copy
        ]
        build_run_indices = [
            index
            for index, (instruction, body) in enumerate(rc8_builder)
            if instruction == "RUN" and "python -m venv /opt/czsc-rc8-venv" in body
        ]

        assert len(project_copy_indices) == 1
        assert len(build_run_indices) == 1
        assert project_copy_indices[0] < build_run_indices[0]
        build_run = rc8_builder[build_run_indices[0]][1]
        assert "setuptools==83.0.0 wheel==0.47.0 uv==0.11.6" in build_run
        assert rc8_import_smoke in build_run


def test_rc8_runners_copy_and_import_the_venv_after_runtime_dependencies() -> None:
    repo_root = Path(__file__).parents[3]
    dockerfiles = [repo_root / "Dockerfile", repo_root / "apps/api/Dockerfile"]
    rc8_venv_copy = "--from=rc8-builder /opt/czsc-rc8-venv /opt/czsc-rc8-venv"
    rc8_import_smoke = (
        '/opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; '
        "assert importlib.metadata.version('czsc') == '1.0.0rc8'\""
    )

    for path in dockerfiles:
        runner = _docker_stages(path.read_text(encoding="utf-8"))["runner"]
        copy_indices = [
            index
            for index, (instruction, body) in enumerate(runner)
            if instruction == "COPY" and body == rc8_venv_copy
        ]
        libgomp_indices = [
            index
            for index, (instruction, body) in enumerate(runner)
            if instruction == "RUN" and "libgomp1" in body
        ]
        smoke_indices = [
            index
            for index, (instruction, body) in enumerate(runner)
            if instruction == "RUN" and rc8_import_smoke in body
        ]

        assert len(copy_indices) == 1
        assert len(libgomp_indices) == 1
        assert len(smoke_indices) == 1
        assert smoke_indices[0] > copy_indices[0]
        assert smoke_indices[0] > libgomp_indices[0]


def test_runtime_app_copies_include_the_executable_rc8_worker() -> None:
    repo_root = Path(__file__).parents[3]
    worker = repo_root / "apps/api/app/services/chanlun/rc8_worker.py"
    dockerfiles = {
        repo_root / "Dockerfile": ("apps/api/app ./api/app", "/app/api/app"),
        repo_root / "apps/api/Dockerfile": ("app ./app", "/app/app"),
    }

    assert worker.is_file()
    assert "if __name__ == \"__main__\":" in worker.read_text(encoding="utf-8")
    for dockerfile, (app_copy, destination) in dockerfiles.items():
        runner = _docker_stages(dockerfile.read_text(encoding="utf-8"))["runner"]
        assert any(
            instruction == "COPY" and body == app_copy
            for instruction, body in runner
        ), f"{dockerfile} must place the worker under {destination}"


def test_root_runner_asserts_the_formal_czsc_metadata_version() -> None:
    repo_root = Path(__file__).parents[3]
    runner = _docker_stages((repo_root / "Dockerfile").read_text(encoding="utf-8"))["runner"]
    formal_version_assertion = (
        '/opt/strong-stock-api-venv/bin/python -c "import importlib.metadata; '
        "assert importlib.metadata.version('czsc') == '0.10.12'\""
    )

    assert any(
        instruction == "RUN" and formal_version_assertion in body
        for instruction, body in runner
    )


def test_dev_dependencies_use_httpx2_for_starlette_testclient() -> None:
    repo_root = Path(__file__).parents[3]
    with (repo_root / "apps/api/pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert "httpx2>=2.0.0" in pyproject["dependency-groups"]["dev"]

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import warnings; "
            "from starlette.exceptions import StarletteDeprecationWarning; "
            "warnings.simplefilter('error', StarletteDeprecationWarning); "
            "import fastapi.testclient; import httpx2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_dockerfiles_smoke_check_chanlun_runtime_versions() -> None:
    repo_root = Path(__file__).parents[3]
    root_instructions = _docker_instructions((repo_root / "Dockerfile").read_text(encoding="utf-8"))
    api_instructions = _docker_instructions(
        (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    )
    root_runs = [body for kind, body in root_instructions if kind == "RUN"]
    api_runs = [body for kind, body in api_instructions if kind == "RUN"]
    root_smoke_check = (
        '/opt/strong-stock-api-venv/bin/python -c '
        '"import czsc, mootdx; print(czsc.__version__, mootdx.__version__)"'
    )
    api_smoke_check = 'python -c "import czsc, mootdx; print(czsc.__version__, mootdx.__version__)"'

    root_smoke_indices = [index for index, command in enumerate(root_runs) if root_smoke_check in command]
    assert len(root_smoke_indices) == 2
    assert any(api_smoke_check in command for command in api_runs)

    runner_smoke_index = root_smoke_indices[-1]
    runner_libgomp_index = next(
        index for index, command in enumerate(root_runs) if "libgomp1" in command
    )
    root_venv_copy_index = next(
        index
        for index, (kind, command) in enumerate(root_instructions)
        if kind == "COPY" and "--from=api-builder /opt/strong-stock-api-venv" in command
    )
    runner_smoke_instruction_index = next(
        index
        for index, (kind, command) in enumerate(root_instructions)
        if kind == "RUN" and command == root_runs[runner_smoke_index]
    )

    assert runner_smoke_index > runner_libgomp_index
    assert runner_smoke_instruction_index > root_venv_copy_index


def test_dockerfiles_install_dependencies_from_locked_export() -> None:
    repo_root = Path(__file__).parents[3]
    dockerfiles = {
        repo_root / "Dockerfile": "apps/api/pyproject.toml apps/api/uv.lock ./",
        repo_root / "apps/api/Dockerfile": "pyproject.toml uv.lock ./",
    }
    locked_export = "uv export --locked --no-dev --no-emit-project --format requirements-txt"

    for path, lock_copy in dockerfiles.items():
        instructions = _docker_instructions(path.read_text(encoding="utf-8"))
        runs = [body for kind, body in instructions if kind == "RUN"]

        assert any(kind == "COPY" and lock_copy in body for kind, body in instructions)
        assert any(locked_export in command and "-o requirements.txt" in command for command in runs)
        assert any("pip install" in command and "-r requirements.txt" in command for command in runs)
        assert any("pip install" in command and "--no-deps" in command for command in runs)
        assert any("pip install" in command and "uv==0.11.6" in command for command in runs)
        assert any("pip uninstall -y uv" in command for command in runs)
        assert all("uv export --frozen" not in command for command in runs)


def test_root_exporter_is_removed_before_copying_the_runtime_venv() -> None:
    repo_root = Path(__file__).parents[3]
    instructions = _docker_instructions((repo_root / "Dockerfile").read_text(encoding="utf-8"))

    exporter_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "RUN" and "uv export" in command
    )
    venv_copy_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "COPY" and "--from=api-builder /opt/strong-stock-api-venv" in command
    )

    assert "pip uninstall -y uv" in instructions[exporter_index][1]
    assert exporter_index < venv_copy_index


def test_api_dockerfile_copies_source_after_locked_dependencies() -> None:
    repo_root = Path(__file__).parents[3]
    instructions = _docker_instructions(
        (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    )

    dependencies_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "RUN" and "uv export --locked" in command and "-r requirements.txt" in command
    )
    source_copy_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "COPY" and command == "app ./app"
    )
    app_install_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "RUN" and "pip install" in command and "--no-deps" in command
    )

    assert dependencies_index < source_copy_index < app_install_index


def test_api_dockerfile_copies_artifacts_after_package_install() -> None:
    repo_root = Path(__file__).parents[3]
    instructions = _docker_instructions(
        (repo_root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    )

    install_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "RUN" and "pip install" in command and "--no-deps" in command
    )
    artifacts_index = next(
        index
        for index, (kind, command) in enumerate(instructions)
        if kind == "COPY" and command == "artifacts ./artifacts"
    )

    assert install_index < artifacts_index
