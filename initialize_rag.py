"""
Script to initialize RAG with existing regulations
Run this after refreshing regulations data
"""

import sqlite3
from rag_service import RAGService

DB_NAME = 'regulations.db'

def initialize_rag():
    """Initialize RAG with all regulations from database"""
    print("🚀 Initializing RAG service...")
    
    # Initialize RAG service
    try:
        rag_service = RAGService()
        print("✅ RAG service initialized")
    except Exception as e:
        print(f"❌ Error initializing RAG service: {e}")
        return
    
    # Get all regulations from database
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
    c = conn.cursor()
    c.execute('SELECT * FROM regulations')
    rows = c.fetchall()
    regulations = [dict(row) for row in rows]
    conn.close()
    
    if not regulations:
        print("⚠️  No regulations found in database.")
        print("   Please run the refresh endpoint first to load regulations.")
        return
    
    print(f"📚 Found {len(regulations)} regulations in database")
    
    # Clear existing index
    print("🧹 Clearing existing index...")
    rag_service.clear_index()
    
    # Index regulations
    print("📝 Indexing regulations...")
    indexed_count = rag_service.index_regulations(regulations)
    
    if indexed_count > 0:
        print(f"✅ Successfully indexed {indexed_count} regulations")
        print("🎉 RAG is now ready to use!")
    else:
        print("❌ Failed to index regulations")

if __name__ == '__main__':
    initialize_rag()

