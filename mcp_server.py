"""
MCP (Model Context Protocol) Server for Regulations
Exposes regulations as resources and provides tools for search and analysis
"""

import os
import json
import sys
import asyncio
from typing import Any, Sequence
import requests

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
    from mcp.server.models import InitializationOptions
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install 'mcp[cli]'")
    sys.exit(1)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")

# Initialize MCP Server
server = Server("regulations-mcp-server")


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List all regulations as MCP resources"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/regulations",
            params={"include_administrative": "true", "include_reserved": "true"},
            timeout=10
        )
        response.raise_for_status()
        regulations = response.json()
        
        resources = []
        for reg in regulations:
            # Create a descriptive name
            name_parts = []
            if reg.get('part'):
                name_parts.append(reg['part'])
            if reg.get('chapter'):
                name_parts.append(f"Chapter {reg['chapter']}")
            if reg.get('subchapter'):
                name_parts.append(f"Subchapter {reg['subchapter']}")
            
            name = " - ".join(name_parts) if name_parts else f"Regulation {reg['id']}"
            
            # Create description
            description = reg.get('description', '')[:200]  # Truncate for display
            if reg.get('status'):
                description = f"[{reg['status']}] {description}"
            
            resources.append(Resource(
                uri=f"regulation://{reg['id']}",
                name=name,
                description=description,
                mimeType="application/json"
            ))
        
        return resources
    except Exception as e:
        print(f"Error listing resources: {e}", file=sys.stderr)
        return []


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Get a specific regulation resource by URI"""
    try:
        # Parse regulation ID from URI (format: regulation://123)
        if not uri.startswith("regulation://"):
            raise ValueError(f"Invalid URI format: {uri}")
        
        reg_id = uri.replace("regulation://", "")
        
        response = requests.get(
            f"{API_BASE_URL}/api/regulations/{reg_id}",
            timeout=10
        )
        response.raise_for_status()
        regulation = response.json()
        
        # Return formatted JSON
        return json.dumps(regulation, indent=2)
    except Exception as e:
        error_msg = json.dumps({"error": str(e), "uri": uri})
        print(f"Error reading resource: {e}", file=sys.stderr)
        return error_msg


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_regulations",
            description="Search Title 21 FDA regulations using semantic search (RAG). Returns regulations matching the query by meaning, not just keywords.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'medical device approval', 'drug import requirements')"
                    },
                    "use_rag": {
                        "type": "boolean",
                        "description": "Use RAG semantic search (default: true)",
                        "default": True
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="ask_regulation_question",
            description="Ask a natural language question about FDA Title 21 regulations. Uses RAG to find relevant regulations and LLM to provide an answer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question about regulations (e.g., 'What are the requirements for importing prescription drugs?')"
                    },
                    "use_rag": {
                        "type": "boolean",
                        "description": "Use RAG for better context retrieval (default: true)",
                        "default": True
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="get_regulation_by_id",
            description="Get a specific regulation by its database ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "regulation_id": {
                        "type": "integer",
                        "description": "The ID of the regulation to retrieve"
                    }
                },
                "required": ["regulation_id"]
            }
        ),
        Tool(
            name="get_recent_changes",
            description="Get recently updated regulations with change details",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of changes to return",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_regulation_stats",
            description="Get statistics about regulations in the database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute an MCP tool"""
    try:
        if name == "search_regulations":
            query = arguments.get("query")
            if not query:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Query is required"}, indent=2)
                )]
            
            use_rag = arguments.get("use_rag", True)
            limit = arguments.get("limit", 20)
            
            response = requests.post(
                f"{API_BASE_URL}/api/search",
                json={"query": query, "use_rag": use_rag},
                timeout=30
            )
            response.raise_for_status()
            results = response.json()
            
            # Format results
            if isinstance(results, dict) and "results" in results:
                results_list = results["results"][:limit]
                count = results.get("count", len(results_list))
                search_method = results.get("search_method", "unknown")
                
                formatted = {
                    "query": query,
                    "count": count,
                    "search_method": search_method,
                    "results": results_list
                }
            else:
                formatted = results
            
            return [TextContent(
                type="text",
                text=json.dumps(formatted, indent=2)
            )]
        
        elif name == "ask_regulation_question":
            question = arguments.get("question")
            if not question:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Question is required"}, indent=2)
                )]
            
            use_rag = arguments.get("use_rag", True)
            
            response = requests.post(
                f"{API_BASE_URL}/api/llm/ask",
                json={"question": question, "use_rag": use_rag},
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "get_regulation_by_id":
            regulation_id = arguments.get("regulation_id")
            if not regulation_id:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "regulation_id is required"}, indent=2)
                )]
            
            response = requests.get(
                f"{API_BASE_URL}/api/regulations/{regulation_id}",
                timeout=10
            )
            response.raise_for_status()
            regulation = response.json()
            
            return [TextContent(
                type="text",
                text=json.dumps(regulation, indent=2)
            )]
        
        elif name == "get_recent_changes":
            limit = arguments.get("limit", 10)
            
            response = requests.get(
                f"{API_BASE_URL}/api/changes",
                params={"limit": limit},
                timeout=10
            )
            response.raise_for_status()
            changes = response.json()
            
            return [TextContent(
                type="text",
                text=json.dumps(changes, indent=2)
            )]
        
        elif name == "get_regulation_stats":
            response = requests.get(
                f"{API_BASE_URL}/api/stats",
                timeout=10
            )
            response.raise_for_status()
            stats = response.json()
            
            return [TextContent(
                type="text",
                text=json.dumps(stats, indent=2)
            )]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2)
            )]
    
    except requests.exceptions.RequestException as e:
        error_msg = {
            "error": f"API request failed: {str(e)}",
            "tool": name,
            "arguments": arguments
        }
        return [TextContent(
            type="text",
            text=json.dumps(error_msg, indent=2)
        )]
    except Exception as e:
        error_msg = {
            "error": str(e),
            "tool": name,
            "arguments": arguments
        }
        print(f"Error calling tool {name}: {e}", file=sys.stderr)
        return [TextContent(
            type="text",
            text=json.dumps(error_msg, indent=2)
        )]


async def main():
    """Run the MCP server using stdio transport"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="regulations-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None
                )
            )
        )


if __name__ == "__main__":
    print("Starting Regulations MCP Server...", file=sys.stderr)
    print(f"API Base URL: {API_BASE_URL}", file=sys.stderr)
    print("Waiting for MCP client connection...", file=sys.stderr)
    asyncio.run(main())

