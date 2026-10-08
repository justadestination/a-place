# MCP Python patterns (for scaffolds)

## Official entry points

- Spec + concepts: https://modelcontextprotocol.io
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- FastMCP (higher-level, common in scaffolds): part of the SDK or `mcp` package

## Minimal real server (stdio)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agent-tools")

@mcp.tool()
def task_list(action: str, id: str | None = None, patch: dict | None = None, task: dict | None = None) -> dict:
    """Read or update the shared task list"""
    # ... call your existing handler ...
    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## Loading declarative tools from YAML

Keep the YAML as the source of truth for names + schemas. In the server:

1. Load `mcp-tools.yaml`
2. For each tool, register a handler that matches the name
3. Validate or document that the Python signatures stay in sync with the YAML `inputSchema`

Scaffolds that only print "Loaded N tools" are incomplete until the handlers are registered with the SDK.

## Common missing pieces in skeletons

- Actual `mcp.run()` or low-level session handling
- Tool result types (content blocks vs plain JSON)
- Error propagation so the client sees failures cleanly
- Optional SSE transport if the client expects HTTP

## Local testing

```bash
# After wiring FastMCP
python server.py   # or mcp run server.py
# Then use any MCP client / inspector that speaks stdio
```
