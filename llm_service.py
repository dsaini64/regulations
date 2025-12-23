"""
LLM Service for Regulation Analysis
Integrates with OpenAI/ChatGPT for enhanced regulation analysis
"""

import os
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMRegulationAnalyzer:
    """LLM-powered regulation analyzer using OpenAI"""
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            print("Warning: OPENAI_API_KEY not found. LLM features disabled.")
    
    def analyze_regulation_status(self, description: str, url: str = '', content: str = '') -> tuple:
        """
        Use LLM to analyze regulation and determine its status.
        Returns (status, reason) tuple.
        Status options: 'Requires Compliance', 'Prohibited', 'Reserved', 'Administrative', 'Unknown'
        """
        if not self.enabled:
            return ('Unknown', 'LLM not configured')
        
        try:
            # Prepare comprehensive context with actual regulation content
            content_text = content[:3000] if content else 'No content available'
            
            context = f"""
You are an expert in FDA Title 21 CFR regulations. Analyze this regulation carefully.

Regulation Title/Description: {description}
URL: {url}
Regulation Content: {content_text}

Analyze this regulation and determine its status:

1. **Prohibited**: If the regulation explicitly PROHIBITS, FORBIDS, or BANS certain activities (look for phrases like "shall not", "prohibited", "forbidden", "not permitted", "unlawful")

2. **Requires Compliance**: If the regulation establishes REQUIREMENTS, STANDARDS, or PROCEDURES that must be followed (most regulations fall here - they tell you what you MUST do, not what you CANNOT do)

3. **Reserved**: If the section is explicitly marked as reserved for future use

4. **Administrative**: If it's purely organizational (definitions, structure, general provisions)

5. **Unknown**: If you cannot determine from the available information

IMPORTANT: Most Title 21 regulations are REQUIREMENTS (what you must do), not PROHIBITIONS (what you cannot do). 
Only mark as "Prohibited" if there are explicit prohibitions in the text.

Respond in this exact format:
STATUS: [Requires Compliance/Prohibited/Reserved/Administrative/Unknown]
REASON: [brief explanation - one sentence]
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using mini for cost efficiency
                messages=[
                    {"role": "system", "content": "You are an expert in FDA Title 21 CFR regulations. Analyze regulations carefully to determine their true nature - whether they prohibit activities, require compliance, or are administrative."},
                    {"role": "user", "content": context}
                ],
                temperature=0.2,  # Lower temperature for more consistent analysis
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse response
            status = 'Unknown'
            reason = 'Analysis completed'
            
            if 'STATUS:' in result:
                status_line = [line for line in result.split('\n') if 'STATUS:' in line][0]
                status = status_line.split('STATUS:')[1].strip()
                # Normalize status values
                status_lower = status.lower()
                if 'prohibit' in status_lower:
                    status = 'Prohibited'
                elif 'compliance' in status_lower or 'requirement' in status_lower:
                    status = 'Requires Compliance'
                elif 'reserved' in status_lower:
                    status = 'Reserved'
                elif 'administrative' in status_lower or 'admin' in status_lower:
                    status = 'Administrative'
                else:
                    status = 'Unknown'
            
            if 'REASON:' in result:
                reason_line = [line for line in result.split('\n') if 'REASON:' in line][0]
                reason = reason_line.split('REASON:')[1].strip()
            
            return (status, reason)
            
        except Exception as e:
            print(f"LLM analysis error: {e}")
            return ('Unknown', f'LLM analysis failed: {str(e)}')
    
    def summarize_regulation(self, description: str, url: str = '', content: str = '') -> str:
        """Generate a concise summary of a regulation"""
        if not self.enabled:
            return description[:200] + '...' if len(description) > 200 else description
        
        try:
            context = f"""
Regulation Description: {description}
URL: {url}
Content: {content[:2000] if content else 'None'}

Provide a concise, clear summary (2-3 sentences) of what this regulation covers and its key requirements.
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert in FDA Title 21 regulations. Provide clear, concise summaries."},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"LLM summarization error: {e}")
            return description
    
    def answer_question(self, question: str, regulations: List[Dict]) -> Dict:
        """
        Answer a question about regulations using LLM.
        Returns a dictionary with answer and relevant regulations.
        """
        if not self.enabled:
            return {
                'answer': 'LLM service not configured. Please set OPENAI_API_KEY environment variable.',
                'relevant_regulations': regulations[:5],
                'confidence': 'low'
            }
        
        try:
            # Prepare context from regulations
            reg_context = "\n\n".join([
                f"Part: {r.get('part', 'N/A')}\n"
                f"Description: {r.get('description', 'N/A')}\n"
                f"Status: {r.get('status', 'Unknown')}\n"
                f"URL: {r.get('url', 'N/A')}"
                for r in regulations[:10]  # Limit to 10 for context
            ])
            
            prompt = f"""
You are an expert in FDA Title 21 regulations. Answer the following question based on the provided regulations.

Question: {question}

Relevant Regulations:
{reg_context}

Provide:
1. A clear, direct answer to the question
2. Reference specific parts/sections if relevant
3. Note if the answer is based on limited information

Format your response as:
ANSWER: [your answer]
REFERENCES: [list relevant parts/sections]
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert in FDA Title 21 regulations. Provide accurate, helpful answers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            answer_text = response.choices[0].message.content.strip()
            
            # Extract answer and references
            answer = answer_text
            references = []
            
            if 'ANSWER:' in answer_text:
                answer = answer_text.split('ANSWER:')[1].split('REFERENCES:')[0].strip()
            
            if 'REFERENCES:' in answer_text:
                ref_section = answer_text.split('REFERENCES:')[1].strip()
                references = [r.strip() for r in ref_section.split('\n') if r.strip()]
            
            return {
                'answer': answer,
                'references': references,
                'relevant_regulations': regulations[:5],
                'confidence': 'high' if len(regulations) > 0 else 'low'
            }
            
        except Exception as e:
            print(f"LLM question answering error: {e}")
            return {
                'answer': f'Error processing question: {str(e)}',
                'relevant_regulations': regulations[:5],
                'confidence': 'low'
            }
    
    def extract_key_requirements(self, description: str, content: str = '') -> List[str]:
        """Extract key requirements from regulation text"""
        if not self.enabled:
            return []
        
        try:
            context = f"""
Regulation Description: {description}
Content: {content[:2000] if content else 'None'}

Extract the key requirements, prohibitions, or allowances from this regulation.
List them as bullet points (3-5 items).
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract key requirements from regulations."},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            # Parse bullet points
            requirements = [line.strip('- •').strip() for line in result.split('\n') if line.strip() and (line.strip().startswith('-') or line.strip().startswith('•'))]
            
            return requirements[:5]  # Limit to 5
            
        except Exception as e:
            print(f"LLM extraction error: {e}")
            return []

