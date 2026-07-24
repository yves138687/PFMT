import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_required_reference_docs_exist() -> None:
    required_docs = [
        "README.md",
        "docs/Personal_Knowledge_System_Iteration_Plan.md",
        "docs/Personal_Knowledge_System_Project_Structure_Convention.md",
        "docs/Personal_Knowledge_System_Technical_Architecture.md",
    ]

    missing = [path for path in required_docs if not (ROOT / path).exists()]
    assert missing == []


def test_conda_environment_is_python_312() -> None:
    environment_text = read_text("scripts/dev/environment.yml")

    assert re.search(r"(?m)^name:\s*pfmt-py312\s*$", environment_text)
    assert "python=3.12" in environment_text
    assert "fastapi" in environment_text.lower()
    assert "pytest" in environment_text.lower()


def test_dev_scripts_exist_and_keep_chinese_notes() -> None:
    script_paths = [
        "scripts/dev/bootstrap_dev.ps1",
        "scripts/dev/start_server.ps1",
        "scripts/dev/start_web.ps1",
        "scripts/dev/run_tests.ps1",
        "scripts/dev/self_check.ps1",
    ]

    for script_path in script_paths:
        content = read_text(script_path)
        assert "#requires -Version 7.0" in content
        assert re.search(r"[\u4e00-\u9fff]", content), f"{script_path} should keep Chinese notes"


def test_env_example_contains_only_placeholders() -> None:
    env_text = read_text(".env.example")

    assert "PFMT_JWT_SECRET_KEY=replace_with_" in env_text
    assert "PFMT_FILE_MASTER_KEY=replace_with_" in env_text
    assert "PFMT_DATABASE_URL=sqlite:///./storage/db/pfmt-dev.sqlite3" in env_text

    forbidden_secret_patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
    ]
    for pattern in forbidden_secret_patterns:
        assert re.search(pattern, env_text) is None


def test_phase1_contract_covers_required_scenarios() -> None:
    contract_path = ROOT / "tests/contracts/phase1_api_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    scenario_ids = {scenario["id"] for scenario in contract["scenarios"]}

    assert {
        "login",
        "settings_read",
        "settings_update",
        "tree_read",
        "upload_encrypted_markdown",
        "markdown_view",
    }.issubset(scenario_ids)


def test_phase1_checklist_mentions_core_flows() -> None:
    checklist_text = read_text("tests/checklists/phase1_self_check.md")

    for keyword in ["登录", "配置", "目录树", "上传", "加密", "Markdown"]:
        assert keyword in checklist_text
