# LLM Integration Setup Guide

This guide explains how to set up and use ChatGPT/OpenAI integration for enhanced regulation analysis.

## Setup

1. **Get OpenAI API Key**:
   - Sign up at https://platform.openai.com/
   - Navigate to https://platform.openai.com/api-keys
   - Create a new API key

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key:
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

3. **Install Dependencies** (if not already installed):
   ```bash
   pip install openai python-dotenv
   ```

4. **Restart the Application**:
   ```bash
   python app.py
   ```

## Features Enabled with LLM

### 1. Enhanced Status Analysis
- **Before**: Simple keyword matching
- **After**: LLM analyzes regulation content to determine if something is Allowed/Prohibited with better accuracy
- **Usage**: Automatically applied when regulations are loaded/refreshed

### 2. Question Answering
Ask natural language questions about regulations:

```bash
curl -X POST http://localhost:5000/api/llm/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the requirements for medical device labeling?"}'
```

**Response**:
```json
{
  "answer": "Medical device labeling requirements are specified in Part 801...",
  "references": ["Part 801", "Section 801.1"],
  "relevant_regulations": [...],
  "confidence": "high"
}
```

### 3. Regulation Summaries
Get AI-generated summaries of regulations:

```bash
curl -X POST http://localhost:5000/api/llm/summarize \
  -H "Content-Type: application/json" \
  -d '{"regulation_id": 1}'
```

**Response**:
```json
{
  "regulation_id": 1,
  "summary": "This regulation establishes general provisions...",
  "original_description": "..."
}
```

## API Endpoints

### POST `/api/llm/ask`
Ask a question about regulations.

**Request**:
```json
{
  "question": "What are the labeling requirements for food products?"
}
```

**Response**:
```json
{
  "answer": "...",
  "references": ["Part 101", "Section 101.9"],
  "relevant_regulations": [...],
  "confidence": "high"
}
```

### POST `/api/llm/summarize`
Get an LLM-generated summary of a specific regulation.

**Request**:
```json
{
  "regulation_id": 1
}
```

**Response**:
```json
{
  "regulation_id": 1,
  "summary": "...",
  "original_description": "..."
}
```

## Fallback Behavior

If LLM is not configured:
- Status analysis falls back to keyword matching
- Question answering returns an error message
- Summarization returns the original description

## Cost Considerations

- Uses `gpt-4o-mini` model for cost efficiency
- Each status analysis: ~150 tokens
- Each question: ~500 tokens
- Each summary: ~200 tokens

**Estimated costs** (as of 2024):
- Status analysis: ~$0.0001 per regulation
- Question: ~$0.0003 per question
- Summary: ~$0.0001 per summary

## Best Practices

1. **Cache Results**: The system caches regulation status in the database
2. **Batch Processing**: Status analysis is done during refresh, not on-demand
3. **Error Handling**: System gracefully falls back if LLM fails
4. **Rate Limiting**: Consider implementing rate limiting for production use

## Troubleshooting

**Issue**: "LLM service not available"
- **Solution**: Check that `.env` file exists and contains `OPENAI_API_KEY`

**Issue**: "LLM analysis failed"
- **Solution**: Check API key validity and account balance

**Issue**: Slow responses
- **Solution**: LLM calls add ~1-2 seconds. Consider caching frequently asked questions.

