"""
Regulation Search Workflow System
Main Flask application for searching and displaying Title 21 regulations
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
from typing import List, Dict
import threading
from llm_service import LLMRegulationAnalyzer
from rag_service import RAGService

app = Flask(__name__)
CORS(app)

# Database setup
DB_NAME = 'regulations.db'

def init_db():
    """Initialize the database with regulations table"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS regulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            chapter TEXT,
            subchapter TEXT,
            part TEXT,
            section_range TEXT,
            description TEXT,
            url TEXT,
            last_updated TIMESTAMP,
            content_summary TEXT,
            status TEXT,
            status_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            results_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS regulation_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regulation_id INTEGER,
            change_type TEXT,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified BOOLEAN DEFAULT 0,
            FOREIGN KEY (regulation_id) REFERENCES regulations(id)
        )
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_changes_detected ON regulation_changes(detected_at DESC)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_changes_notified ON regulation_changes(notified)
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

class RegulationScraper:
    """Scraper for eCFR Title 21 regulations with fallback mechanisms"""
    
    BASE_URL = "https://www.ecfr.gov/current/title-21"
    ALTERNATIVE_URLS = [
        "https://www.ecfr.gov/api/title/21",
        "https://www.ecfr.gov/current/title-21/chapter-I"
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        # Initialize LLM analyzer
        try:
            self.llm_analyzer = LLMRegulationAnalyzer()
        except Exception as e:
            print(f"Warning: Could not initialize LLM analyzer: {e}")
            self.llm_analyzer = None
        self.last_successful_url = None  # Track successful URLs
    
    def analyze_regulation_status(self, description: str, url: str = '', content: str = '') -> tuple:
        """
        Analyze regulation to determine if it's allowed or prohibited.
        Uses LLM if available, otherwise falls back to keyword matching.
        Returns (status, reason) tuple.
        """
        # Fetch content from URL if not provided and URL is available
        if not content and url and url.startswith('http'):
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "header", "footer"]):
                        script.decompose()
                    
                    # Try multiple strategies to find main content
                    main_content = None
                    
                    # Strategy 1: Look for content divs
                    content_divs = soup.find_all('div', class_=lambda x: x and any(
                        keyword in x.lower() for keyword in ['content', 'main', 'article', 'regulation', 'section']
                    ))
                    if content_divs:
                        main_content = max(content_divs, key=lambda x: len(x.get_text()))
                    
                    # Strategy 2: Look for main/article tags
                    if not main_content:
                        main_content = soup.find('main') or soup.find('article')
                    
                    # Strategy 3: Look for regulation-specific content
                    if not main_content:
                        reg_content = soup.find('div', id=lambda x: x and 'content' in x.lower())
                        if reg_content:
                            main_content = reg_content
                    
                    # Strategy 4: Use body but filter out navigation
                    if not main_content:
                        body = soup.find('body')
                        if body:
                            # Remove navigation elements
                            for nav in body.find_all(['nav', 'header', 'footer', 'aside']):
                                nav.decompose()
                            main_content = body
                    
                    if main_content:
                        # Get text content, prioritize first 8000 chars for better analysis
                        text_content = main_content.get_text(separator=' ', strip=True)
                        # Keep first 8000 chars but also try to get meaningful sections
                        content = text_content[:8000]
                        
                        # If content is very short, try to get more
                        if len(content) < 500:
                            # Try getting all paragraphs
                            paragraphs = soup.find_all('p')
                            para_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:20]])
                            if len(para_text) > len(content):
                                content = para_text[:8000]
            except Exception as e:
                print(f"Could not fetch content from {url}: {e}")
                content = ''
        
        # Combine description and content for analysis
        full_text = f"{description} {content}".strip().lower()
        
        # Try LLM first if available
        if self.llm_analyzer and self.llm_analyzer.enabled:
            try:
                result = self.llm_analyzer.analyze_regulation_status(description, url, content)
                if result[0] != 'Unknown':
                    return result
            except Exception as e:
                print(f"LLM analysis failed, using fallback: {e}")
        
        # Fallback to improved keyword matching
        description_lower = description.lower()
        full_text_lower = full_text
        
        # Keywords that suggest prohibition (more specific - avoid false positives)
        # Only use strong prohibition language, not general regulatory terms
        prohibited_keywords = [
            'prohibited', 'forbidden', 'not permitted', 'not allowed', 
            'banned', 'unlawful', 'illegal',
            'shall not', 'must not', 'may not', 'cannot', 'prohibits',
            'ban', 'outlaw', 'no person may', 'no person shall',
            'it is unlawful', 'it is illegal', 'prohibited from',
            'forbidden to', 'prohibition',
            'may not be', 'shall not be', 'must not be', 'cannot be'
        ]
        
        # Phrases that strongly indicate prohibition (check these separately)
        prohibited_phrases = [
            'shall not', 'must not', 'may not', 'cannot', 'no person may',
            'no person shall', 'it is unlawful', 'it is illegal',
            'prohibited from', 'forbidden to'
        ]
        
        # Keywords that suggest allowance
        allowed_keywords = [
            'permitted', 'allowed', 'authorized', 'approved', 'legal',
            'may', 'can', 'shall', 'must', 'requires', 'mandates',
            'regulation', 'provision', 'requirement', 'standard', 'guideline'
        ]
        
        # Check for explicit prohibition indicators FIRST (highest priority)
        # BUT: Be very conservative - regulatory language often uses "shall not" in non-prohibitive contexts
        # Only mark as prohibited if we have STRONG indicators in the DESCRIPTION (not content)
        
        # Check keywords in description only (more reliable than content)
        prohibited_in_desc = sum(1 for keyword in prohibited_keywords if keyword in description_lower)
        
        # Check for prohibition phrases, but ONLY in description to avoid false positives
        prohibited_phrase_in_desc = False
        for phrase in prohibited_phrases:
            if phrase in description_lower:
                prohibited_phrase_in_desc = True
                break
        
        # Only mark as prohibited if we have STRONG indicators in the DESCRIPTION
        # Require either: (1) a prohibition phrase in description, OR (2) multiple keywords in description
        if prohibited_phrase_in_desc:
            # Strong indicator - found a prohibition phrase in description
            return ('Prohibited', f'Regulation explicitly prohibits activities (prohibition phrase found in description)')
        elif prohibited_in_desc >= 2:
            # Multiple prohibition keywords in description
            return ('Prohibited', f'Contains {prohibited_in_desc} prohibition indicator(s) in description')
        # Don't mark as prohibited based on content alone (too many false positives from regulatory language)
        
        # Check for reserved sections
        if 'reserved' in full_text_lower:
            return ('Reserved', 'Regulation section is reserved for future use')
        
        # Check for explicit allowance indicators (in both description and content)
        allowed_in_desc = sum(1 for keyword in allowed_keywords if keyword in description_lower)
        allowed_in_content = sum(1 for keyword in allowed_keywords if keyword in full_text_lower)
        allowed_count = allowed_in_desc + allowed_in_content
        
        # Context-based analysis for common patterns
        # Administrative/general provisions - these are organizational, not regulatory
        if any(keyword in description_lower for keyword in ['chapter', 'subchapter']):
            if description_lower.strip() in ['chapter i', 'chapter ii', 'chapter iii', 'subchapter a', 'subchapter b', 'subchapter c', 'subchapter d', 'subchapter e', 'subchapter f', 'subchapter g', 'subchapter h', 'subchapter i', 'subchapter j', 'subchapter k', 'subchapter l']:
                return ('Administrative', 'Organizational structure')
        
        # Definitions and general provisions
        if any(keyword in description_lower for keyword in ['definition', 'definitions']):
            return ('Administrative', 'Definitions section')
        
        # Regulations that establish requirements (not prohibitions, but requirements to follow)
        # This is the MOST COMMON case - most regulations are requirements
        requirement_indicators = ['requirement', 'requirements', 'standard', 'standards', 'regulation', 'regulations', 
                                 'rule', 'rules', 'procedure', 'procedures', 'guideline', 'guidelines',
                                 'registration', 'labeling', 'approval', 'manufacturing', 'prescription',
                                 'record', 'records', 'report', 'reports', 'quota', 'quotas']
        
        if any(keyword in description_lower for keyword in requirement_indicators):
            return ('Requires Compliance', 'Establishes regulatory requirements that must be followed')
        
        # Food, drug, device regulations - these regulate but don't necessarily prohibit
        if any(keyword in description_lower for keyword in ['food', 'drug', 'device', 'controlled substance']):
            return ('Requires Compliance', 'Regulatory requirement for compliance')
        
        # If we have explicit allowance keywords, use them
        if allowed_count > 0:
            return ('Requires Compliance', f'Regulatory requirement ({allowed_count} compliance indicators found)')
        
        # If description is very short or just organizational, mark as administrative
        if len(description_lower.strip()) < 20 or description_lower.strip() in ['general', 'definitions']:
            return ('Administrative', 'Organizational structure')
        
        # Default: Most FDA regulations are requirements to follow, not prohibitions
        # Content analysis is NOT used for prohibition detection - too many false positives
        # Regulatory language often contains "shall not" in contexts that aren't prohibitions
        # Only the description is used for prohibition detection above
        
        return ('Requires Compliance', 'Regulatory provision')
    
    def fetch_title_21_structure(self) -> List[Dict]:
        """Fetch the structure of Title 21 regulations with fallback URLs"""
        # Try main URL first
        regulations = self._try_fetch_from_url(self.BASE_URL)
        if regulations:
            self.last_successful_url = self.BASE_URL
            return regulations
        
        # Try alternative URLs
        for alt_url in self.ALTERNATIVE_URLS:
            print(f"Trying alternative URL: {alt_url}")
            regulations = self._try_fetch_from_url(alt_url)
            if regulations:
                self.last_successful_url = alt_url
                print(f"Successfully fetched from alternative URL: {alt_url}")
                return regulations
        
        # If all URLs fail, return empty
        print("Warning: All URL attempts failed")
        return []
    
    def _try_fetch_from_url(self, url: str) -> List[Dict]:
        """Try to fetch regulations from a specific URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Check if it's HTML or JSON
            content_type = response.headers.get('content-type', '').lower()
            if 'json' in content_type:
                return self._parse_json_response(response.json())
            else:
                return self._parse_html_response(response.content)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from {url}: {e}")
            return []
        except Exception as e:
            print(f"Error parsing response from {url}: {e}")
            return []
    
    def _parse_json_response(self, json_data: Dict) -> List[Dict]:
        """Parse JSON API response if available"""
        regulations = []
        # Adapt based on actual API structure
        # This is a placeholder for JSON parsing
        return regulations
    
    def _parse_html_response(self, html_content: bytes) -> List[Dict]:
        """Parse HTML response"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            regulations = []
            
            # Find all tables (nested structure)
            tables = soup.find_all('table', recursive=True)
            if not tables:
                print("Warning: No tables found in HTML")
                return regulations
            
            # Use the main content table
            main_table = tables[0] if tables else None
            if not main_table:
                return regulations
            
            current_chapter = None
            current_subchapter = None
            
            def process_row(row, parent_chapter=None, parent_subchapter=None):
                """Recursively process table rows"""
                cells = row.find_all(['td', 'th'], recursive=False)
                if len(cells) < 2:
                    return parent_chapter, parent_subchapter
                
                first_cell = cells[0]
                first_text = first_cell.get_text(strip=True)
                link = first_cell.find('a')
                
                # Check for chapter
                if link and 'Chapter' in first_text:
                    chapter_text = link.get_text(strip=True)
                    desc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    section_range = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    href = link.get('href', '')
                    url = f"https://www.ecfr.gov{href}" if href.startswith('/') else href
                    
                    # Analyze status
                    status, status_reason = self.analyze_regulation_status(desc, url)
                    regulations.append({
                        'title': 'Title 21',
                        'chapter': chapter_text,
                        'subchapter': '',
                        'part': '',
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': status,
                        'status_reason': status_reason
                    })
                    return chapter_text, None
                
                # Check for subchapter
                if link and 'Subchapter' in first_text:
                    subchapter_text = link.get_text(strip=True)
                    desc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    section_range = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    href = link.get('href', '')
                    url = f"https://www.ecfr.gov{href}" if href.startswith('/') else href
                    
                    # Analyze status
                    status, status_reason = self.analyze_regulation_status(desc, url)
                    regulations.append({
                        'title': 'Title 21',
                        'chapter': parent_chapter or '',
                        'subchapter': subchapter_text,
                        'part': '',
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': status,
                        'status_reason': status_reason
                    })
                    
                    # IMPROVEMENT 1: Fetch parts from subchapter page
                    if url and len(regulations) < 500:  # Increased limit for more parts
                        try:
                            print(f"Fetching parts from subchapter: {subchapter_text} ({url})")
                            # Ensure we have chapter info - infer from subchapter if missing
                            chapter_for_subchapter = parent_chapter or ''
                            if not chapter_for_subchapter:
                                # Subchapter L is Chapter II (DEA), others are Chapter I
                                if 'Subchapter L' in subchapter_text:
                                    chapter_for_subchapter = 'Chapter II'
                                else:
                                    chapter_for_subchapter = 'Chapter I'
                            subchapter_parts = self.fetch_parts_from_subchapter(url, chapter_for_subchapter, subchapter_text)
                            if subchapter_parts:
                                print(f"Found {len(subchapter_parts)} parts in {subchapter_text}")
                                regulations.extend(subchapter_parts)
                        except Exception as e:
                            print(f"Error fetching parts from subchapter {url}: {e}")
                    
                    return parent_chapter, subchapter_text
                
                # Check for parts
                if first_text.startswith('Part ') and not first_text.startswith('Parts '):
                    desc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    section_range = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    part_link = first_cell.find('a')
                    href = part_link.get('href', '') if part_link else ''
                    url = f"https://www.ecfr.gov{href}" if href.startswith('/') else (href if href else '')
                    
                    # Analyze status
                    status, status_reason = self.analyze_regulation_status(desc, url)
                    regulations.append({
                        'title': 'Title 21',
                        'chapter': parent_chapter or '',
                        'subchapter': parent_subchapter or '',
                        'part': first_text,
                        'section_range': section_range,
                        'description': desc,
                        'url': url,
                        'status': status,
                        'status_reason': status_reason
                    })
                    
                    # Try to fetch detailed sections from this part (limit to avoid too many requests)
                    if url and len(regulations) < 50:  # Only fetch details for first 50 parts
                        # Ensure we have chapter info - infer from subchapter if missing
                        chapter_for_part = parent_chapter or ''
                        if not chapter_for_part and parent_subchapter:
                            # Subchapter L is Chapter II (DEA), others are Chapter I
                            if 'Subchapter L' in parent_subchapter:
                                chapter_for_part = 'Chapter II'
                            else:
                                chapter_for_part = 'Chapter I'
                        part_details = self.fetch_part_details(url, first_text, chapter_for_part, parent_subchapter or '')
                        regulations.extend(part_details)
                
                # Check for nested tables - process recursively to find parts
                nested_tables = row.find_all('table', recursive=False)
                for nested_table in nested_tables:
                    nested_rows = nested_table.find_all('tr', recursive=False)
                    for nested_row in nested_rows:
                        # Recursively process nested rows to find parts
                        updated_chapter, updated_subchapter = process_row(nested_row, parent_chapter, parent_subchapter)
                        # Update parent context for deeper nesting
                        if updated_chapter:
                            parent_chapter = updated_chapter
                        if updated_subchapter:
                            parent_subchapter = updated_subchapter
                
                # Also check for parts in the same row (sometimes parts are in nested cells)
                if not first_text.startswith('Part ') and not first_text.startswith('Parts '):
                    # Look for part links anywhere in the row
                    all_links = row.find_all('a')
                    for row_link in all_links:
                        link_text = row_link.get_text(strip=True)
                        if link_text.startswith('Part ') and not link_text.startswith('Parts '):
                            # Found a part link in this row
                            desc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                            section_range = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            href = row_link.get('href', '')
                            url = f"https://www.ecfr.gov{href}" if href.startswith('/') else (href if href else '')
                            
                            status, status_reason = self.analyze_regulation_status(desc, url)
                            regulations.append({
                                'title': 'Title 21',
                                'chapter': parent_chapter or '',
                                'subchapter': parent_subchapter or '',
                                'part': link_text,
                                'section_range': section_range,
                                'description': desc,
                                'url': url,
                                'status': status,
                                'status_reason': status_reason
                            })
                            break  # Only add one part per row
                
                return parent_chapter, parent_subchapter
            
            # IMPROVEMENT 2: Process all rows with deeper nested table parsing
            rows = main_table.find_all('tr', recursive=False)
            for row in rows:
                current_chapter, current_subchapter = process_row(row, current_chapter, current_subchapter)
            
            # Deep recursive search for parts in all nested tables (up to 5 levels deep)
            def process_nested_tables_recursive(table_element, depth=0, max_depth=5):
                """Recursively process nested tables to find parts"""
                if depth > max_depth:
                    return
                
                nested_tables = table_element.find_all('table', recursive=False)
                for nested_table in nested_tables:
                    if nested_table == table_element:
                        continue  # Skip self
                    
                    nested_rows = nested_table.find_all('tr', recursive=False)
                    for nested_row in nested_rows:
                        process_row(nested_row, current_chapter, current_subchapter)
                    
                    # Recursively process deeper nested tables
                    process_nested_tables_recursive(nested_table, depth + 1, max_depth)
            
            # Process nested tables recursively
            process_nested_tables_recursive(main_table)
            
            # Also search for parts in all nested tables recursively (backup method)
            all_nested_tables = main_table.find_all('table', recursive=True)
            for nested_table in all_nested_tables:
                if nested_table == main_table:
                    continue  # Skip the main table
                nested_rows = nested_table.find_all('tr', recursive=False)
                for nested_row in nested_rows:
                    process_row(nested_row, current_chapter, current_subchapter)
            
            print(f"Successfully parsed {len(regulations)} regulations")
            return regulations
            
        except Exception as e:
            print(f"Error fetching regulations: {e}")
            import traceback
            traceback.print_exc()
            # Return sample data if scraping fails
            return self._get_sample_regulations()
    
    def fetch_parts_from_subchapter(self, subchapter_url: str, chapter: str, subchapter: str) -> List[Dict]:
        """Fetch all parts listed in a subchapter page - IMPROVEMENT 1"""
        regulations = []
        try:
            response = self.session.get(subchapter_url, timeout=20)
            if response.status_code != 200:
                return regulations
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Multiple strategies to find parts
            # Strategy 1: Look for part links in hrefs
            part_links = soup.find_all('a', href=lambda x: x and '/part-' in x)
            
            # Strategy 2: Look for text starting with "Part " in table cells
            part_cells = soup.find_all(['td', 'th'], string=lambda x: x and x.strip().startswith('Part ') and not x.strip().startswith('Parts '))
            for cell in part_cells:
                link = cell.find('a')
                if link:
                    part_links.append(link)
            
            # Strategy 3: Look in table rows for parts
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if cell_text.startswith('Part ') and not cell_text.startswith('Parts '):
                        link = cell.find('a')
                        if link and link not in part_links:
                            part_links.append(link)
            
            seen_parts = set()
            for link in part_links[:100]:  # Increased limit
                part_text = link.get_text(strip=True).strip()
                # Check if it's actually a part (starts with "Part ")
                if part_text.startswith('Part ') and not part_text.startswith('Parts '):
                    # Normalize part text (remove extra whitespace)
                    part_text = ' '.join(part_text.split())
                    if part_text not in seen_parts:
                        seen_parts.add(part_text)
                        href = link.get('href', '')
                        url = f"https://www.ecfr.gov{href}" if href.startswith('/') else href
                        
                        # Get description from parent row or element
                        parent_row = link.find_parent('tr')
                        if parent_row:
                            desc_cells = parent_row.find_all(['td', 'th'])
                            if len(desc_cells) > 1:
                                desc = desc_cells[1].get_text(strip=True)[:200]
                            else:
                                desc = parent_row.get_text(strip=True)[:200]
                        else:
                            parent = link.find_parent(['td', 'li', 'p', 'div'])
                            desc = parent.get_text(strip=True)[:200] if parent else part_text
                        
                        # Get section range if available
                        section_range = ''
                        if parent_row:
                            range_cells = parent_row.find_all(['td', 'th'])
                            if len(range_cells) > 2:
                                section_range = range_cells[2].get_text(strip=True)
                        
                        status, status_reason = self.analyze_regulation_status(desc, url)
                        
                        regulations.append({
                            'title': 'Title 21',
                            'chapter': chapter,
                            'subchapter': subchapter,
                            'part': part_text,
                            'section_range': section_range,
                            'description': desc,
                            'url': url,
                            'status': status,
                            'status_reason': status_reason
                        })
        except Exception as e:
            print(f"Error fetching parts from subchapter {subchapter_url}: {e}")
            import traceback
            traceback.print_exc()
        
        return regulations
    
    def fetch_part_details(self, part_url: str, part_name: str, chapter: str, subchapter: str) -> List[Dict]:
        """Fetch detailed sections from a part page"""
        regulations = []
        try:
            response = self.session.get(part_url, timeout=15)
            if response.status_code != 200:
                return regulations
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for section links or content
            section_links = soup.find_all('a', href=lambda x: x and '/section-' in x)
            
            for link in section_links[:20]:  # Limit to first 20 sections
                section_text = link.get_text(strip=True)
                href = link.get('href', '')
                url = f"https://www.ecfr.gov{href}" if href.startswith('/') else href
                
                # Extract section number
                section_match = section_text.split()[0] if section_text else ''
                
                # Get parent text for description
                parent = link.find_parent(['p', 'div', 'li'])
                desc = parent.get_text(strip=True)[:200] if parent else section_text
                
                status, status_reason = self.analyze_regulation_status(desc, url)
                
                regulations.append({
                    'title': 'Title 21',
                    'chapter': chapter,
                    'subchapter': subchapter,
                    'part': part_name,
                    'section_range': section_match,
                    'description': desc,
                    'url': url,
                    'status': status,
                    'status_reason': status_reason
                })
        except Exception as e:
            print(f"Error fetching part details from {part_url}: {e}")
        
        return regulations
    
    def _get_sample_regulations(self) -> List[Dict]:
        """Return sample regulations when scraping fails - expanded with more granular entries"""
        return [
            # Chapter I - Subchapter A (General)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter A',
                'part': 'Part 1',
                'section_range': '1.1',
                'description': 'General provisions - Establishes general provisions and definitions for FDA regulations',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-1',
                'status': 'Requires Compliance',
                'status_reason': 'General administrative provisions'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter A',
                'part': 'Part 1',
                'section_range': '1.2',
                'description': 'Definitions - Defines terms used throughout Title 21 regulations',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-1/section-1.2',
                'status': 'Requires Compliance',
                'status_reason': 'Provides definitions'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter A',
                'part': 'Part 2',
                'section_range': '2.1',
                'description': 'General administrative rulings and decisions',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-2',
                'status': 'Requires Compliance',
                'status_reason': 'Administrative procedures'
            },
            # Chapter I - Subchapter B (Food for Human Consumption)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter B',
                'part': 'Part 100',
                'section_range': '100.1',
                'description': 'Food for human consumption - General provisions for food regulations',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-100',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates food products'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter B',
                'part': 'Part 101',
                'section_range': '101.1',
                'description': 'Food labeling - Requirements for food product labeling',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101',
                'status': 'Requires Compliance',
                'status_reason': 'Mandates labeling requirements'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter B',
                'part': 'Part 101',
                'section_range': '101.9',
                'description': 'Nutrition labeling - Nutrition facts panel requirements',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/section-101.9',
                'status': 'Requires Compliance',
                'status_reason': 'Requires nutrition information'
            },
            # Chapter I - Subchapter C (Drugs: General)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter C',
                'part': 'Part 200',
                'section_range': '200.1',
                'description': 'General - General provisions for drug regulations',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-200',
                'status': 'Requires Compliance',
                'status_reason': 'General drug provisions'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter C',
                'part': 'Part 201',
                'section_range': '201.1',
                'description': 'Labeling - Requirements for prescription drug labeling',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-201',
                'status': 'Requires Compliance',
                'status_reason': 'Mandates drug labeling'
            },
            # Chapter I - Subchapter D (Drugs for Human Use)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter D',
                'part': 'Part 300',
                'section_range': '300.1',
                'description': 'General - General provisions for drugs for human use',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-D/part-300',
                'status': 'Requires Compliance',
                'status_reason': 'General drug provisions'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter D',
                'part': 'Part 310',
                'section_range': '310.1',
                'description': 'New drugs - Requirements for new drug applications',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-D/part-310',
                'status': 'Requires Compliance',
                'status_reason': 'Establishes approval requirements'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter D',
                'part': 'Part 312',
                'section_range': '312.1',
                'description': 'Investigational new drug application - Requirements for IND submissions',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-D/part-312',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates clinical trials'
            },
            # Chapter I - Subchapter E (Animal Drugs)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter E',
                'part': 'Part 500',
                'section_range': '500.1',
                'description': 'General - General provisions for animal drugs',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-E/part-500',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates animal drug products'
            },
            # Chapter I - Subchapter F (Biologics)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter F',
                'part': 'Part 600',
                'section_range': '600.1',
                'description': 'Biological products - General provisions for biological products',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-F/part-600',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates biologics'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter F',
                'part': 'Part 601',
                'section_range': '601.1',
                'description': 'Licensing - Requirements for biologics license applications',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-F/part-601',
                'status': 'Requires Compliance',
                'status_reason': 'Establishes licensing requirements'
            },
            # Chapter I - Subchapter G (Cosmetics)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter G',
                'part': 'Part 700',
                'section_range': '700.1',
                'description': 'General - General provisions for cosmetic products',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-G/part-700',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates cosmetic products'
            },
            # Chapter I - Subchapter H (Medical Devices)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter H',
                'part': 'Part 800',
                'section_range': '800.1',
                'description': 'General - General provisions for medical devices',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-800',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates medical devices'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter H',
                'part': 'Part 801',
                'section_range': '801.1',
                'description': 'Labeling - Requirements for medical device labeling',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801',
                'status': 'Requires Compliance',
                'status_reason': 'Mandates device labeling'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter H',
                'part': 'Part 807',
                'section_range': '807.1',
                'description': 'Establishment registration and device listing - Requirements for device manufacturers',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807',
                'status': 'Requires Compliance',
                'status_reason': 'Requires registration'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter H',
                'part': 'Part 812',
                'section_range': '812.1',
                'description': 'Investigational device exemptions - Requirements for investigational devices',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-812',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates investigational devices'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter H',
                'part': 'Part 814',
                'section_range': '814.1',
                'description': 'Premarket approval of medical devices - Requirements for PMA applications',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-814',
                'status': 'Requires Compliance',
                'status_reason': 'Establishes approval process'
            },
            # Chapter I - Subchapter J (Radiological Health)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter J',
                'part': 'Part 1000',
                'section_range': '1000.1',
                'description': 'General - General provisions for radiological health',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-J/part-1000',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates radiological equipment'
            },
            # Chapter I - Subchapter K (Tobacco Products)
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter K',
                'part': 'Part 1100',
                'section_range': '1100.1',
                'description': 'General - General provisions for tobacco products',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-K/part-1100',
                'status': 'Requires Compliance',
                'status_reason': 'Regulates tobacco products'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter I',
                'subchapter': 'Subchapter K',
                'part': 'Part 1140',
                'section_range': '1140.1',
                'description': 'Cigarettes and smokeless tobacco - Restrictions on sale and distribution',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-I/subchapter-K/part-1140',
                'status': 'Prohibited',
                'status_reason': 'Restricts sale to minors'
            },
            # Chapter II (Drug Enforcement Administration)
            {
                'title': 'Title 21',
                'chapter': 'Chapter II',
                'subchapter': '',
                'part': 'Part 1300',
                'section_range': '1300.1',
                'description': 'Definitions - Definitions for controlled substances',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-II/part-1300',
                'status': 'Requires Compliance',
                'status_reason': 'Provides definitions'
            },
            {
                'title': 'Title 21',
                'chapter': 'Chapter II',
                'subchapter': '',
                'part': 'Part 1301',
                'section_range': '1301.1',
                'description': 'Registration of manufacturers, distributors, and dispensers - Requirements for controlled substance handlers',
                'url': 'https://www.ecfr.gov/current/title-21/chapter-II/part-1301',
                'status': 'Requires Compliance',
                'status_reason': 'Requires registration'
            }
        ]
    
    def search_regulations(self, query: str) -> List[Dict]:
        """Search regulations by keyword, part number, or section number"""
        conn = get_db_connection()
        c = conn.cursor()
        
        # Normalize query
        query_lower = query.lower().strip()
        
        # Check if query looks like a part/section number (e.g., "Part 1301", "1301", "1301.1", "§1301")
        import re
        is_part_search = False
        is_section_search = False
        part_number = None
        section_number = None
        
        # Extract part number (e.g., "Part 1301", "1301", "part 1301")
        part_match = re.search(r'(?:part\s*)?(\d{4,5})', query_lower)
        if part_match:
            is_part_search = True
            part_number = part_match.group(1)
        
        # Extract section number (e.g., "1301.1", "§1301.1", "section 1301.1")
        section_match = re.search(r'(?:§|section\s*)?(\d{4,5}\.\d+)', query_lower)
        if section_match:
            is_section_search = True
            section_number = section_match.group(1)
        
        # Build search query - exclude Reserved sections by default (unless query explicitly mentions "reserved")
        exclude_reserved = 'reserved' not in query_lower
        
        if is_section_search:
            # Exact section number match
            base_query = '''
                SELECT * FROM regulations 
                WHERE (section_range LIKE ? OR section_range LIKE ?)
            '''
            if exclude_reserved:
                base_query += ' AND status != "Reserved"'
            base_query += ' ORDER BY chapter, subchapter, part, section_range'
            c.execute(base_query, (f"%{section_number}%", f"%{query}%"))
        elif is_part_search:
            # Part number search - exact match preferred
            base_query = '''
                SELECT * FROM regulations 
                WHERE (part LIKE ? OR part LIKE ? OR section_range LIKE ?)
            '''
            if exclude_reserved:
                base_query += ' AND status != "Reserved"'
            base_query += ''' ORDER BY 
                    CASE WHEN part LIKE ? THEN 1 ELSE 2 END,
                    chapter, subchapter, part'''
            c.execute(base_query, (
                f"%Part {part_number}%",
                f"%{part_number}%",
                f"%{part_number}%",
                f"%Part {part_number}%"
            ))
        else:
            # General keyword search - include chapter field
            # Handle Roman numeral conversion for chapter searches (e.g., "chapter 2" -> "Chapter II")
            import re
            chapter_patterns = []
            query_lower = query.lower().strip()
            
            # Check if query contains chapter number
            chapter_num_match = re.search(r'chapter\s*(\d+)', query_lower)
            if chapter_num_match:
                chapter_num = int(chapter_num_match.group(1))
                # Convert to Roman numeral
                roman_numerals = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
                if 1 <= chapter_num <= 10:
                    roman = roman_numerals[chapter_num]
                    chapter_patterns.append(f"%Chapter {roman}%")
                    chapter_patterns.append(f"%chapter {roman}%")
                    chapter_patterns.append(f"%Chapter {chapter_num}%")
                    chapter_patterns.append(f"%chapter {chapter_num}%")
            
            search_pattern = f"%{query}%"
            base_query = '''
                SELECT * FROM regulations 
                WHERE (description LIKE ? OR part LIKE ? OR subchapter LIKE ?
                   OR section_range LIKE ? OR content_summary LIKE ? OR chapter LIKE ?'''
            
            # Add additional chapter patterns if we detected a chapter number
            if chapter_patterns:
                for pattern in chapter_patterns[1:]:  # Skip first, already added
                    base_query += f' OR chapter LIKE ?'
            
            base_query += ')'
            
            if exclude_reserved:
                base_query += ' AND status != "Reserved"'
            base_query += ' ORDER BY chapter, subchapter, part'
            
            # Build parameters list
            params = [search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, search_pattern]
            if chapter_patterns:
                params.extend(chapter_patterns[1:])  # Add additional chapter patterns
            
            c.execute(base_query, tuple(params))
        
        results = []
        for row in c.fetchall():
            results.append(dict(row))
        
        conn.close()
        return results

