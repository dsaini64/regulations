"""
Agent Workflow System for Regulation Queries
This module provides an agent-based workflow for processing regulation queries
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime
import json

class RegulationAgentWorkflow:
    """
    Agent workflow system for processing regulation queries.
    Agents can search, analyze, and summarize regulations.
    """
    
    def __init__(self, api_base_url: str = "http://localhost:5000"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
    
    def search(self, query: str) -> Dict:
        """Agent searches for regulations matching the query"""
        try:
            response = self.session.post(
                f"{self.api_base_url}/api/search",
                json={"query": query},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "error": str(e),
                "query": query,
                "results": [],
                "count": 0
            }
    
    def analyze(self, query: str, context: Optional[str] = None) -> Dict:
        """
        Agent analyzes a query and provides comprehensive results.
        This is a multi-step workflow:
        1. Search for regulations
        2. Categorize results
        3. Generate summary
        """
        # Step 1: Search
        search_results = self.search(query)
        
        if search_results.get("error") or search_results.get("count", 0) == 0:
            return {
                "query": query,
                "status": "no_results",
                "message": f"No regulations found for '{query}'",
                "results": []
            }
        
        # Step 2: Categorize
        categorized = self._categorize_results(search_results["results"])
        
        # Step 3: Generate comprehensive summary
        summary = self._generate_comprehensive_summary(
            query, 
            search_results["results"], 
            categorized,
            context
        )
        
        return {
            "query": query,
            "status": "success",
            "total_results": search_results["count"],
            "categories": categorized,
            "summary": summary,
            "results": search_results["results"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _categorize_results(self, results: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize results by chapter and subchapter"""
        categories = {}
        
        for result in results:
            chapter = result.get("chapter", "Unknown")
            subchapter = result.get("subchapter", "General")
            
            key = f"{chapter} - {subchapter}" if subchapter else chapter
            
            if key not in categories:
                categories[key] = []
            categories[key].append(result)
        
        return categories
    
    def _generate_comprehensive_summary(
        self, 
        query: str, 
        results: List[Dict],
        categories: Dict[str, List[Dict]],
        context: Optional[str] = None
    ) -> str:
        """Generate a comprehensive summary of search results"""
        summary_parts = [
            f"Regulation Search Analysis for: '{query}'",
            "=" * 60,
            f"\nTotal Results: {len(results)}",
            f"Categories Found: {len(categories)}",
        ]
        
        if context:
            summary_parts.append(f"\nContext: {context}")
        
        summary_parts.append("\n\nResults by Category:")
        summary_parts.append("-" * 60)
        
        for category, items in categories.items():
            summary_parts.append(f"\n{category}:")
            summary_parts.append(f"  Found {len(items)} regulation(s)")
            
            # Show top 3 items per category
            for item in items[:3]:
                part = item.get("part", "")
                desc = item.get("description", "")
                if part:
                    summary_parts.append(f"    • {part}: {desc[:100]}...")
                elif desc:
                    summary_parts.append(f"    • {desc[:100]}...")
            
            if len(items) > 3:
                summary_parts.append(f"    ... and {len(items) - 3} more")
        
        summary_parts.append("\n" + "=" * 60)
        summary_parts.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(summary_parts)
    
    def batch_search(self, queries: List[str]) -> List[Dict]:
        """Process multiple queries in batch"""
        results = []
        for query in queries:
            result = self.analyze(query)
            results.append(result)
        return results
    
    def get_recommendations(self, query: str) -> List[str]:
        """
        Agent provides recommendations based on the query.
        This could suggest related searches or relevant regulations.
        """
        results = self.search(query)
        
        if results.get("count", 0) == 0:
            return [
                "Try searching with different keywords",
                "Check spelling of your search terms",
                "Use broader search terms"
            ]
        
        recommendations = []
        
        # Extract unique chapters
        chapters = set()
        for result in results.get("results", []):
            chapter = result.get("chapter", "")
            if chapter:
                chapters.add(chapter)
        
        if chapters:
            recommendations.append(f"Explore regulations in: {', '.join(list(chapters)[:3])}")
        
        # Suggest related searches
        recommendations.append("Consider searching for related terms in the same category")
        recommendations.append("Review the section ranges for detailed information")
        
        return recommendations


# Example usage
if __name__ == "__main__":
    # Initialize the agent workflow
    agent = RegulationAgentWorkflow()
    
    # Example queries
    queries = [
        "medical devices",
        "drug approval",
        "food labeling"
    ]
    
    print("Agent Workflow Demo")
    print("=" * 60)
    
    for query in queries:
        print(f"\nProcessing query: '{query}'")
        print("-" * 60)
        
        result = agent.analyze(query)
        
        if result.get("status") == "success":
            print(f"\n{result['summary']}")
            print(f"\nRecommendations:")
            recommendations = agent.get_recommendations(query)
            for rec in recommendations:
                print(f"  • {rec}")
        else:
            print(f"  {result.get('message', 'No results')}")
        
        print("\n" + "=" * 60)

