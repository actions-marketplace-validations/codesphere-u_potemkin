from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "potemkin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import potemkin  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_clean_app_scores_100_verified() -> None:
    target = FIXTURES / "clean_app"
    report = potemkin.run_scan(target)

    assert report["score"] == 100
    assert report["grade"] == "VERIFIED"
    assert report["findings"] == []
    assert report["wire_graph"] == {
        "backend_routes": 4,
        "client_calls": 3,
        "dead_client_calls": 0,
        "orphan_routes": 0,
    }
    assert report["env_audit"]["missing_from_template"] == []
    assert potemkin.main([str(target), "--fail-on", "any", "--no-color"]) == 0


def test_potemkin_app_catches_all_static_rules() -> None:
    target = FIXTURES / "potemkin_app"
    report = potemkin.run_scan(target)
    found_rules = {item["rule_id"] for item in report["findings"]}

    expected_rules = {f"POT{i:03d}" for i in range(1, 14)}
    assert expected_rules <= found_rules
    assert report["grade"] == "POTEMKIN ALERT"
    assert report["score"] == 0
    assert report["counts"]["critical"] >= 4
    assert potemkin.main([str(target), "--fail-on", "high", "--no-color"]) == 1


def test_false_positive_guards_and_suppressions(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "backend").mkdir()

    (tmp_path / "src" / "ValidComponent.tsx").write_text(
        """
import React from "react";

// Commented fake code must be ignored:
// const MOCK_LIST = [{ id: 1 }];
// fetch("/api/nonexistent");

export function ValidComponent({ go }: { go: () => void }) {
  const localCliUrl = "http://localhost:9222"; // potemkin-ignore: POT010 - local debug protocol
  // potemkin-ignore: POT010 - allowed next line suppression
  const secondLocal = "http://127.0.0.1:9333";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await fetch("/api/items/42", { method: "POST" });
    setTimeout(() => console.log(localCliUrl, secondLocal), 250);
  }

  return (
    <form onSubmit={handleSubmit}>
      <a href="#pricing">Pricing</a>
      <a href="#" onClick={(e) => { e.preventDefault(); go(); }}>Help</a>
    </form>
  );
}
""",
        encoding="utf-8",
    )

    (tmp_path / "src" / "server.ts").write_text(
        """
import express from "express";
const app = express();
const db = process.env.DATABASE_URL;
app.post("/api/items/:id", (_req, res) => {
  res.json({ ok: true, db });
});
""",
        encoding="utf-8",
    )

    (tmp_path / "backend" / "guards.py").write_text(
        """
import os
from abc import ABC, abstractmethod


class BaseStorage(ABC):
    @abstractmethod
    def save(self, key: str) -> None:
        raise NotImplementedError("Subclasses implement save")


def setup_env() -> None:
    os.environ["HF_HOME"] = "/tmp/hf"


def parse_count(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        pass
    return None


def cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass

    return
""",
        encoding="utf-8",
    )

    report = potemkin.run_scan(tmp_path)
    assert report["score"] == 100
    assert report["findings"] == []


def test_potemkinignore_and_config_file(tmp_path: Path) -> None:
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "sandbox" / "rough.tsx").write_text(
        'export const X = () => <button onClick={() => alert("stub")}>Click</button>;\n',
        encoding="utf-8",
    )
    (tmp_path / "app.ts").write_text(
        'export const endpoint = "http://localhost:8080/v1";\n',
        encoding="utf-8",
    )

    # Without ignore config, both POT001 and POT010 fire.
    unfiltered = {f["rule_id"] for f in potemkin.run_scan(tmp_path)["findings"]}
    assert {"POT001", "POT010"} <= unfiltered

    (tmp_path / ".potemkinignore").write_text("sandbox/\n", encoding="utf-8")
    (tmp_path / ".potemkin.json").write_text(json.dumps({"ignoreRules": ["POT010"]}), encoding="utf-8")

    filtered = potemkin.run_scan(tmp_path)
    assert filtered["findings"] == []
    assert filtered["score"] == 100