class RegulationAgent:
    """Agent for processing regulation queries"""
    
    def __init__(self):
        self.scraper = RegulationScraper()
    
    def process_query(self, query: str) -> Dict:
        """Process a regulation query and return results"""
        # Log the query
        conn = get_db_connection()
        c = conn.cursor()
        
        # Search regulations
        results = self.scraper.search_regulations(query)
        
        # Log search history
        c.execute('''
            INSERT INTO search_history (query, results_count)
            VALUES (?, ?)
        ''', (query, len(results)))
        conn.commit()
        conn.close()
        
        # Generate summary
        summary = self._generate_summary(results, query)
        
        return {
            'query': query,
            'results': results,
            'count': len(results),
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_summary(self, results: List[Dict], query: str) -> str:
        """Generate a human-readable summary of search results"""
        if not results:
            return f"No regulations found matching '{query}'."
        
        summary_parts = [f"Found {len(results)} regulation(s) matching '{query}':\n"]
        
        # Group by chapter
        by_chapter = {}
        for result in results:
            chapter = result.get('chapter', 'Unknown')
            if chapter not in by_chapter:
                by_chapter[chapter] = []
            by_chapter[chapter].append(result)
        
        for chapter, items in by_chapter.items():
            summary_parts.append(f"\n{chapter}:")
            for item in items[:5]:  # Limit to 5 per chapter
                part = item.get('part', '')
                desc = item.get('description', '')
                if part:
                    summary_parts.append(f"  - {part}: {desc}")
                elif desc:
                    summary_parts.append(f"  - {desc}")
        
        if len(results) > 5:
            summary_parts.append(f"\n... and {len(results) - 5} more result(s)")
        
        return "\n".join(summary_parts)

# Initialize database on startup
init_db()

# Global agent instance
agent = RegulationAgent()

# Initialize RAG service
try:
    rag_service = RAGService()
    print("✅ RAG service initialized")
except Exception as e:
    print(f"⚠️  Warning: Could not initialize RAG service: {e}")
    rag_service = None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/regulations', methods=['GET'])
def get_regulations():
    """Get all regulations from database - Filter out administrative and reserved by default"""
    # Get filter parameters
    filter_parts_only = request.args.get('parts_only', 'false').lower() == 'true'
    include_administrative = request.args.get('include_administrative', 'false').lower() == 'true'
    include_reserved = request.args.get('include_reserved', 'false').lower() == 'true'
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Build query with filters
    query = 'SELECT * FROM regulations WHERE 1=1'
    params = []
    
    if filter_parts_only:
        query += ' AND part != "" AND part IS NOT NULL'
    
    if not include_administrative:
        # Filter out administrative entries by default (cleaner view)
        query += ' AND status != "Administrative"'
    
    if not include_reserved:
        # Filter out reserved sections by default (they're empty placeholders)
        query += ' AND status != "Reserved"'
    
    query += ' ORDER BY chapter, subchapter, part'
    
    c.execute(query, params)
    regulations = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(regulations)

@app.route('/api/regulations/<int:regulation_id>', methods=['GET'])
def get_regulation(regulation_id):
    """Get a single regulation by ID"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM regulations WHERE id = ?', (regulation_id,))
    regulation = c.fetchone()
    conn.close()
    
    if regulation:
        return jsonify(dict(regulation))
    else:
        return jsonify({'error': 'Regulation not found'}), 404

@app.route('/api/search', methods=['POST'])
def search_regulations():
    """Search regulations - Enhanced with RAG semantic search"""
    data = request.get_json()
    query = data.get('query', '')
    use_rag = data.get('use_rag', True)  # Default to RAG
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Use RAG if available and enabled
    if use_rag and rag_service and rag_service.is_indexed:
        try:
            # Perform semantic search
            semantic_results = rag_service.semantic_search(query, n_results=20)
            
            # Also get keyword results for hybrid search
            keyword_result = agent.process_query(query)
            keyword_results = keyword_result.get('results', [])
            
            # Perform hybrid search
            hybrid_results = rag_service.hybrid_search(
                query,
                n_results=20,
                keyword_results=keyword_results,
                semantic_weight=0.7
            )
            
            # Generate summary with RAG results
            summary = agent._generate_summary(hybrid_results, query)
            
            return jsonify({
                'query': query,
                'results': hybrid_results,
                'count': len(hybrid_results),
                'summary': summary,
                'timestamp': datetime.now().isoformat(),
                'search_method': 'rag_hybrid'
            })
        except Exception as e:
            print(f"RAG search error, falling back to keyword: {e}")
            # Fallback to keyword search
            result = agent.process_query(query)
            result['search_method'] = 'keyword_fallback'
            return jsonify(result)
    else:
        # Fallback to keyword search
        result = agent.process_query(query)
        result['search_method'] = 'keyword'
        if not rag_service or not rag_service.is_indexed:
            result['rag_status'] = 'not_indexed'
        return jsonify(result)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check scraper health and URL accessibility"""
    try:
        from robust_scraper import RobustRegulationScraper
        robust_scraper = RobustRegulationScraper()
        health = robust_scraper.health_check()
        return jsonify(health)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'base_scraper_available': True
        })

