# URL Change Monitoring & Robustness

This document explains how the system handles URL changes and maintains robustness.

## Problem Statement

If the eCFR website structure changes (URLs, HTML structure, API endpoints), the scraper could break. This system implements multiple strategies to handle such changes.

## Robustness Strategies

### 1. **Multiple URL Fallbacks**
- Primary URL: `https://www.ecfr.gov/current/title-21`
- Alternative URLs:
  - `https://www.ecfr.gov/api/title/21` (API endpoint)
  - `https://www.ecfr.gov/current/title-21/chapter-I` (Direct chapter access)

### 2. **Multiple Parsing Strategies**
- **HTML Tables**: Primary method - looks for `<table>` elements
- **Link Extraction**: Fallback - extracts regulations from links if tables not found
- **JSON API**: If available, uses structured API responses
- **Flexible Selectors**: Tries multiple CSS selectors to find regulation data

### 3. **Error Handling & Retry Logic**
- Automatic retries with exponential backoff
- Tracks successful URLs for caching
- Graceful degradation to sample data if all methods fail

### 4. **Health Monitoring**
- `/api/health` endpoint checks:
  - Base URL accessibility
  - API availability
  - Cached URL status
  - Last successful fetch time

### 5. **URL Caching**
- Stores successful URLs
- Reuses cached URLs if primary fails
- Cache expires after 7 days

## Monitoring & Alerts

### Health Check Endpoint
```bash
curl http://localhost:5000/api/health
```

Response:
```json
{
  "status": "healthy",
  "base_url_accessible": true,
  "api_available": false,
  "cached_urls_count": 5,
  "failed_urls_count": 0,
  "last_success": "2024-12-16T12:00:00"
}
```

### Status Values
- `healthy`: All systems operational
- `degraded`: Some URLs failing but fallbacks working
- `error`: Critical failure

## Handling URL Changes

### If Primary URL Changes:
1. System automatically tries alternative URLs
2. If alternatives work, updates `last_successful_url`
3. Continues using working URL

### If HTML Structure Changes:
1. Tries multiple parsing strategies
2. Falls back to link extraction
3. Logs parsing failures for debugging

### If All Methods Fail:
1. Uses cached sample data
2. Logs error for administrator review
3. System continues operating with limited data

## Manual URL Updates

If URLs change permanently, update in `app.py`:

```python
BASE_URL = "https://www.ecfr.gov/new-url/title-21"
ALTERNATIVE_URLS = [
    "https://www.ecfr.gov/new-api/title/21",
    # Add new alternatives
]
```

## Best Practices

1. **Regular Health Checks**: Monitor `/api/health` endpoint
2. **Log Monitoring**: Watch for parsing errors
3. **Sample Data**: Keep sample data updated as fallback
4. **API Preference**: If eCFR provides official API, prefer it over scraping
5. **Version Tracking**: Track eCFR website versions/changes

## Future Improvements

- [ ] Automatic URL discovery
- [ ] Machine learning for structure detection
- [ ] Webhook notifications for URL failures
- [ ] Integration with eCFR change notifications
- [ ] Automated testing of URL accessibility

