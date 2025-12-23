"""
Robust Regulation Scraper with Multiple Fallback Strategies
Handles URL changes and website structure updates gracefully
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobustRegulationScraper:
    """
    Robust scraper with multiple strategies and fallback mechanisms
    """
    
    BASE_URL = "https://www.ecfr.gov/current/title-21"
    API_BASE_URL = "https://www.ecfr.gov/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.last_successful_urls = {}  # Cache successful URLs
        self.failed_attempts = {}  # Track failures
        
    def fetch_with_retry(self, url: str, max_retries: int = 3, timeout: int = 30) -> Optional[requests.Response]:
        """Fetch URL with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code == 200:
                    self.last_successful_urls[url] = datetime.now()
                    if url in self.failed_attempts:
                        del self.failed_attempts[url]
                    return response
                elif response.status_code == 404:
                    logger.warning(f"URL not found (404): {url}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                self.failed_attempts[url] = self.failed_attempts.get(url, 0) + 1
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def try_api_endpoint(self, title: int = 21) -> List[Dict]:
        """Try to use eCFR API if available"""
        try:
            # eCFR has an API - try to use it
            api_url = f"{self.API_BASE_URL}/titles/{title}"
            response = self.fetch_with_retry(api_url)
            
            if response:
                try:
                    data = response.json()
                    # Parse API response
                    regulations = []
                    # API structure may vary, adapt as needed
                    if 'chapters' in data:
                        for chapter in data['chapters']:
                            regulations.extend(self._parse_api_chapter(chapter))
                    return regulations
                except Exception as e:
                    logger.warning(f"API response parsing failed: {e}")
        except Exception as e:
            logger.info(f"API endpoint not available: {e}")
        
        return []
    
    def _parse_api_chapter(self, chapter_data: Dict) -> List[Dict]:
        """Parse chapter data from API response"""
        regulations = []
        # Adapt based on actual API structure
        # This is a placeholder for API parsing logic
        return regulations
    
    def fetch_with_multiple_strategies(self) -> List[Dict]:
        """
        Try multiple strategies to fetch regulations:
        1. Official API (if available)
        2. Current URL structure
        3. Alternative URL patterns
        4. Cached successful URLs
        """
        regulations = []
        
        # Strategy 1: Try official API
        logger.info("Attempting to fetch via API...")
        api_regs = self.try_api_endpoint()
        if api_regs:
            logger.info(f"Successfully fetched {len(api_regs)} regulations via API")
            return api_regs
        
        # Strategy 2: Try current URL structure
        logger.info("Attempting to fetch via current URL structure...")
        response = self.fetch_with_retry(self.BASE_URL)
        if response:
            regulations = self._parse_html_structure(response.content)
            if regulations:
                logger.info(f"Successfully fetched {len(regulations)} regulations via HTML")
                return regulations
        
        # Strategy 3: Try alternative URL patterns
        logger.info("Attempting alternative URL patterns...")
        alt_urls = [
            "https://www.ecfr.gov/api/title/21",
            "https://www.ecfr.gov/current/title-21/chapter-I",
            "https://www.ecfr.gov/api/v1/title/21"
        ]
        
        for alt_url in alt_urls:
            response = self.fetch_with_retry(alt_url)
            if response:
                parsed = self._parse_html_structure(response.content) if response.headers.get('content-type', '').startswith('text/html') else []
                if parsed:
                    logger.info(f"Successfully fetched via alternative URL: {alt_url}")
                    return parsed
        
        # Strategy 4: Use cached URLs if available
        if self.last_successful_urls:
            logger.info("Attempting to use cached successful URLs...")
            for cached_url, last_success in self.last_successful_urls.items():
                # Only use if cached recently (within 7 days)
                if (datetime.now() - last_success).days < 7:
                    response = self.fetch_with_retry(cached_url)
                    if response:
                        parsed = self._parse_html_structure(response.content)
                        if parsed:
                            return parsed
        
        logger.warning("All fetching strategies failed")
        return []
    
    def _parse_html_structure(self, html_content: bytes) -> List[Dict]:
        """Parse HTML structure - adapts to different HTML structures"""
        regulations = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try multiple selectors to find regulation tables
            selectors = [
                'table',
                '.regulation-table',
                '#regulations-table',
                '[class*="regulation"]',
                '[id*="regulation"]'
            ]
            
            table = None
            for selector in selectors:
                table = soup.select_one(selector)
                if table:
                    logger.info(f"Found table using selector: {selector}")
                    break
            
            if not table:
                # Try finding any table with regulation-like content
                tables = soup.find_all('table')
                for t in tables:
                    text = t.get_text().lower()
                    if any(keyword in text for keyword in ['part', 'chapter', 'section', 'regulation']):
                        table = t
                        break
            
            if table:
                regulations = self._extract_regulations_from_table(table)
            
        except Exception as e:
            logger.error(f"HTML parsing error: {e}")
        
        return regulations
    
    def _extract_regulations_from_table(self, table) -> List[Dict]:
        """Extract regulations from table - handles various table structures"""
        regulations = []
        current_chapter = None
        current_subchapter = None
        
        try:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # Try to extract regulation data
                    reg_data = self._parse_table_row(cells, current_chapter, current_subchapter)
                    if reg_data:
                        # Update current chapter/subchapter for next rows
                        if reg_data.get('chapter'):
                            current_chapter = reg_data['chapter']
                        if reg_data.get('subchapter'):
                            current_subchapter = reg_data['subchapter']
                        regulations.append(reg_data)
        except Exception as e:
            logger.error(f"Table extraction error: {e}")
        
        return regulations
    
    def _parse_table_row(self, cells, parent_chapter=None, parent_subchapter=None) -> Optional[Dict]:
        """Parse a table row - flexible parsing, returns proper structure"""
        try:
            # Look for links (usually contain regulation info)
            links = []
            for cell in cells:
                cell_links = cell.find_all('a')
                links.extend(cell_links)
            
            if links:
                first_link = links[0]
                text = first_link.get_text(strip=True)
                href = first_link.get('href', '')
                url = self._normalize_url(href)
                desc = cells[1].get_text(strip=True) if len(cells) > 1 else text
                section_range = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                
                # Determine if it's a chapter, subchapter, or part
                if 'chapter' in text.lower() and 'subchapter' not in text.lower():
                    return {
                        'title': 'Title 21',
                        'chapter': text,
                        'subchapter': '',
                        'part': '',
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': 'Requires Compliance',
                        'status_reason': 'Administrative structure'
                    }
                elif 'subchapter' in text.lower():
                    return {
                        'title': 'Title 21',
                        'chapter': parent_chapter or '',
                        'subchapter': text,
                        'part': '',
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': 'Requires Compliance',
                        'status_reason': 'Administrative structure'
                    }
                elif text.lower().startswith('part '):
                    return {
                        'title': 'Title 21',
                        'chapter': parent_chapter or '',
                        'subchapter': parent_subchapter or '',
                        'part': text,
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': 'Requires Compliance',
                        'status_reason': 'Regulatory provision'
                    }
        except Exception as e:
            logger.debug(f"Row parsing error: {e}")
        
        return None
    
    def _normalize_url(self, href: str) -> str:
        """Normalize URLs to handle different formats"""
        if not href:
            return ''
        
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f"https://www.ecfr.gov{href}"
        else:
            return f"https://www.ecfr.gov/{href}"
    
    def health_check(self) -> Dict:
        """Check health of scraper and URLs"""
        health = {
            'status': 'healthy',
            'base_url_accessible': False,
            'api_available': False,
            'cached_urls_count': len(self.last_successful_urls),
            'failed_urls_count': len(self.failed_attempts),
            'last_success': None
        }
        
        # Check base URL
        response = self.fetch_with_retry(self.BASE_URL, max_retries=1, timeout=5)
        health['base_url_accessible'] = response is not None
        
        # Check API
        try:
            api_response = self.session.get(f"{self.API_BASE_URL}/health", timeout=5)
            health['api_available'] = api_response.status_code == 200
        except Exception:
            pass
        
        if self.last_successful_urls:
            health['last_success'] = max(self.last_successful_urls.values()).isoformat()
        
        if not health['base_url_accessible'] and not health['api_available']:
            health['status'] = 'degraded'
        
        return health

