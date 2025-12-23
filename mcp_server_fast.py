"""
MCP Server using FastMCP (Simpler API)
Alternative implementation using FastMCP for easier setup
"""

import os
import json
import sys
import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install 'mcp[cli]'")
    sys.exit(1)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")

# Initialize FastMCP Server
mcp = FastMCP("Regulations MCP Server")


@mcp.resource("regulation://{regulation_id}")
def get_regulation_resource(regulation_id: str) -> str:
    """Get a regulation as a resource"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/regulations/{regulation_id}",
            timeout=10
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "regulation_id": regulation_id})


@mcp.tool()
def search_regulations(query: str, use_rag: bool = True, limit: int = 20) -> str:
    """
    Search Title 21 FDA regulations using semantic search (RAG).
    
    Args:
        query: Search query (e.g., 'medical device approval', 'drug import requirements')
        use_rag: Use RAG semantic search (default: true)
        limit: Maximum number of results to return (default: 20)
    
    Returns:
        JSON string with search results
    """
    try:
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
            formatted = {
                "query": query,
                "count": results.get("count", len(results_list)),
                "search_method": results.get("search_method", "unknown"),
                "results": results_list
            }
        else:
            formatted = results
        
        return json.dumps(formatted, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


@mcp.tool()
def ask_regulation_question(question: str, use_rag: bool = True) -> str:
    """
    Ask a natural language question about FDA Title 21 regulations.
    Uses RAG to find relevant regulations and LLM to provide an answer.
    
    Args:
        question: Question about regulations (e.g., 'What are the requirements for importing prescription drugs?')
        use_rag: Use RAG for better context retrieval (default: true)
    
    Returns:
        JSON string with answer and relevant regulations
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/llm/ask",
            json={"question": question, "use_rag": use_rag},
            timeout=60
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "question": question})


@mcp.tool()
def get_regulation_by_id(regulation_id: int) -> str:
    """
    Get a specific regulation by its database ID.
    
    Args:
        regulation_id: The ID of the regulation to retrieve
    
    Returns:
        JSON string with regulation data
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/regulations/{regulation_id}",
            timeout=10
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "regulation_id": regulation_id})


@mcp.tool()
def get_recent_changes(limit: int = 10) -> str:
    """
    Get recently updated regulations with change details.
    
    Args:
        limit: Maximum number of changes to return (default: 10)
    
    Returns:
        JSON string with recent changes
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/changes",
            params={"limit": limit},
            timeout=10
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_regulation_stats() -> str:
    """
    Get statistics about regulations in the database.
    
    Returns:
        JSON string with statistics
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/stats",
            timeout=10
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    print("Starting Regulations MCP Server (FastMCP)...", file=sys.stderr)
    print(f"API Base URL: {API_BASE_URL}", file=sys.stderr)
    print("Waiting for MCP client connection...", file=sys.stderr)
    mcp.run()

