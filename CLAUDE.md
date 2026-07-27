@AGENTS.md

# Claude Code Runtime Notes

Claude Code is one compatible runtime for this workflow; it does not own particular States.

- Treat `.workflow/runs/<run-id>/` as the only Run-specific memory.
- Do not use Claude Auto Memory as workflow state.
- Open a fresh conversation when taking over from Codex or after workflow rules change.
- At a takeover, reconstruct state from Git, `state.json`, `checkpoint.json`, current artifacts, and actual command evidence.
- If the current lock belongs to another active agent, remain read-only and request a release or explicit forced takeover.
