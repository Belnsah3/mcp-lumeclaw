# MCP Memory LumeClaw 

Model Context Protocol (MCP) server for Memory LumeClaw — a persistent shared memory system spanning Claude Code, OpenClaw, Codex CLI, and other systems.

## Features
- Semantic Vector Search
- Categories & Tagging
- Secure API Key Authentication

## Requirements
- Python 3.8+
- An API Key from [memory.lumeclaw.ru](https://memory.lumeclaw.ru)

## Quickstart

Configure your MCP-compatible client with your \`LUMECLAW_API_KEY\`:

### Claude Desktop
Add this to your \`claude_desktop_config.json\`:

\`\`\`json
{
  "mcpServers": {
    "memory-lumeclaw": {
      "command": "python3",
      "args": ["/path/to/mcp-lumeclaw/server.py"],
      "env": {
        "LUMECLAW_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
\`\`\`
