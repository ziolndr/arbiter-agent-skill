# ARBITER MCP integration

Public Streamable HTTP endpoint: `https://api.grip.fyi/mcp`.
Advertised MCP tools: `arbiter_compare` and `arbiter_embed`.

## Claude Code

```bash
claude mcp add --transport http arbiter https://api.grip.fyi/mcp
```

## Generic MCP client configuration

For an MCP host that supports a `url` and `type` object for remote Streamable HTTP:

```json
{
  "mcpServers": {
    "arbiter": {
      "type": "http",
      "url": "https://api.grip.fyi/mcp"
    }
  }
}
```

Host-specific MCP configuration formats vary. Consult the host's documentation before inserting the example verbatim.

Do not invent exact nested MCP tool schemas: obtain tool descriptions/parameters from a live `tools/list` response after initializing the session. MCP transports may reject GET while accepting proper POST initialization. A 402 payment challenge may also occur; do not bypass it.

## Integration procedure

1. Connect and initialize MCP with the client.
2. Retrieve `tools/list` and confirm both expected tools.
3. Build a rich context query and the full candidate array for `arbiter_compare`.
4. Return raw ordering and scores without confidence-language fabrication.
5. Independently check permission before executing any downstream tool.

Do not mistake this skills package for a second MCP server. It is agent guidance and examples for the existing ARBITER API/MCP service.
