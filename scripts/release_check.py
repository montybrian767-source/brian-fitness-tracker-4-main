from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    status: str
    evidence: str
    required_fix: str


def run_command(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)


def compile_check() -> CheckResult:
    files = [
        ROOT / "app.py",
        ROOT / "services" / "supabase_service.py",
        ROOT / "engines" / "recovery_readiness_engine.py",
        ROOT / "pages" / "apple_activity.py",
        ROOT / "config" / "version.py",
        ROOT / "utils" / "datetime_utils.py",
    ]
    failures = []
    for file_path in files:
        try:
            py_compile.compile(str(file_path), doraise=True)
        except Exception as exc:
            failures.append(f"{file_path.name}: {exc}")
    if failures:
        return CheckResult("Compile Key Files", "Fail", " | ".join(failures), "Fix syntax/import errors in listed files.")
    return CheckResult("Compile Key Files", "Pass", f"Compiled {len(files)} files successfully.", "")


def pytest_check() -> CheckResult:
    proc = run_command([sys.executable, "-m", "pytest", "-q", "tests"])
    if proc.returncode == 0:
        tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "pytest passed"
        return CheckResult("Automated Tests", "Pass", tail, "")
    evidence = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
    snippet = " | ".join(evidence[-5:]) if evidence else "pytest failed"
    return CheckResult("Automated Tests", "Fail", snippet, "Run pytest locally and fix failing tests.")


def version_check() -> CheckResult:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    apple_text = (ROOT / "pages" / "apple_activity.py").read_text(encoding="utf-8")
    blockers = []
    for token in ["Brian Fit 7.4", "Brian Fit 7.5", "Brian Fit 8.0 • X.20 Adaptive AI Coach", "Brian Fitness Tracker X"]:
        if token in app_text:
            blockers.append(f"app.py still contains: {token}")
    if "Brian Fit 7.4" in apple_text:
        blockers.append("pages/apple_activity.py still contains Brian Fit 7.4")

    if blockers:
        return CheckResult("Version Consistency", "Fail", " | ".join(blockers), "Replace hardcoded labels with config.version constants.")
    return CheckResult("Version Consistency", "Pass", "No legacy version labels found in app shell pages.", "")


def git_hygiene_check() -> CheckResult:
    proc = run_command(["git", "status", "--porcelain"])
    if proc.returncode != 0:
        return CheckResult("Git Hygiene", "Not Tested", proc.stderr.strip() or "git status failed", "Verify git availability and rerun.")

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        return CheckResult("Git Hygiene", "Pass", "Working tree clean.", "")

    risky_tokens = [".env", "secrets.toml", "data/workout_log.csv", "data/nutrition_log.csv", "data/recovery_log.csv", "data/supplement_log.csv", "data/body_stats.csv"]
    risky = [line for line in lines if any(token in line for token in risky_tokens)]
    if risky:
        return CheckResult("Git Hygiene", "Fail", " | ".join(risky[:10]), "Unstage/remove runtime or secret files before push.")
    return CheckResult("Git Hygiene", "Pass", f"Dirty tree with {len(lines)} files, no runtime/secrets detected.", "")


def run_release_checks() -> List[CheckResult]:
    return [
        compile_check(),
        pytest_check(),
        version_check(),
        git_hygiene_check(),
    ]


def print_markdown_table(results: List[CheckResult]) -> None:
    print("| Check | Pass / Fail / Not Tested | Evidence | Required Fix |")
    print("|---|---|---|---|")
    for item in results:
        evidence = item.evidence.replace("|", "/")
        fix = item.required_fix.replace("|", "/")
        print(f"| {item.name} | {item.status} | {evidence} | {fix} |")


if __name__ == "__main__":
    results = run_release_checks()
    print_markdown_table(results)
    print("\nJSON:")
    print(json.dumps([r.__dict__ for r in results], indent=2))
