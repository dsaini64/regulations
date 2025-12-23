# Quick Start Guide

## 🚀 Getting Started in 3 Steps

1. **Start the server**:
   ```bash
   ./run.sh
   ```

2. **Open your browser**:
   ```
   http://localhost:5000
   ```

3. **Start searching**:
   - Enter a search term (e.g., "medical devices")
   - Click "Search" or press Enter
   - View results in the table

## 📋 Key Features

- **Search**: Search regulations by keyword
- **Refresh**: Update data from eCFR website
- **Statistics**: View total regulations, chapters, and searches
- **Agent Workflow**: Use `agent_workflow.py` for programmatic access
- **MCP Integration**: See `mcp_integration.md` for MCP setup

## 🔍 Example Searches

Try these example searches:
- "medical devices"
- "drug approval"
- "food labeling"
- "biologics"
- "cosmetics"

## 🤖 Using the Agent Workflow

```python
from agent_workflow import RegulationAgentWorkflow

agent = RegulationAgentWorkflow()
result = agent.analyze("medical devices")
print(result['summary'])
```

## 📊 API Endpoints

- `GET /api/regulations` - Get all regulations
- `POST /api/search` - Search regulations
- `POST /api/refresh` - Refresh from eCFR
- `GET /api/stats` - Get statistics

## 💡 Tips

- The database is created automatically on first run
- Use "Refresh Data" to update regulations from eCFR
- Search is case-insensitive
- Results are cached in SQLite for fast searches

