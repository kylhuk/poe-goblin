from pathlib import Path


def test_makefile_up_uses_dev_overlay_without_build() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "docker-compose.dev.yml" in makefile
    assert "up --build" not in makefile


def test_dev_overlay_mounts_source_and_sets_pythonpath() -> None:
    dev_compose = Path("docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "/app" in dev_compose
    assert "PYTHONPATH=/app" in dev_compose


def test_qa_up_stays_on_base_compose_files() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "QA_COMPOSE" in makefile
    assert (
        "docker-compose.dev.yml"
        not in makefile.split("qa-up:", 1)[1].split("qa-down:", 1)[0]
    )


def test_dockerfile_uses_separate_runtime_dependency_manifest() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "requirements-runtime.txt" in dockerfile
    assert "COPY poe_trade ./poe_trade" in dockerfile
