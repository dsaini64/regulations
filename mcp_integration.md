# MCP Integration Guide

This document explains how to integrate Model Context Protocol (MCP) with the Regulation Search System.

## Why MCP?

MCP (Model Context Protocol) would be excellent for this use case because:

1. **Resource Exposure**: Regulations can be exposed as MCP resources, making them accessible to AI agents and other MCP clients
2. **Tool Integration**: Search and analysis functions can be exposed as MCP tools
3. **Standardized Interface**: Provides a standard way for agents to interact with regulation data
4. **Extensibility**: Easy to add new capabilities without changing the core system

## MCP Server Implementation

### Option 1: Simple MCP Server (Python)

Create an MCP server that exposes regulations as resources:

```python
# mcp_server.py
from mcp.server import Server
from mcp.types import Resource, Tool
import requests

server = Server("regulations-mcp-server")

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List all regulations as resources"""
    response = requests.get("http://localhost:5000/api/regulations")
    regulations = response.json()
    
    resources = []
    for reg in regulations:
        resources.append(Resource(
            uri=f"regulation://{reg['id']}",
            name=f"{reg.get('part', reg.get('chapter', 'Regulation'))}",
            description=reg.get('description', ''),
            mimeType="application/json"
        ))
    
    return resources

@server.get_resource()
async def get_resource(uri: str) -> str:
    """Get a specific regulation resource"""
    reg_id = uri.split("://")[1]
    response = requests.get(f"http://localhost:5000/api/regulations/{reg_id}")
    return json.dumps(response.json())

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="search_regulations",
            description="Search Title 21 regulations by keyword",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="analyze_regulation",
            description="Analyze a regulation query comprehensively",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query to analyze"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Execute a tool"""
    if name == "search_regulations":
        response = requests.post(
            "http://localhost:5000/api/search",
            json={"query": arguments["query"]}
        )
        return json.dumps(response.json())
    
    elif name == "analyze_regulation":
        from agent_workflow import RegulationAgentWorkflow
        agent = RegulationAgentWorkflow()
        result = agent.analyze(
            arguments["query"],
            arguments.get("context")
        )
        return json.dumps(result)
    
    else:
        raise ValueError(f"Unknown tool: {name}")
```

### Option 2: Using Existing MCP Framework

If you're using an MCP framework like `@modelcontextprotocol/sdk`:

1. **Install MCP SDK**:
```bash
npm install @modelcontextprotocol/sdk
```

2. **Create MCP Server**:
```typescript
// mcp-server.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { 
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const server = new Server({
  name: 'regulations-mcp-server',
  version: '1.0.0',
}, {
  capabilities: {
    resources: {},
    tools: {},
  },
});

// List regulations as resources
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const response = await fetch('http://localhost:5000/api/regulations');
  const regulations = await response.json();
  
  return {
    resources: regulations.map((reg: any) => ({
      uri: `regulation://${reg.id}`,
      name: reg.part || reg.chapter || 'Regulation',
      description: reg.description || '',
      mimeType: 'application/json',
    })),
  };
});

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'search_regulations',
        description: 'Search Title 21 regulations',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query',
            },
          },
          required: ['query'],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'search_regulations') {
    const query = request.params.arguments?.query;
    const response = await fetch('http://localhost:5000/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const result = await response.json();
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});
```

## MCP Client Configuration

### For Cursor/Claude Desktop

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "regulations": {
      "command": "python",
      "args": ["/path/to/regulations/mcp_server.py"],
      "env": {
        "API_BASE_URL": "http://localhost:5000"
      }
    }
  }
}
```

## Benefits of MCP Integration

1. **AI Agent Access**: AI agents can directly access regulations as resources
2. **Tool-Based Queries**: Agents can use tools to search and analyze regulations
3. **Standardized Interface**: Consistent API for all MCP-compatible clients
4. **Extensibility**: Easy to add new tools and resources
5. **Composability**: Can combine with other MCP servers for complex workflows

## Usage Example

Once MCP is set up, agents can:

```python
# Agent can access regulations as resources
regulation = mcp_client.get_resource("regulation://123")

# Agent can use tools
results = mcp_client.call_tool("search_regulations", {
    "query": "medical devices"
})

# Agent can analyze comprehensively
analysis = mcp_client.call_tool("analyze_regulation", {
    "query": "drug approval process",
    "context": "FDA submission requirements"
})
```

## Next Steps

1. Install MCP SDK (Python or TypeScript)
2. Implement MCP server using one of the options above
3. Configure MCP client (Cursor, Claude Desktop, etc.)
4. Test with sample queries
5. Extend with additional tools as needed

