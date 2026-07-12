from __future__ import annotations

import json
import py_compile
import subprocess
import sys
import ast
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
        ROOT / "utils" / "performance_utils.py",
        ROOT / "engines" / "adaptive_ai_coach_engine.py",
        ROOT / "services" / "supabase_service.py",
        ROOT / "services" / "workout_save_service.py",
        ROOT / "services" / "cardio_session_service.py",
        ROOT / "services" / "apple_health_import_service.py",
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
    version_text = (ROOT / "config" / "version.py").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    apple_text = (ROOT / "pages" / "apple_activity.py").read_text(encoding="utf-8")
    blockers = []
    if 'APP_VERSION = "X 11.1"' not in version_text:
        blockers.append('config/version.py is not set to X 11.1')
    if 'X.41 Premium AI Coach Experience' not in version_text:
        blockers.append('config/version.py is missing X.41 build label')
    for token in ["Brian Fit 7.4", "Brian Fit 7.5", "Brian Fit 8.0 • X.20 Adaptive AI Coach", "Brian Fitness Tracker X"]:
        if token in app_text:
            blockers.append(f"app.py still contains: {token}")
    if "Brian Fit 7.4" in apple_text:
        blockers.append("pages/apple_activity.py still contains Brian Fit 7.4")

    if blockers:
        return CheckResult("Version Consistency", "Fail", " | ".join(blockers), "Replace hardcoded labels with config.version constants.")
    return CheckResult("Version Consistency", "Pass", "No legacy version labels found in app shell pages.", "")


def cache_decorator_check() -> CheckResult:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    supabase_text = (ROOT / "services" / "supabase_service.py").read_text(encoding="utf-8")
    issues = []
    if "@st.cache_resource(show_spinner=False)" not in supabase_text:
        issues.append("Supabase client cache_resource is missing show_spinner=False")
    required_cache_calls = [
        "@st.cache_data(ttl=60, show_spinner=False)",
        "@st.cache_data(ttl=3600, show_spinner=False)",
    ]
    for snippet in required_cache_calls:
        if snippet not in app_text:
            issues.append(f"Missing cache decorator pattern: {snippet}")
    if issues:
        return CheckResult("Cache Decorator Checks", "Fail", " | ".join(issues), "Apply required cache decorators with show_spinner=False and correct TTL.")
    return CheckResult("Cache Decorator Checks", "Pass", "Required cache decorators detected.", "")


def _collect_module_level_calls(tree: ast.AST) -> List[str]:
    calls: List[str] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name):
                calls.append(call.func.id)
            elif isinstance(call.func, ast.Attribute):
                calls.append(call.func.attr)
    return calls


def top_level_query_detection() -> CheckResult:
    app_path = ROOT / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_calls = _collect_module_level_calls(tree)
    risky = [
        name for name in module_calls
        if name in {"get_workouts", "load_log", "load_cardio_log", "get_apple_activity_daily", "get_apple_workouts_dataframe"}
    ]
    if risky:
        return CheckResult(
            "Top-level Query Detection",
            "Fail",
            "Top-level calls found: " + ", ".join(sorted(set(risky))),
            "Move data queries behind route-specific render functions or cached loaders.",
        )
    return CheckResult("Top-level Query Detection", "Pass", "No direct top-level data query calls detected.", "")


def duplicate_query_warning_check() -> CheckResult:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    if "record_query_call(" not in app_text:
        return CheckResult("Duplicate-query Warnings", "Fail", "No query-call instrumentation found.", "Add record_query_call instrumentation in cached query helpers.")
    if "Duplicate query calls detected in this rerun" not in app_text:
        return CheckResult("Duplicate-query Warnings", "Fail", "Data Manager warning text missing.", "Add duplicate query warning UI in diagnostics.")
    return CheckResult("Duplicate-query Warnings", "Pass", "Query-call instrumentation and warning UI detected.", "")


def performance_summary_check() -> CheckResult:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    required = ["Performance Diagnostics", "Render Time", "Slowest Section", "perf_render_state"]
    missing = [token for token in required if token not in app_text]
    if missing:
        return CheckResult("Performance Test Summary", "Fail", "Missing diagnostics markers: " + ", ".join(missing), "Expose performance summary metrics in Data Manager.")
    return CheckResult("Performance Test Summary", "Pass", "Performance diagnostics markers detected.", "")


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
        cache_decorator_check(),
        top_level_query_detection(),
        duplicate_query_warning_check(),
        performance_summary_check(),
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
