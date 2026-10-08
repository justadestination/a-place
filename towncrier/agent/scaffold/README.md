# Agent Scaffold (declarative)

Minimal, privacy-first scaffold for a dual-role agent (Builder + Researcher) that:
- Prefers local Hermes inference, escalates to cloud only when reasoning depth requires it
- Exposes a small MCP server with useful tools
- Shares an intuitive lexicon so human ↔ agent communication stays low-signal
- Maintains a task list
- Uses an existing Synapse/Matrix room as the secure chat / rendezvous channel

## Instantiation (one command)

```bash
# From this directory
./instantiate.sh
```

Or manually:
1. Copy `config/*.yaml` and edit the few placeholders (Matrix room ID, local model endpoint, optional cloud key).
2. `pip install -r mcp-server/requirements.txt`
3. Start MCP: `python -m mcp_server`
4. Point your agent runtime (or thin client) at the configs + MCP.

## Layout

```
config/
  agent.yaml          # roles, inference policy, escalation rules
  lexicon.yaml        # shared dictionary (intuitive code)
  tasks.yaml          # task schema + seed list
  mcp-tools.yaml      # declarative tool definitions for the MCP server
  matrix.yaml         # Synapse/Matrix room + auth
mcp-server/           # tiny MCP implementation that loads the YAML tools
roles/                # system prompts / contracts for each side
state/                # runtime (tasks, memory) — gitignored in real use
instantiate.sh
```

## Design notes

- Everything important is YAML. Code is only the thin loader + MCP server.
- Lexicon is intentionally plain-English-feeling but domain-specific; expand it together.
- Task list is the single source of truth the agent checks before acting.
- Matrix is the only external persistent channel; treat it as the rendezvous point.
- No hard-coded cloud keys. Local first.