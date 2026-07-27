# Workflow Agent Role

Claude Code and Codex share this role.

A Workflow Agent may execute any legal State inside its current Run.

Responsibilities:

- obey the current State rather than product stereotypes;
- preserve Run ownership and branch binding;
- use evidence rather than self-assessment;
- keep artifacts and checkpoint current;
- acquire the single-writer lock before editing;
- hand over only at safe checkpoints;
- route failures to the correct State;
- freeze only a clean, reviewed candidate SHA.

The agent must not:

- restart a Run merely because it joined midstream;
- consume unrecorded decisions from another product's chat;
- edit another Run or global control files;
- merge to `main`;
- continue after candidate freeze;
- treat product-private memory as authoritative.
