# MCP Implementation Guide

This document describes the MCP (Model Context Protocol) server implementation for the Regulations Search Platform.

## Overview

The MCP server exposes regulations as resources and provides tools for search, analysis, and monitoring. This allows AI agents and MCP-compatible clients to interact with the regulations system through a standardized protocol.

## Installation

1. Install MCP SDK:
```bash
pip install 'mcp[cli]'
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

## Running the MCP Server

### Prerequisites

1. **Flask app must be running**: The MCP server communicates with the Flask API at `http://localhost:5000` by default.

```bash
# Terminal 1: Start Flask app
python app.py

# Terminal 2: Start MCP server
python mcp_server.py
```

### Configuration

Set the `API_BASE_URL` environment variable to point to your Flask API:

```bash
export API_BASE_URL=http://localhost:5000
python mcp_server.py
```

## MCP Resources

The server exposes all regulations as MCP resources:

- **URI Format**: `regulation://{id}`
- **MIME Type**: `application/json`
- **Description**: Includes regulation part, chapter, subchapter, and status

### Example Resource:
```
URI: regulation://123
Name: Part 862 - Chapter I - Subchapter H
Description: [Requires Compliance] Clinical chemistry and clinical toxicology devices
```

## MCP Tools

### 1. `search_regulations`

Search Title 21 FDA regulations using semantic search (RAG).

**Parameters:**
- `query` (required): Search query string
- `use_rag` (optional, default: true): Use RAG semantic search
- `limit` (optional, default: 20): Maximum number of results

**Example:**
```json
{
  "query": "medical device approval",
  "use_rag": true,
  "limit": 10
}
```

### 2. `ask_regulation_question`

Ask a natural language question about FDA Title 21 regulations.

**Parameters:**
- `question` (required): Question about regulations
- `use_rag` (optional, default: true): Use RAG for context retrieval

**Example:**
```json
{
  "question": "What are the requirements for importing prescription drugs?",
  "use_rag": true
}
```

### 3. `get_regulation_by_id`

Get a specific regulation by its database ID.

**Parameters:**
- `regulation_id` (required): The ID of the regulation

**Example:**
```json
{
  "regulation_id": 123
}
```

### 4. `get_recent_changes`

Get recently updated regulations with change details.

**Parameters:**
- `limit` (optional, default: 10): Maximum number of changes to return

**Example:**
```json
{
  "limit": 20
}
```

### 5. `get_regulation_stats`

Get statistics about regulations in the database.

**Parameters:** None

## Client Configuration

### For Cursor IDE

Add to your Cursor MCP configuration (`~/.cursor/mcp.json` or similar):

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

### For Claude Desktop

Add to Claude Desktop MCP configuration:

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

### For Other MCP Clients

The server uses stdio transport, so it can be used with any MCP-compatible client that supports stdio servers.

## Testing

### Using MCP Inspector

Install and run the MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

Then connect to the server:
```bash
python mcp_server.py
```

### Manual Testing

You can test the server by running it directly and sending MCP protocol messages via stdin/stdout.

## Architecture

```
MCP Client (Cursor/Claude/etc.)
    ↓ (stdio)
MCP Server (mcp_server.py)
    ↓ (HTTP REST API)
Flask App (app.py)
    ↓
SQLite Database + RAG Service
```

## Features

✅ **Resources**: All regulations exposed as MCP resources  
✅ **Semantic Search**: RAG-powered search via `search_regulations` tool  
✅ **Q&A**: Natural language questions via `ask_regulation_question` tool  
✅ **Change Monitoring**: Get recent changes via `get_recent_changes` tool  
✅ **Statistics**: Database stats via `get_regulation_stats` tool  
✅ **Direct Access**: Get regulations by ID via `get_regulation_by_id` tool  

## Error Handling

The server handles errors gracefully:
- API connection failures return error messages
- Invalid parameters return validation errors
- Missing regulations return 404-style errors

All errors are returned as JSON in the tool response.

## Future Enhancements

- [ ] Add tool for refreshing regulations
- [ ] Add tool for filtering regulations by status
- [ ] Add tool for batch operations
- [ ] Support SSE transport for web-based clients
- [ ] Add authentication/authorization

