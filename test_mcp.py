"""
Test script for MCP server
Tests the MCP server functionality by simulating tool calls
"""

import requests
import json
import sys

API_BASE_URL = "http://localhost:5000"

def test_api_endpoints():
    """Test that Flask API endpoints are working"""
    print("Testing Flask API endpoints...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=5)
        print(f"✅ Health check: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test regulations endpoint
    try:
        response = requests.get(f"{API_BASE_URL}/api/regulations?limit=5", timeout=5)
        regulations = response.json()
        print(f"✅ Regulations endpoint: {len(regulations)} regulations")
        if len(regulations) > 0:
            print(f"   Sample regulation ID: {regulations[0].get('id')}")
    except Exception as e:
        print(f"❌ Regulations endpoint failed: {e}")
        return False
    
    # Test search endpoint
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/search",
            json={"query": "medical devices", "use_rag": False},
            timeout=10
        )
        results = response.json()
        print(f"✅ Search endpoint: {results.get('count', 0)} results")
    except Exception as e:
        print(f"❌ Search endpoint failed: {e}")
        return False
    
    # Test stats endpoint
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats", timeout=5)
        stats = response.json()
        print(f"✅ Stats endpoint: {stats.get('total_regulations', 0)} total regulations")
    except Exception as e:
        print(f"❌ Stats endpoint failed: {e}")
        return False
    
    return True

def test_mcp_tool_logic():
    """Test the logic that MCP tools would use"""
    print("\nTesting MCP tool logic...")
    
    # Simulate search_regulations tool
    print("\n1. Testing search_regulations logic:")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/search",
            json={"query": "drug approval", "use_rag": True},
            timeout=30
        )
        results = response.json()
        print(f"   ✅ Found {results.get('count', 0)} results")
        print(f"   Search method: {results.get('search_method', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Simulate ask_regulation_question tool
    print("\n2. Testing ask_regulation_question logic:")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/llm/ask",
            json={"question": "What are medical devices?", "use_rag": True},
            timeout=60
        )
        result = response.json()
        if 'answer' in result:
            print(f"   ✅ Got answer: {result['answer'][:100]}...")
        else:
            print(f"   ⚠️  Response: {json.dumps(result, indent=2)[:200]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Simulate get_regulation_by_id tool
    print("\n3. Testing get_regulation_by_id logic:")
    try:
        # First get a regulation ID
        response = requests.get(f"{API_BASE_URL}/api/regulations?limit=1", timeout=5)
        regulations = response.json()
        if regulations:
            reg_id = regulations[0]['id']
            response = requests.get(f"{API_BASE_URL}/api/regulations/{reg_id}", timeout=5)
            regulation = response.json()
            print(f"   ✅ Retrieved regulation {reg_id}: {regulation.get('part', 'N/A')}")
        else:
            print("   ⚠️  No regulations found to test")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Simulate get_recent_changes tool
    print("\n4. Testing get_recent_changes logic:")
    try:
        response = requests.get(f"{API_BASE_URL}/api/changes?limit=5", timeout=5)
        changes = response.json()
        print(f"   ✅ Found {len(changes.get('changes', []))} recent changes")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Simulate get_regulation_stats tool
    print("\n5. Testing get_regulation_stats logic:")
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats", timeout=5)
        stats = response.json()
        print(f"   ✅ Stats retrieved:")
        print(f"      Total regulations: {stats.get('total_regulations', 0)}")
        print(f"      By status: {stats.get('by_status', {})}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def main():
    print("=" * 60)
    print("MCP Server Test Suite")
    print("=" * 60)
    print(f"\nTesting against API: {API_BASE_URL}")
    print("Make sure Flask app is running!\n")
    
    # Test API endpoints
    if not test_api_endpoints():
        print("\n❌ API tests failed. Make sure Flask app is running.")
        sys.exit(1)
    
    # Test MCP tool logic
    test_mcp_tool_logic()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\nTo test the actual MCP server:")
    print("1. Make sure Flask app is running: python app.py")
    print("2. Run MCP server: python mcp_server.py")
    print("3. Use MCP Inspector: npx -y @modelcontextprotocol/inspector")

if __name__ == "__main__":
    main()

