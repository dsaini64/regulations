# Title 21 Regulations Search System

A comprehensive workflow system for searching and displaying Title 21 (Food and Drugs) regulations from the Electronic Code of Federal Regulations (eCFR).

## Features

- 🔍 **Intelligent Search**: Search regulations by keywords, parts, chapters, or descriptions
- 🤖 **Agent Workflow**: Automated agent system for processing regulation queries
- 📊 **Summary Table**: Beautiful GUI with a comprehensive table summarizing all regulations
- 🔄 **Auto-Refresh**: Ability to refresh regulation data from the eCFR website
- 💾 **Database Caching**: SQLite database for fast local searches
- 📈 **Statistics Dashboard**: Real-time statistics about regulations and searches

## LLM Integration (ChatGPT/OpenAI)

The system supports LLM integration for enhanced regulation analysis:

1. **Get OpenAI API Key**: Sign up at https://platform.openai.com/api-keys
2. **Create `.env` file**: Copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   # Edit .env and add: OPENAI_API_KEY=your_key_here
   ```
3. **Features enabled with LLM**:
   - More accurate status analysis (Allowed/Prohibited)
   - Natural language question answering about regulations
   - Enhanced regulation summaries
   - Better extraction of key requirements

**Note**: The system works without LLM (using keyword matching), but LLM provides much better accuracy and insights.

## Installation

### Quick Start (Recommended)

Use the provided startup script:

```bash
./run.sh
```

This will:
- Create a virtual environment (if needed)
- Install all dependencies
- Start the Flask server
- Open the application at http://localhost:5000

### Manual Installation

1. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

### Searching Regulations

1. Enter a search term in the search box (e.g., "medical devices", "drugs", "food")
2. Click "Search" or press Enter
3. View results in the table below

### Refreshing Data

Click the "Refresh Data" button to fetch the latest regulations from the eCFR website. This process runs in the background.

### API Endpoints

- `GET /api/regulations` - Get all regulations
- `POST /api/search` - Search regulations
  ```json
  {
    "query": "medical devices"
  }
  ```
- `POST /api/refresh` - Refresh regulations from eCFR
- `GET /api/stats` - Get statistics

## Architecture

### Components

1. **RegulationScraper**: Fetches and parses regulations from eCFR website
2. **RegulationAgent**: Processes queries and generates summaries
3. **Flask API**: RESTful API for frontend communication
4. **SQLite Database**: Local caching of regulations
5. **Web GUI**: Modern, responsive interface

### Database Schema

**regulations** table:
- id, title, chapter, subchapter, part, section_range
- description, url, last_updated, content_summary, created_at

**search_history** table:
- id, query, results_count, created_at

## Agent Workflow System

The system includes a comprehensive agent workflow (`agent_workflow.py`) that provides:

- **Intelligent Search**: Multi-step search and analysis
- **Categorization**: Automatic categorization by chapter and subchapter
- **Comprehensive Summaries**: Detailed analysis of search results
- **Batch Processing**: Process multiple queries at once
- **Recommendations**: AI-powered recommendations for related searches

### Using the Agent Workflow

```python
from agent_workflow import RegulationAgentWorkflow

# Initialize agent
agent = RegulationAgentWorkflow()

# Simple search
results = agent.search("medical devices")

# Comprehensive analysis
analysis = agent.analyze("drug approval", context="FDA submission")

# Batch processing
queries = ["medical devices", "food labeling", "drugs"]
batch_results = agent.batch_search(queries)

# Get recommendations
recommendations = agent.get_recommendations("medical devices")
```

## MCP Integration ✅

**MCP (Model Context Protocol) is fully implemented!** The system exposes:

1. **Resources**: All regulations exposed as MCP resources (`regulation://{id}`)
2. **Tools**: 5 MCP tools for search, Q&A, and monitoring
3. **Standardized Interface**: Works with Cursor, Claude Desktop, and other MCP clients
4. **RAG-Powered**: Tools use semantic search for better results

### Quick Start

1. **Install MCP SDK**:
   ```bash
   pip install 'mcp[cli]'
   ```

2. **Start Flask app** (Terminal 1):
   ```bash
   python app.py
   ```

3. **Start MCP server** (Terminal 2):
   ```bash
   # Using FastMCP (recommended, simpler)
   python mcp_server_fast.py
   
   # Or using standard MCP Server
   python mcp_server.py
   ```

4. **Configure MCP client** (Cursor/Claude Desktop):
   ```json
   {
     "mcpServers": {
       "regulations": {
         "command": "python",
         "args": ["/path/to/regulations/mcp_server_fast.py"],
         "env": {
           "API_BASE_URL": "http://localhost:5000"
         }
       }
     }
   }
   ```

### Available MCP Tools

- `search_regulations`: Semantic search with RAG
- `ask_regulation_question`: Natural language Q&A
- `get_regulation_by_id`: Get specific regulation
- `get_recent_changes`: Monitor regulation updates
- `get_regulation_stats`: Database statistics

See `MCP_IMPLEMENTATION.md` for detailed documentation.

## Notes

- The eCFR website may require IP whitelisting for programmatic access
- Regulations are cached locally for faster searches
- The scraper respects the website's structure and extracts hierarchical data
- Search is case-insensitive and searches across multiple fields

## License

MIT License

