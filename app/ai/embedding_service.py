"""
Embedding Service
Handles text embedding generation using OpenAI's text-embedding-3-small model
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
import numpy as np

class EmbeddingService:
    """Service for generating and managing text embeddings"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "text-embedding-3-small"
        self.dimension = 1536  # text-embedding-3-small dimension
        
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Clean and truncate text if necessary (model has 8192 token limit)
            text = text.strip()
            if not text:
                raise ValueError("Cannot generate embedding for empty text")
                
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            print(f"Generated embedding for text (length: {len(text)} chars, embedding dim: {len(embedding)})")
            return embedding
            
        except Exception as e:
            print(f"ERROR: Failed to generate embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            if not texts:
                return []
            
            # Clean texts
            cleaned_texts = [text.strip() for text in texts if text and text.strip()]
            if not cleaned_texts:
                return []
            
            print(f"Generating embeddings for {len(cleaned_texts)} texts...")
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=cleaned_texts,
                encoding_format="float"
            )
            
            embeddings = [item.embedding for item in response.data]
            print(f"SUCCESS: Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            print(f"ERROR: Failed to generate batch embeddings: {e}")
            raise
    
    async def generate_query_embedding(self, query: str, context: Optional[str] = None) -> List[float]:
        """
        Generate embedding optimized for query/search
        
        Args:
            query: Search query text
            context: Optional context to prepend to query
            
        Returns:
            Embedding vector optimized for retrieval
        """
        try:
            # Optionally prepend context for better retrieval
            if context:
                full_query = f"{context}\n\n{query}"
            else:
                full_query = query
            
            return await self.generate_embedding(full_query)
            
        except Exception as e:
            print(f"ERROR: Failed to generate query embedding: {e}")
            raise
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            print(f"ERROR: Failed to calculate cosine similarity: {e}")
            return 0.0
    
    async def embed_conversation_context(
        self, 
        messages: List[Dict[str, str]], 
        max_messages: int = 10
    ) -> Optional[List[float]]:
        """
        Generate embedding for conversation context
        Combines recent messages into a single context embedding
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_messages: Maximum number of messages to include
            
        Returns:
            Embedding vector for the conversation context
        """
        try:
            if not messages:
                return None
            
            # Take last N messages
            recent_messages = messages[-max_messages:]
            
            # Format conversation context
            context_parts = []
            for msg in recent_messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                context_parts.append(f"{role.capitalize()}: {content}")
            
            context_text = "\n".join(context_parts)
            
            return await self.generate_embedding(context_text)
            
        except Exception as e:
            print(f"ERROR: Failed to embed conversation context: {e}")
            return None
    
    async def embed_story_element(
        self,
        element_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[List[float]]:
        """
        Generate embedding for a story element (character, plot, scene, etc.)
        
        Args:
            element_type: Type of element ('character', 'plot', 'scene', 'theme', etc.)
            content: Content to embed
            metadata: Optional metadata to include in embedding
            
        Returns:
            Embedding vector for the story element
        """
        try:
            # Prepend element type for better semantic understanding
            formatted_content = f"[{element_type.upper()}] {content}"
            
            # Optionally include metadata
            if metadata:
                metadata_str = " | ".join([f"{k}: {v}" for k, v in metadata.items() if v])
                formatted_content = f"{formatted_content}\n{metadata_str}"
            
            return await self.generate_embedding(formatted_content)
            
        except Exception as e:
            print(f"ERROR: Failed to embed story element: {e}")
            return None


# Global singleton instance (lazy initialization)
_embedding_service_instance = None

def get_embedding_service():
    """Get or create the embedding service singleton"""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance

# For backward compatibility
embedding_service = None  # Will be initialized on first access