def test_git_diff_reward_hacking_rules(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Potemkin Test")
    _git(tmp_path, "config", "user.email", "test@potemkin.local")

    test_py = tmp_path / "tests" / "test_math.py"
    test_py.parent.mkdir(parents=True)
    test_py.write_text(
        """
def test_calculations():
    assert 1 + 1 == 2
    assert 2 + 2 == 4
    assert 3 + 3 == 6
    assert 4 + 4 == 8
""",
        encoding="utf-8",
    )
    app_ts = tmp_path / "src" / "math.ts"
    app_ts.parent.mkdir(parents=True)
    app_ts.write_text("export function add(a: number, b: number) { return a + b; }\n", encoding="utf-8")

    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial clean baseline")

    # Stage a skipped JS test and eslint-disable suppression.
    staged_test = tmp_path / "tests" / "math.test.ts"
    staged_test.write_text(
        """
// eslint-disable-next-line @typescript-eslint/no-explicit-any
it.skip("adds numbers", () => {
  expect(true).toBe(true);
});
""",
        encoding="utf-8",
    )
    _git(tmp_path, "add", str(staged_test.relative_to(tmp_path)))

    staged_report = potemkin.run_scan(tmp_path, staged=True)
    staged_rules = {f["rule_id"] for f in staged_report["findings"]}
    assert {"POT014", "POT015", "POT016"} <= staged_rules

    # Add unstaged Python test cheating + ts-ignore + hollowed assertions against HEAD.
    test_py.write_text(
        """
import pytest

@pytest.mark.skip(reason="temporarily bypassed")
def test_calculations():
    assert True
""",
        encoding="utf-8",
    )
    app_ts.write_text(
        """
// @ts-ignore
export function add(a: any, b: any) { return a + b; }
""",
        encoding="utf-8",
    )

    diff_report = potemkin.run_scan(tmp_path, diff_ref="HEAD", with_diff=True)
    diff_rules = {f["rule_id"] for f in diff_report["findings"]}
    assert {"POT014", "POT015", "POT016"} <= diff_rules
    assert diff_report["diff_audit"] == {"ran": True, "ref": "HEAD"}
    assert any(
        f["rule_id"] == "POT016" and "removed" in f["message"]
        for f in diff_report["findings"]
    )


def test_cli_formats_baseline_min_score_and_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Version and missing path handling
    with pytest.raises(SystemExit) as exc:
        potemkin.main(["--version"])
    assert exc.value.code == 0
    assert potemkin.VERSION in capsys.readouterr().out
    assert potemkin.main([str(tmp_path / "missing-dir"), "--no-color"]) == 2
    capsys.readouterr()

    sample = tmp_path / "repo"
    sample.mkdir()
    target_file = sample / "client.ts"
    target_file.write_text('export const api = "http://localhost:5000";\n', encoding="utf-8")

    # --min-score failure when score (96) < 100 despite high threshold
    assert potemkin.main([str(sample), "--fail-on", "critical", "--min-score", "100", "--no-color"]) == 1
    capsys.readouterr()

    # --ignore-rule removes the finding
    assert potemkin.main([str(sample), "--ignore-rule", "POT010", "--fail-on", "any", "--no-color"]) == 0
    capsys.readouterr()

    # Output formats: json, markdown, sarif
    json_out = tmp_path / "report.json"
    sarif_out = tmp_path / "report.sarif"
    assert potemkin.main([str(sample), "--format", "json", "--output", str(json_out), "--fail-on", "none"]) == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["score"] == 96
    capsys.readouterr()

    assert potemkin.main([str(sample), "--format", "markdown", "--fail-on", "none"]) == 0
    assert "Potemkin Real-Code Audit" in capsys.readouterr().out

    assert potemkin.main([str(sample), "--format", "sarif", "--output", str(sarif_out), "--fail-on", "none"]) == 0
    sarif = json.loads(sarif_out.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["tool"]["driver"]["rules"]) == len(potemkin.RULE_META)

    # Baseline workflow suppresses existing findings and catches regressions
    baseline_file = tmp_path / ".potemkin-baseline.json"
    assert potemkin.main([str(sample), "--write-baseline", str(baseline_file), "--fail-on", "none"]) == 0
    capsys.readouterr()
    assert potemkin.main([str(sample), "--baseline", str(baseline_file), "--fail-on", "any", "--no-color"]) == 0
    capsys.readouterr()

    target_file.write_text(
        'export const api = "http://localhost:5000";\nexport const s = process.env.JWT_SECRET || "bad";\n',
        encoding="utf-8",
    )
    assert potemkin.main([str(sample), "--baseline", str(baseline_file), "--fail-on", "critical", "--no-color"]) == 1


def test_skill_package_metadata_and_docs_consistency() -> None:
    skill_md = ROOT / "skills" / "potemkin" / "SKILL.md"
    rules_md = ROOT / "skills" / "potemkin" / "references" / "rules.md"
    remediation_md = ROOT / "skills" / "potemkin" / "references" / "remediation.md"

    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) < 500
    assert lines[0] == "---"
    end_idx = lines.index("---", 1)
    frontmatter = "\n".join(lines[1:end_idx])
    assert "name: potemkin" in frontmatter
    assert f'version: "{potemkin.VERSION}"' in frontmatter
    assert "license: MIT" in frontmatter
    assert rules_md.is_file()
    assert remediation_md.is_file()

    rules_doc = rules_md.read_text(encoding="utf-8")
    for rule_id in potemkin.RULE_META:
        assert rule_id in rules_doc

    plugin_json = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace_json = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin_json["name"] == "potemkin"
    assert marketplace_json["plugins"][0]["name"] == "potemkin"
    assert plugin_json["version"] == potemkin.VERSION
    assert marketplace_json["plugins"][0]["version"] == potemkin.VERSION


def test_production_hardening_assets_outputs_and_warnings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj = tmp_path / "prod"
    proj.mkdir()
    (proj / "vendor.min.js").write_text('const MOCK_VEND = [{a:1}]; alert("x");\n', encoding="utf-8")
    (proj / "types.d.ts").write_text('export declare const MOCK_TYPES: any;\n', encoding="utf-8")
    (proj / "huge.js").write_text('const ok = "real";\n' + ("// pad\n" * 90000), encoding="utf-8")
    (proj / "clean.ts").write_text("export function add(a: number, b: number) { return a + b; }\n", encoding="utf-8")

    report = potemkin.run_scan(proj)
    assert report["score"] == 100
    assert report["files_scanned"] == 1

    # Invalid --min-score fails cleanly with exit code 2
    assert potemkin.main([str(proj), "--min-score", "105", "--no-color"]) == 2
    assert "--min-score" in capsys.readouterr().err

    # Nested --output and --write-baseline auto-create parent directories
    nested_json = tmp_path / "artifacts" / "sub" / "report.json"
    nested_baseline = tmp_path / "baselines" / "sub" / "baseline.json"
    assert potemkin.main([str(proj), "--format", "json", "--output", str(nested_json), "--fail-on", "none"]) == 0
    assert nested_json.is_file()
    assert potemkin.main([str(proj), "--write-baseline", str(nested_baseline), "--fail-on", "none"]) == 0
    assert nested_baseline.is_file()
    capsys.readouterr()

    # --diff on non-git folder emits warning without crashing
    assert potemkin.main([str(proj), "--diff", "HEAD", "--no-color"]) == 0
    captured = capsys.readouterr()
    assert "git diff audit skipped" in captured.err
