# RAG Setup Guide

## Overview

RAG (Retrieval-Augmented Generation) has been implemented to provide semantic search and improved Q&A accuracy for the regulations application.

## Features

1. **Semantic Search**: Finds regulations by meaning, not just keywords
2. **Hybrid Search**: Combines semantic and keyword search for best results
3. **Improved Q&A**: LLM gets better context from semantically relevant regulations
4. **Vector Database**: Uses ChromaDB for efficient similarity search

## Installation

1. **Install dependencies**:
```bash
source venv/bin/activate
pip install chromadb sentence-transformers numpy
```

2. **Initialize RAG** (after regulations are loaded):
```bash
python initialize_rag.py
```

Or use the API endpoint:
```bash
curl -X POST http://localhost:5000/api/rag/index
```

## Usage

### Search with RAG

The search endpoint now uses RAG by default:

```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "medical device approval", "use_rag": true}'
```

### Q&A with RAG

The LLM Q&A endpoint uses RAG for better context:

```bash
curl -X POST http://localhost:5000/api/llm/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the requirements for importing prescription drugs?", "use_rag": true}'
```

### Check RAG Status

```bash
curl http://localhost:5000/api/rag/stats
```

## How It Works

1. **Indexing**: Regulations are converted to embeddings and stored in ChromaDB
2. **Search**: Query is converted to embedding and compared with regulation embeddings
3. **Retrieval**: Most semantically similar regulations are retrieved
4. **Hybrid**: Combines semantic results with keyword results for best accuracy
5. **LLM Context**: Retrieved regulations provide context for LLM answers

## Benefits

- ✅ Finds regulations even with different terminology
- ✅ Better Q&A accuracy with relevant context
- ✅ Handles complex queries across multiple regulations
- ✅ More relevant search results

## Re-indexing

After refreshing regulations data, re-index:

```bash
python initialize_rag.py
```

Or use the API:
```bash
curl -X POST http://localhost:5000/api/rag/index
```

## Troubleshooting

**RAG not working?**
- Check if indexed: `curl http://localhost:5000/api/rag/stats`
- Re-index if needed: `python initialize_rag.py`

**Slow indexing?**
- Normal for first-time indexing (may take a few minutes)
- Subsequent re-indexing is faster

**Memory issues?**
- ChromaDB stores data on disk, minimal memory usage
- Sentence transformers model loads into memory (~100MB)

