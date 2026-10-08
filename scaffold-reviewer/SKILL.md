---
name: scaffold-reviewer
description: Parse small scaffolded codebases (especially agent/MCP/declarative YAML ones), flag incomplete risky or incorrect parts, then pull the exact docs and snippets needed to finish building. Use when the user points at a new scaffold, agent template, MCP skeleton, or says review this scaffold, onboard this codebase, flag the gotchas, or make this buildable.
---

# Scaffold Reviewer

Review a small scaffolded project, surface what is incomplete/tricky/wrong, and retrieve the precise documentation + code patterns required to turn it into a working system.

## When to apply

- User provides or points at a small codebase / zip / directory that looks generated or templated.
- Mentions of "scaffold", "agent template", "MCP server skeleton", "declarative agent", "make this work", "what's missing", "onboard me".
- Especially strong signal for YAML-heavy agent layouts with roles, tasks, lexicon, Matrix, local-first inference, or MCP tool definitions.

## Workflow (follow in order)

### 1. Inventory the scaffold

- List the tree and identify the primary language(s), frameworks, and config style.
- Detect key patterns:
  - Declarative YAML configs (agent.yaml, tools.yaml, tasks.yaml, lexicon, matrix, etc.)
  - MCP server (stdio/SSE, FastMCP, low-level, or pure skeleton)
  - Dual-role or multi-agent contracts in markdown/YAML
  - Local-first inference (Ollama, llama.cpp, vLLM) + cloud fallback
  - External rendezvous (Matrix/Synapse, Discord, etc.)
  - Instantiate / bootstrap scripts
- Note version pins, lockfiles, and missing packages.

### 2. Flag problems (be concrete)

Call out issues with file references where possible. Prioritize:

**Incomplete / skeleton**
- Placeholder values (`your-*.example.com`, `TODO`, stub handlers that only print)
- MCP server that loads YAML but does not actually register tools with an MCP SDK
- Tools declared but not fully implemented or not reachable from a real client
- Missing state seeding, gitignore for runtime dirs, or env-var handling

**Risky / wrong**
- Shell execution without proper sandboxing or path checks
- Hard-coded secrets or missing env-var guidance
- Inference endpoints or models that do not match common local setups
- Overly broad tool permissions vs role contracts
- Missing error handling, timeouts, or acceptance criteria for seed tasks

**Structural**
- Config that the code never reads
- Roles that reference tools the server does not expose
- Circular or missing dependencies between tasks
- Transport mismatches (stdio declared but code assumes something else)

Do not invent problems. Stick to what is actually present or clearly implied by the files.

### 3. Retrieve the needed pieces

For each high-priority flag, pull the minimal relevant documentation:

- Prefer DevDocs (devdocs.io) when the library is covered (Python, httpx, etc.).
- Otherwise use official docs via search + open_page:
  - MCP Python SDK / FastMCP
  - matrix-nio or Matrix Client-Server API
  - Ollama / OpenAI-compatible local endpoints
  - PyYAML safe loading patterns
- Extract only the sections that map to the missing pieces (tool registration, authentication, basic client call, error handling).
- Prefer short, copy-pasteable snippets over long explanations.

If the scaffold already contains implementation notes or comments, treat those as the primary source of intent and align the docs to them.

### 4. Produce the report

Structure the final answer as:

1. **Snapshot** — one-paragraph summary of what the scaffold is trying to be.
2. **Flags** — prioritized list (blocker / important / nice-to-have) with file references and brief rationale.
3. **Build path** — ordered next actions the user (or agent) should take, each tied to a flag.
4. **Docs & snippets** — the exact references and minimal code needed for the top 2–4 items.

Keep the tone direct. Assume the user is competent but wants the shortest path from skeleton to working.

## Supporting resources

- `references/mcp-python.md` — quick patterns for turning a skeleton into a real MCP server
- `references/common-gotchas.md` — recurring issues in agent/MCP scaffolds
- `scripts/inventory.py` — optional helper to dump a structured view of a scaffold directory

## Anti-patterns

- Do not rewrite the entire scaffold unless asked.
- Do not pull full tutorials; only the fragments required by the flags.
- Do not assume a particular agent runtime beyond what the files declare.
