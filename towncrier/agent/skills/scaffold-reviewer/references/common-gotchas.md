# Common gotchas in agent / MCP scaffolds

## Config vs code drift
- YAML declares tools or roles that the Python (or other) server never implements.
- Role markdown lists tools that do not appear in `mcp-tools.yaml` or the runtime allow-list.
- `instantiate.sh` seeds state but the server looks in a different path.

## Placeholders that break first run
- `homeserver: https://your-synapse.example.com`
- Model names that do not exist on the local Ollama/llama.cpp instance
- Missing `MATRIX_ACCESS_TOKEN` / `CLOUD_API_KEY` env guidance

## MCP skeleton symptoms
- Server loads YAML and prints a count but never calls the SDK
- Handlers exist as plain functions but are not decorated / registered
- `transport: stdio` in YAML while the code only has a `main()` that demos one call

## Security / safety
- `run_shell` (or equivalent) with `shell=True` and weak cwd checks
- No restriction on absolute paths or parent-directory escapes
- Logging tokens or full prompts by accident

## Inference
- Hard-coded cloud model names while policy is `local_first`
- No health-check for the local endpoint before escalating
- Context length / temperature set in YAML but never passed to the actual call

## Task / state
- Seed tasks have no `created`/`updated` timestamps even though schema declares them
- Acceptance criteria that cannot be verified from the tools the agent actually has
- State directory not gitignored

## Matrix
- Config present but the signal tool only prints instead of sending
- No handling of sync, room join, or token refresh
- Reactions / status mapping defined but unused
