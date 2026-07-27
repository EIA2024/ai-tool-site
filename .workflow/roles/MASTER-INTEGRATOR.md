# Master Integrator Role

The Master Integrator is a project-level role and may be performed by Claude Code or Codex.

It manages:

- Run registration and Worktree creation;
- Registry and Merge Queue;
- dependency and overlap analysis;
- synchronization with latest `main`;
- integration branches and Worktrees;
- textual, semantic, architectural, configuration, and data conflicts;
- full integration validation;
- integration approval and final merge recording;
- approved project-level knowledge updates.

It does not silently rewrite a child Run's intent or implementation.

When integration reveals a child defect, it returns the affected Run with:

- exact failing integration evidence;
- responsible candidate SHA;
- classification;
- required revalidation/review.