@app.route('/api/refresh', methods=['POST'])
def refresh_regulations():
    """Refresh regulations from eCFR website with robust fallback strategies"""
    def update_regulations():
        # Try robust scraper first
        try:
            from robust_scraper import RobustRegulationScraper
            robust_scraper = RobustRegulationScraper()
            regulations = robust_scraper.fetch_with_multiple_strategies()
            
            if regulations:
                print(f"Successfully fetched {len(regulations)} regulations using robust scraper")
            else:
                print("Robust scraper returned empty, trying standard scraper...")
                scraper = RegulationScraper()
                regulations = scraper.fetch_title_21_structure()
        except Exception as e:
            print(f"Robust scraper failed: {e}, falling back to standard scraper")
            scraper = RegulationScraper()
            regulations = scraper.fetch_title_21_structure()
        
        # Use sample data if scraping returns empty
        if not regulations:
            print("All scraping methods returned empty, using sample regulations")
            scraper = RegulationScraper()
            regulations = scraper._get_sample_regulations()
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get existing regulations for change detection (before deleting)
        c.execute('SELECT * FROM regulations')
        existing_regs = {}
        for row in c.fetchall():
            reg_dict = dict(row)
            # Create lookup key by part + description
            key = f"{reg_dict.get('part', '')}|{reg_dict.get('description', '')[:100]}"
            existing_regs[key] = reg_dict
        
        # Clear old regulations
        c.execute('DELETE FROM regulations')
        
        # Insert new regulations with status analysis and change detection
        scraper = RegulationScraper()
        changes_detected = []
        
        for reg in regulations:
            # Normalize the regulation structure - handle different formats
            # If robust scraper returned type/text format, convert it
            if 'type' in reg and 'text' in reg:
                reg_type = reg.get('type', '')
                reg_text = reg.get('text', '')
                if reg_type == 'chapter':
                    reg['chapter'] = reg_text
                    reg['subchapter'] = ''
                    reg['part'] = ''
                elif reg_type == 'subchapter':
                    reg['chapter'] = reg.get('parent_chapter', '')
                    reg['subchapter'] = reg_text
                    reg['part'] = ''
                elif reg_type == 'part':
                    reg['chapter'] = reg.get('parent_chapter', '')
                    reg['subchapter'] = reg.get('parent_subchapter', '')
                    reg['part'] = reg_text
            
            # Ensure required fields exist
            reg.setdefault('title', 'Title 21')
            reg.setdefault('chapter', '')
            reg.setdefault('subchapter', '')
            reg.setdefault('part', '')
            reg.setdefault('section_range', '')
            reg.setdefault('description', '')
            reg.setdefault('url', '')
            
            # Always re-analyze status during refresh to detect changes
            # This ensures if regulation content changes, status will be updated
            status, status_reason = scraper.analyze_regulation_status(
                reg.get('description', ''),
                reg.get('url', ''),
                reg.get('content_summary', '')
            )
            reg['status'] = status
            reg['status_reason'] = status_reason
            
            # Check for changes by comparing with existing regulations
            lookup_key = f"{reg.get('part', '')}|{reg.get('description', '')[:100]}"
            existing_reg = existing_regs.get(lookup_key)
            
            # Insert new regulation
            c.execute('''
                INSERT INTO regulations 
                (title, chapter, subchapter, part, section_range, description, url, status, status_reason, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reg.get('title', ''),
                reg.get('chapter', ''),
                reg.get('subchapter', ''),
                reg.get('part', ''),
                reg.get('section_range', ''),
                reg.get('description', ''),
                reg.get('url', ''),
                reg.get('status', 'Requires Compliance'),
                reg.get('status_reason', ''),
                datetime.now()
            ))
            
            new_reg_id = c.lastrowid
            
            # Detect changes if this regulation existed before
            if existing_reg:
                # Check for changes in key fields
                fields_to_check = ['description', 'status', 'url', 'section_range']
                for field in fields_to_check:
                    old_val = str(existing_reg.get(field, '') or '')
                    new_val = str(reg.get(field, '') or '')
                    if old_val != new_val:
                        c.execute('''
                            INSERT INTO regulation_changes 
                            (regulation_id, change_type, field_name, old_value, new_value, detected_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            new_reg_id,
                            'updated',
                            field,
                            old_val[:500],  # Limit length
                            new_val[:500],
                            datetime.now()
                        ))
                        changes_detected.append({
                            'part': reg.get('part', ''),
                            'field': field,
                            'old': old_val[:100],
                            'new': new_val[:100]
                        })
            else:
                # New regulation added
                c.execute('''
                    INSERT INTO regulation_changes 
                    (regulation_id, change_type, field_name, old_value, new_value, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    new_reg_id,
                    'added',
                    'regulation',
                    '',
                    reg.get('part', '') + ': ' + reg.get('description', '')[:100],
                    datetime.now()
                ))
                changes_detected.append({
                    'part': reg.get('part', ''),
                    'field': 'new_regulation',
                    'old': '',
                    'new': reg.get('description', '')[:100]
                })
        
        conn.commit()
        conn.close()
        
        if changes_detected:
            print(f"✅ Detected {len(changes_detected)} changes in regulations")
        
        conn.commit()
        conn.close()
        print(f"Updated database with {len(regulations)} regulations")
    
    # Run in background thread
    thread = threading.Thread(target=update_regulations)
    thread.start()
    
    return jsonify({'status': 'refresh_started', 'message': 'Regulations are being updated in the background'})

@app.route('/api/changes', methods=['GET'])
def get_recent_changes():
    """Get recent regulation changes"""
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT 
            rc.id,
            rc.change_type,
            rc.field_name,
            rc.old_value,
            rc.new_value,
            rc.detected_at,
            rc.notified,
            rc.regulation_id,
            r.part,
            r.description,
            r.chapter,
            r.subchapter,
            r.url
        FROM regulation_changes rc
        LEFT JOIN regulations r ON rc.regulation_id = r.id
        WHERE rc.detected_at >= datetime('now', '-' || ? || ' days')
        ORDER BY rc.detected_at DESC
        LIMIT ?
    ''', (days, limit))
    
    changes = []
    for row in c.fetchall():
        # Try to extract part/description from new_value if JOIN didn't find the regulation
        part = row['part']
        description = row['description']
        
        # If part/description are null, try to extract from new_value
        if not part and row['new_value']:
            # For "added" changes, new_value might be "Part 1401: Description"
            if 'Part ' in row['new_value']:
                part_match = row['new_value'].split(':')[0].strip()
                if part_match.startswith('Part '):
                    part = part_match
                if ':' in row['new_value']:
                    description = row['new_value'].split(':', 1)[1].strip()
        
        changes.append({
            'id': row['id'],
            'change_type': row['change_type'],
            'field_name': row['field_name'],
            'old_value': row['old_value'],
            'new_value': row['new_value'],
            'detected_at': row['detected_at'],
            'notified': bool(row['notified']),
            'regulation_id': row['regulation_id'],
            'part': part,
            'description': description,
            'chapter': row['chapter'],
            'subchapter': row['subchapter'],
            'url': row['url']
        })
    
    conn.close()
    
    return jsonify({
        'changes': changes,
        'count': len(changes),
        'days': days
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about regulations"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) as total FROM regulations')
    total = c.fetchone()['total']
    
    c.execute('SELECT COUNT(*) as searches FROM search_history')
    searches = c.fetchone()['searches']
    
    c.execute('SELECT COUNT(DISTINCT chapter) as chapters FROM regulations WHERE chapter != ""')
    chapters = c.fetchone()['chapters']
    
    conn.close()
    
    return jsonify({
        'total_regulations': total,
        'total_searches': searches,
        'total_chapters': chapters
    })

@app.route('/api/llm/ask', methods=['POST'])
def ask_llm():
    """Ask a question about regulations using LLM - Enhanced with RAG"""
    data = request.get_json()
    question = data.get('question', '')
    use_rag = data.get('use_rag', True)  # Default to RAG
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    # Use RAG if available and enabled
    if use_rag and rag_service and rag_service.is_indexed:
        try:
            # Get most relevant regulations using semantic search
            regulations = rag_service.semantic_search(question, n_results=10)
            
            # Get context string for LLM
            context = rag_service.get_relevant_context(question, n_results=5)
            
            # Use LLM to answer with RAG context
            llm_analyzer = LLMRegulationAnalyzer()
            result = llm_analyzer.answer_question(question, regulations)
            result['rag_context'] = context
            result['search_method'] = 'rag'
            return jsonify(result)
        except Exception as e:
            print(f"RAG Q&A error, falling back to keyword: {e}")
            # Fallback to keyword search
            search_pattern = f"%{question}%"
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''
                SELECT * FROM regulations 
                WHERE description LIKE ? 
                   OR part LIKE ? 
                   OR subchapter LIKE ?
                ORDER BY chapter, subchapter, part
                LIMIT 20
            ''', (search_pattern, search_pattern, search_pattern))
            regulations = [dict(row) for row in c.fetchall()]
            conn.close()
            
            try:
                llm_analyzer = LLMRegulationAnalyzer()
                result = llm_analyzer.answer_question(question, regulations)
                result['search_method'] = 'keyword_fallback'
                return jsonify(result)
            except Exception as llm_error:
                return jsonify({
                    'error': str(llm_error),
                    'answer': 'LLM service not available. Please configure OPENAI_API_KEY.',
                    'relevant_regulations': regulations[:5],
                    'search_method': 'keyword_fallback'
                }), 500
    else:
        # Fallback to keyword search
        search_pattern = f"%{question}%"
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            SELECT * FROM regulations 
            WHERE description LIKE ? 
               OR part LIKE ? 
               OR subchapter LIKE ?
            ORDER BY chapter, subchapter, part
            LIMIT 20
        ''', (search_pattern, search_pattern, search_pattern))
        regulations = [dict(row) for row in c.fetchall()]
        conn.close()
        
        try:
            llm_analyzer = LLMRegulationAnalyzer()
            result = llm_analyzer.answer_question(question, regulations)
            result['search_method'] = 'keyword'
            if not rag_service or not rag_service.is_indexed:
                result['rag_status'] = 'not_indexed'
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'error': str(e),
                'answer': 'LLM service not available. Please configure OPENAI_API_KEY.',
                'relevant_regulations': regulations[:5],
                'search_method': 'keyword'
            }), 500

