"""
RAG (Retrieval-Augmented Generation) Service for Regulations
Provides semantic search and improved context retrieval for LLM Q&A
Uses FAISS for vector storage (more compatible than ChromaDB)
"""

import os
import json
import pickle
from typing import List, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

class RAGService:
    """RAG service for semantic search and retrieval using FAISS"""
    
    def __init__(self, collection_name: str = "regulations"):
        """Initialize RAG service with FAISS vector database"""
        self.collection_name = collection_name
        self.index_file = f"./faiss_index_{collection_name}.pkl"
        self.metadata_file = f"./faiss_metadata_{collection_name}.json"
        
        # Initialize embedding model
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_dim = 384  # Dimension for all-MiniLM-L6-v2
            self.use_local_embeddings = True
            print("✅ Using local sentence transformer for embeddings")
        except Exception as e:
            print(f"Warning: Could not load local embedding model: {e}")
            self.embedding_model = None
            self.use_local_embeddings = False
            self.embedding_dim = 384
        
        # Initialize FAISS index
        self.index = None
        self.regulations_metadata = []
        self.is_indexed = False
        
        # Try to load existing index
        self._load_index()
    
    def _load_index(self):
        """Load existing FAISS index if available"""
        try:
            if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
                # Load FAISS index
                self.index = faiss.read_index(self.index_file)
                
                # Load metadata
                with open(self.metadata_file, 'r') as f:
                    self.regulations_metadata = json.load(f)
                
                self.is_indexed = len(self.regulations_metadata) > 0
                if self.is_indexed:
                    print(f"✅ Loaded existing index with {len(self.regulations_metadata)} regulations")
        except Exception as e:
            print(f"Could not load existing index: {e}")
            self.index = None
            self.regulations_metadata = []
            self.is_indexed = False
    
    def _save_index(self):
        """Save FAISS index and metadata to disk"""
        try:
            if self.index and self.regulations_metadata:
                # Save FAISS index
                faiss.write_index(self.index, self.index_file)
                
                # Save metadata
                with open(self.metadata_file, 'w') as f:
                    json.dump(self.regulations_metadata, f)
                
                print(f"✅ Saved index with {len(self.regulations_metadata)} regulations")
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        if self.use_local_embeddings and self.embedding_model:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding.astype('float32')
        else:
            # Fallback: use OpenAI embeddings if available
            try:
                from openai import OpenAI
                from dotenv import load_dotenv
                load_dotenv()
                
                api_key = os.getenv('OPENAI_API_KEY')
                if api_key:
                    client = OpenAI(api_key=api_key)
                    response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=text
                    )
                    embedding = np.array(response.data[0].embedding, dtype='float32')
                    self.embedding_dim = len(embedding)
                    return embedding
            except Exception as e:
                print(f"Error generating embedding: {e}")
                # Return zero vector as fallback
                return np.zeros(self.embedding_dim, dtype='float32')
    
    def index_regulations(self, regulations: List[Dict]) -> int:
        """
        Index regulations in vector database
        Returns number of regulations indexed
        """
        if not regulations:
            return 0
        
        print(f"Indexing {len(regulations)} regulations...")
        
        # Prepare embeddings
        embeddings = []
        metadata = []
        
        for reg in regulations:
            # Create searchable text
            searchable_text = self._create_searchable_text(reg)
            
            # Generate embedding
            embedding = self._generate_embedding(searchable_text)
            embeddings.append(embedding)
            
            # Store metadata
            metadata.append({
                'id': reg.get('id', len(metadata)),
                'chapter': reg.get('chapter', ''),
                'subchapter': reg.get('subchapter', ''),
                'part': reg.get('part', ''),
                'description': reg.get('description', '')[:500],
                'status': reg.get('status', 'Unknown'),
                'url': reg.get('url', ''),
                'section_range': reg.get('section_range', ''),
                'title': reg.get('title', 'Title 21')
            })
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create or update FAISS index
        if self.index is None:
            # Create new index
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # Add embeddings to index
        self.index.add(embeddings_array)
        self.regulations_metadata = metadata
        self.is_indexed = True
        
        # Save to disk
        self._save_index()
        
        print(f"✅ Successfully indexed {len(regulations)} regulations")
        return len(regulations)
    
    def _create_searchable_text(self, reg: Dict) -> str:
        """Create searchable text from regulation"""
        parts = []
        
        if reg.get('part'):
            parts.append(f"Part {reg['part']}")
        if reg.get('chapter'):
            parts.append(f"Chapter {reg['chapter']}")
        if reg.get('subchapter'):
            parts.append(f"Subchapter {reg['subchapter']}")
        if reg.get('description'):
            parts.append(reg['description'])
        if reg.get('section_range'):
            parts.append(f"Sections {reg['section_range']}")
        
        return " | ".join(parts)
    
    def semantic_search(
        self, 
        query: str, 
        n_results: int = 10,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Perform semantic search on regulations
        Returns list of regulations ordered by relevance
        """
        if not self.is_indexed or self.index is None:
            print("⚠️  Vector database not indexed. Returning empty results.")
            return []
        
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            query_embedding = query_embedding.reshape(1, -1).astype('float32')
            
            # Search in FAISS
            k = min(n_results * 2, len(self.regulations_metadata))  # Get more results for filtering
            distances, indices = self.index.search(query_embedding, k)
            
            # Convert results to regulation format
            regulations = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.regulations_metadata):
                    metadata = self.regulations_metadata[idx]
                    distance = float(distances[0][i])
                    
                    # Apply filters if specified
                    if filter_dict:
                        if 'status' in filter_dict and metadata.get('status') != filter_dict['status']:
                            continue
                        if 'chapter' in filter_dict and metadata.get('chapter') != filter_dict['chapter']:
                            continue
                    
                    # Convert distance to similarity score (lower distance = higher similarity)
                    similarity_score = 1.0 / (1.0 + distance)
                    
                    regulations.append({
                        'id': metadata.get('id', 0),
                        'chapter': metadata.get('chapter', ''),
                        'subchapter': metadata.get('subchapter', ''),
                        'part': metadata.get('part', ''),
                        'description': metadata.get('description', ''),
                        'status': metadata.get('status', 'Unknown'),
                        'url': metadata.get('url', ''),
                        'relevance_score': similarity_score,
                        'section_range': metadata.get('section_range', ''),
                        'title': metadata.get('title', 'Title 21')
                    })
                    
                    if len(regulations) >= n_results:
                        break
            
            return regulations
            
        except Exception as e:
            print(f"Error in semantic search: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def hybrid_search(
        self,
        query: str,
        n_results: int = 10,
        keyword_results: Optional[List[Dict]] = None,
        semantic_weight: float = 0.7
    ) -> List[Dict]:
        """
        Hybrid search combining semantic and keyword search
        semantic_weight: 0.0 = keyword only, 1.0 = semantic only
        """
        # Get semantic results
        semantic_results = self.semantic_search(query, n_results=n_results * 2)
        
        # If no keyword results provided, return semantic only
        if not keyword_results:
            return semantic_results[:n_results]
        
        # Combine results with scoring
        combined = {}
        
        # Add semantic results with weighted scores
        for i, result in enumerate(semantic_results):
            reg_id = result.get('id')
            score = result.get('relevance_score', 0.0) * semantic_weight
            combined[reg_id] = {
                **result,
                'combined_score': score,
                'source': 'semantic'
            }
        
        # Add keyword results with weighted scores
        keyword_weight = 1.0 - semantic_weight
        for i, result in enumerate(keyword_results):
            reg_id = result.get('id')
            # Calculate keyword score (inverse rank)
            keyword_score = keyword_weight * (1.0 / (i + 1))
            
            if reg_id in combined:
                # Combine scores if already in results
                combined[reg_id]['combined_score'] += keyword_score
                combined[reg_id]['source'] = 'both'
            else:
                combined[reg_id] = {
                    **result,
                    'combined_score': keyword_score,
                    'source': 'keyword'
                }
        
        # Sort by combined score and return top N
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x.get('combined_score', 0.0),
            reverse=True
        )
        
        return sorted_results[:n_results]
    
    def get_relevant_context(
        self,
        query: str,
        n_results: int = 5
    ) -> str:
        """
        Get relevant regulation context for LLM
        Returns formatted string with relevant regulations
        """
        results = self.semantic_search(query, n_results=n_results)
        
        if not results:
            return "No relevant regulations found."
        
        context_parts = []
        for i, reg in enumerate(results, 1):
            part_info = []
            if reg.get('chapter'):
                part_info.append(f"Chapter: {reg['chapter']}")
            if reg.get('subchapter'):
                part_info.append(f"Subchapter: {reg['subchapter']}")
            if reg.get('part'):
                part_info.append(f"Part: {reg['part']}")
            
            context_parts.append(
                f"{i}. {' | '.join(part_info)}\n"
                f"   Description: {reg.get('description', 'N/A')}\n"
                f"   Status: {reg.get('status', 'Unknown')}\n"
                f"   Relevance: {reg.get('relevance_score', 0.0):.2f}\n"
            )
        
        return "\n".join(context_parts)
    
    def clear_index(self):
        """Clear all indexed regulations"""
        try:
            self.index = None
            self.regulations_metadata = []
            self.is_indexed = False
            
            # Delete files if they exist
            if os.path.exists(self.index_file):
                os.remove(self.index_file)
            if os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
            
            print("✅ Cleared vector database")
        except Exception as e:
            print(f"Error clearing index: {e}")
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector database"""
        return {
            'indexed_count': len(self.regulations_metadata) if self.regulations_metadata else 0,
            'is_indexed': self.is_indexed,
            'using_local_embeddings': self.use_local_embeddings,
            'embedding_dim': self.embedding_dim
        }
