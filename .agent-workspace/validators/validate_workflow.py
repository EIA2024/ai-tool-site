#!/usr/bin/env python3
"""Read-only linter for the serial Claude–Codex Workflow."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ID_RE = re.compile(r"^WF-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*-[A-F0-9]{4}$")
PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z0-9_ /.-]*>")

STAGE_OWNER = {
    "SCOUTING": "CLAUDE_CONTEXT_SCOUT",
    "HUMAN_INTENT_REVIEW": "HUMAN",
    "CODEX_PLANNING": "CODEX_PLANNING",
    "HUMAN_PLAN_REVIEW": "HUMAN",
    "CLAUDE_EXECUTION": "CLAUDE_EXECUTION",
    "CLAUDE_REVIEW": "CLAUDE_REVIEW",
    "REMEDIATION": "CLAUDE_REMEDIATION",
    "DONE": "NONE",
    "BLOCKED": "HUMAN",
}

COMPLETED_FILES = {
    "SCOUTING": ["WORKFLOW.md"],
    "HUMAN_INTENT_REVIEW": ["WORKFLOW.md", "10-context.md", "20-intent.md"],
    "CODEX_PLANNING": ["WORKFLOW.md", "10-context.md", "20-intent.md"],
    "HUMAN_PLAN_REVIEW": [
        "WORKFLOW.md", "10-context.md", "20-intent.md", "30-plan.md"
    ],
    "CLAUDE_EXECUTION": [
        "WORKFLOW.md", "10-context.md", "20-intent.md", "30-plan.md"
    ],
    "CLAUDE_REVIEW": [
        "WORKFLOW.md", "10-context.md", "20-intent.md",
        "30-plan.md", "40-execution.md"
    ],
    "REMEDIATION": [
        "WORKFLOW.md", "10-context.md", "20-intent.md",
        "30-plan.md", "40-execution.md", "50-review.md"
    ],
    "DONE": [
        "WORKFLOW.md", "10-context.md", "20-intent.md",
        "30-plan.md", "40-execution.md", "50-review.md"
    ],
    "BLOCKED": ["WORKFLOW.md"],
}

HANDOFF_SOURCE = {
    "CODEX_PLANNING": "20-intent.md",
    "HUMAN_PLAN_REVIEW": "30-plan.md",
    "CLAUDE_EXECUTION": "30-plan.md",
    "CLAUDE_REVIEW": "40-execution.md",
    "REMEDIATION": "50-review.md",
    "DONE": "50-review.md",
}

HANDOFF_HEADINGS = [
    "### Workflow",
    "### Completed",
    "### Files produced or updated",
    "### Validation",
    "### Human action",
    "### Copy-Paste Prompt for the Next Agent",
    "### Expected next output",
    "### Stop conditions",
]

CONTEXT_FRESH_STAGES = {
    "HUMAN_INTENT_REVIEW",
    "CODEX_PLANNING",
    "HUMAN_PLAN_REVIEW",
}


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"{path.name}: unterminated YAML frontmatter")
    data: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def git(repo: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode, result.stdout.strip()
    except FileNotFoundError:
        return 127, ""


def check_handoff(path: Path, workflow_id: str, version: str, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if "## Handoff" not in text:
        errors.append(f"{path.name}: missing ## Handoff")
        return

    handoff = text.split("## Handoff", 1)[1]
    for heading in HANDOFF_HEADINGS:
        if heading not in handoff:
            errors.append(f"{path.name}: Handoff missing '{heading}'")

    if f"WORKFLOW_ID: {workflow_id}" not in handoff:
        errors.append(f"{path.name}: copy Prompt missing exact Workflow ID")
    if f"EXPECTED_STATE_VERSION: {version}" not in handoff:
        errors.append(f"{path.name}: copy Prompt missing current state version")
    if f"WORKFLOW_PATH: .agent-workspace/workflows/{workflow_id}" not in handoff:
        errors.append(f"{path.name}: copy Prompt missing exact Workflow path")
    if PLACEHOLDER_RE.search(handoff):
        errors.append(f"{path.name}: Handoff contains unresolved placeholders")


def history_last_row(workflow_text: str) -> tuple[str, str, str] | None:
    rows = []
    for line in workflow_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if cells and cells[0].isdigit() and len(cells) >= 5:
            rows.append(cells)
    if not rows:
        return None
    last = rows[-1]
    return last[0], last[1], last[2]


def validate_change_paths(plan_path: Path, errors: list[str]) -> None:
    text = plan_path.read_text(encoding="utf-8")
    match = re.search(r"## Change Paths.*?```paths\s*(.*?)```", text, re.S)
    if not match:
        errors.append("30-plan.md: missing ```paths Change Paths block")
        return

    paths = []
    for raw in match.group(1).splitlines():
        item = raw.strip()
        if item and not item.startswith("#"):
            paths.append(item)

    if not paths:
        errors.append("30-plan.md: no Change Paths declared")
        return

    for item in paths:
        normalized = item.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if any(char in item for char in ("*", "?")):
            errors.append(f"30-plan.md: wildcard path forbidden: {item}")
        if pure.is_absolute() or re.match(r"^[A-Za-z]:[/\\]", item):
            errors.append(f"30-plan.md: absolute path forbidden: {item}")
        if ".." in pure.parts:
            errors.append(f"30-plan.md: parent traversal forbidden: {item}")
        if normalized.startswith(".agent-workspace/"):
            errors.append(
                f"30-plan.md: Workflow-control path cannot be a product Change Path: {item}"
            )


def context_is_stale(repo: Path, based_on: str) -> bool | None:
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", based_on):
        return None
    code, output = git(
        repo,
        "diff",
        "--name-only",
        f"{based_on}..HEAD",
        "--",
        ".",
        ":(exclude).agent-workspace/**",
    )
    if code != 0:
        return None
    return bool(output.strip())


def report(errors: list[str], warnings: list[str]) -> int:
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: 0 errors, {len(warnings)} warning(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    workflow_id = args.workflow.strip()
    workflow_dir = repo / ".agent-workspace" / "workflows" / workflow_id

    errors: list[str] = []
    warnings: list[str] = []

    if not ID_RE.fullmatch(workflow_id):
        errors.append(f"Invalid Workflow ID format: {workflow_id}")

    if not workflow_dir.is_dir():
        errors.append(f"Workflow directory not found: {workflow_dir}")
        return report(errors, warnings)

    workflow_path = workflow_dir / "WORKFLOW.md"
    if not workflow_path.is_file():
        errors.append("Missing WORKFLOW.md")
        return report(errors, warnings)

    try:
        state = frontmatter(workflow_path)
    except ValueError as exc:
        errors.append(str(exc))
        return report(errors, warnings)

    if state.get("workflow_id") != workflow_id:
        errors.append("WORKFLOW.md workflow_id does not match directory")

    stage = state.get("stage", "")
    if stage not in STAGE_OWNER:
        errors.append(f"Unknown stage: {stage}")

    expected_owner = STAGE_OWNER.get(stage)
    if expected_owner and state.get("current_owner") != expected_owner:
        errors.append(
            f"Stage {stage} requires current_owner {expected_owner}, "
            f"found {state.get('current_owner')}"
        )

    version = state.get("state_version", "")
    try:
        if int(version) < 1:
            raise ValueError
    except ValueError:
        errors.append("state_version must be a positive integer")

    if state.get("execution_mode") != "SERIAL":
        errors.append("execution_mode must be SERIAL")

    expected_branch = f"agent/{workflow_id.lower()}"
    if state.get("working_branch") != expected_branch:
        errors.append(
            f"working_branch must be {expected_branch}, "
            f"found {state.get('working_branch')}"
        )

    code, branch = git(repo, "branch", "--show-current")
    if code == 0 and branch and branch != expected_branch:
        errors.append(f"Current Git branch '{branch}' differs from '{expected_branch}'")

    workflow_text = workflow_path.read_text(encoding="utf-8")
    last = history_last_row(workflow_text)
    if last is None:
        errors.append("WORKFLOW.md: missing History row")
    else:
        hist_version, hist_stage, hist_owner = last
        if hist_version != version:
            errors.append("WORKFLOW.md: History version differs from frontmatter")
        if hist_stage != stage:
            errors.append("WORKFLOW.md: History stage differs from frontmatter")
        if hist_owner != state.get("current_owner"):
            errors.append("WORKFLOW.md: History owner differs from frontmatter")

    metadata: dict[str, dict[str, str]] = {}
    for name in COMPLETED_FILES.get(stage, ["WORKFLOW.md"]):
        path = workflow_dir / name
        if not path.is_file():
            errors.append(f"Missing required file for stage {stage}: {name}")
            continue
        try:
            meta = frontmatter(path)
            metadata[name] = meta
            if meta.get("workflow_id") != workflow_id:
                errors.append(f"{name}: workflow_id mismatch")
        except ValueError as exc:
            errors.append(str(exc))

        if PLACEHOLDER_RE.search(path.read_text(encoding="utf-8")):
            errors.append(f"{name}: unresolved template placeholder")

    handoff_name = HANDOFF_SOURCE.get(stage)
    if handoff_name and (workflow_dir / handoff_name).is_file():
        check_handoff(workflow_dir / handoff_name, workflow_id, version, errors)

    intent = metadata.get("20-intent.md")
    if stage in {
        "CODEX_PLANNING",
        "HUMAN_PLAN_REVIEW",
        "CLAUDE_EXECUTION",
        "CLAUDE_REVIEW",
        "REMEDIATION",
        "DONE",
    }:
        if not intent:
            errors.append("20-intent.md metadata unavailable")
        else:
            if intent.get("author_role") != "CLAUDE_INTENT":
                errors.append("20-intent.md author_role must be CLAUDE_INTENT")
            if intent.get("status") != "APPROVED":
                errors.append("20-intent.md must have status APPROVED")
            if intent.get("human_confirmation") != "YES":
                errors.append("20-intent.md human_confirmation must be YES")
            if intent.get("confirmed_at_utc") in {"", "NONE", None}:
                errors.append("20-intent.md missing confirmed_at_utc")
            if intent.get("confirmed_state_version") in {"", "NONE", None}:
                errors.append("20-intent.md missing confirmed_state_version")

    plan = metadata.get("30-plan.md")
    if stage in {"CLAUDE_EXECUTION", "CLAUDE_REVIEW", "REMEDIATION", "DONE"}:
        if not plan:
            errors.append("30-plan.md metadata unavailable")
        else:
            if plan.get("status") != "APPROVED":
                errors.append("30-plan.md must have status APPROVED")
            if plan.get("human_approval") != "YES":
                errors.append("30-plan.md human_approval must be YES")
            for field in ("approved_at_utc", "approved_state_version", "approved_head_commit"):
                if plan.get(field) in {"", "NONE", None}:
                    errors.append(f"30-plan.md missing {field}")
            validate_change_paths(workflow_dir / "30-plan.md", errors)

    execution = metadata.get("40-execution.md")
    if stage in {"CLAUDE_REVIEW", "REMEDIATION", "DONE"}:
        if not execution:
            errors.append("40-execution.md metadata unavailable")
        elif execution.get("status") != "READY_FOR_REVIEW":
            errors.append("40-execution.md status must be READY_FOR_REVIEW")
        elif execution.get("candidate_head") in {"", "NONE", None}:
            errors.append("40-execution.md missing candidate_head")

    review = metadata.get("50-review.md")
    if stage in {"REMEDIATION", "DONE"}:
        if not review:
            errors.append("50-review.md metadata unavailable")
        else:
            if review.get("author_role") != "CLAUDE_REVIEW":
                errors.append("50-review.md author_role must be CLAUDE_REVIEW")
            if review.get("review_session") != "FRESH":
                errors.append("50-review.md review_session must be FRESH")

    if stage == "REMEDIATION":
        if not review or review.get("status") != "REMEDIATE":
            errors.append("REMEDIATION requires 50-review.md status REMEDIATE")
        selected = state.get("approved_remediation_findings", "NONE")
        if selected == "NONE":
            errors.append("REMEDIATION requires Human-selected finding IDs")
        elif review:
            review_text = (workflow_dir / "50-review.md").read_text(encoding="utf-8")
            for finding in [item.strip() for item in selected.split(",") if item.strip()]:
                if not re.fullmatch(r"F-\d{3,}", finding):
                    errors.append(f"Invalid remediation finding ID: {finding}")
                elif finding not in review_text:
                    errors.append(f"Selected finding not present in review: {finding}")

    if stage == "DONE":
        if state.get("status") != "COMPLETED":
            errors.append("DONE requires Workflow status COMPLETED")
        if not review or review.get("status") != "ACCEPT":
            errors.append("DONE requires 50-review.md status ACCEPT")

    if stage in CONTEXT_FRESH_STAGES:
        context = metadata.get("10-context.md")
        if context:
            stale = context_is_stale(repo, context.get("based_on_commit", ""))
            if stale is True:
                errors.append("10-context.md is stale: product files changed after scouting")
            elif stale is None:
                warnings.append("Could not verify Context freshness")

    if stage in {"CLAUDE_EXECUTION", "REMEDIATION"}:
        workflows_root = repo / ".agent-workspace" / "workflows"
        for sibling in workflows_root.iterdir():
            if not sibling.is_dir() or sibling.name == workflow_id:
                continue
            state_file = sibling / "WORKFLOW.md"
            if not state_file.is_file():
                continue
            try:
                sibling_state = frontmatter(state_file)
            except ValueError:
                continue
            if (
                sibling_state.get("status") == "ACTIVE"
                and sibling_state.get("stage") in {"CLAUDE_EXECUTION", "REMEDIATION"}
            ):
                errors.append(
                    f"Serial policy violation: {sibling.name} is also in "
                    f"{sibling_state.get('stage')}"
                )

    return report(errors, warnings)


if __name__ == "__main__":
    sys.exit(main())