@app.route('/api/rag/index', methods=['POST'])
def index_rag():
    """Initialize or reindex RAG with current regulations"""
    try:
        if not rag_service:
            return jsonify({'error': 'RAG service not initialized'}), 500
        
        # Get all regulations from database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM regulations')
        regulations = [dict(row) for row in c.fetchall()]
        conn.close()
        
        if not regulations:
            return jsonify({'error': 'No regulations found in database. Please refresh data first.'}), 400
        
        # Clear existing index
        rag_service.clear_index()
        
        # Index regulations
        indexed_count = rag_service.index_regulations(regulations)
        
        return jsonify({
            'status': 'success',
            'indexed_count': indexed_count,
            'message': f'Successfully indexed {indexed_count} regulations'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/rag/stats', methods=['GET'])
def rag_stats():
    """Get RAG service statistics"""
    if not rag_service:
        return jsonify({
            'error': 'RAG service not initialized',
            'is_indexed': False
        }), 500
    
    stats = rag_service.get_stats()
    return jsonify(stats)

@app.route('/api/llm/summarize', methods=['POST'])
def summarize_regulation():
    """Get LLM-generated summary of a regulation"""
    data = request.get_json()
    reg_id = data.get('regulation_id')
    
    if not reg_id:
        return jsonify({'error': 'regulation_id is required'}), 400
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM regulations WHERE id = ?', (reg_id,))
    reg = c.fetchone()
    conn.close()
    
    if not reg:
        return jsonify({'error': 'Regulation not found'}), 404
    
    reg_dict = dict(reg)
    
    # Use LLM to summarize
    try:
        llm_analyzer = LLMRegulationAnalyzer()
        summary = llm_analyzer.summarize_regulation(
            reg_dict.get('description', ''),
            reg_dict.get('url', ''),
            reg_dict.get('content_summary', '')
        )
        return jsonify({
            'regulation_id': reg_id,
            'summary': summary,
            'original_description': reg_dict.get('description', '')
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'summary': reg_dict.get('description', '')
        }), 500

if __name__ == '__main__':
    # Initial data load (non-blocking)
    def load_initial_data():
        print("Loading initial regulations data...")
        scraper = RegulationScraper()
        regulations = scraper.fetch_title_21_structure()
        
        if regulations:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('DELETE FROM regulations')
            for reg in regulations:
                c.execute('''
                    INSERT INTO regulations 
                    (title, chapter, subchapter, part, section_range, description, url, status, status_reason, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reg.get('title', ''),
                    reg.get('chapter', ''),
                    reg.get('subchapter', ''),
                    reg.get('part', ''),
                    reg.get('section_range', ''),
                    reg.get('description', ''),
                    reg.get('url', ''),
                    reg.get('status', 'Unknown'),
                    reg.get('status_reason', ''),
                    datetime.now()
                ))
            conn.commit()
            conn.close()
            print(f"Loaded {len(regulations)} regulations")
        else:
            print("No regulations loaded. Use Refresh Data button to try again.")
    
    # Load data in background thread so server starts immediately
    load_thread = threading.Thread(target=load_initial_data, daemon=True)
    load_thread.start()
    
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000)

