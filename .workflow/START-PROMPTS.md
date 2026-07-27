# Start Prompts

## Continue current Run

```text
Start or continue the current Workflow.
Read the repository entry file, derive the Run ID from the current Git branch,
validate Branch–Run–State ownership and local lock status,
then continue from checkpoint.next_action.
Do not restart the Workflow unless the recorded state is invalid.
```

## Take over from another agent

```text
Take over the current Workflow from the recorded safe checkpoint.
Use a fresh session. Verify Git branch, HEAD, status, state.json, checkpoint.json,
current State requirements, and required capabilities.
Acquire the local lock before writing.
Continue from next_action and preserve all existing decisions.
```

## Recovery after abnormal exit

```text
Enter Recovery Mode for the current Workflow.
Remain read-only initially. Reconstruct current state from Git, Diff, state.json,
checkpoint.json, artifacts, and the smallest safe validation.
Record uncertainty and create a recovered checkpoint before continuing.
```

## Master integration

```text
Act as the Master Integrator.
Read AGENTS.md, the Master role, Integration Protocol, Registry, Merge Queue,
and every queued candidate's state, candidate, impact, validation, review, and Diff.
Use a dedicated integration branch/worktree.
Do not implement unrelated feature work.
```
