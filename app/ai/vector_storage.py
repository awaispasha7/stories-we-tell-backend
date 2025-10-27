"""
Vector Storage Service
Handles storing and retrieving embeddings from Supabase
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from ..database.supabase import get_supabase_client


class VectorStorageService:
    """Service for storing and managing embeddings in Supabase"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def store_message_embedding(
        self,
        message_id: UUID,
        user_id: UUID,
        project_id: UUID,
        session_id: UUID,
        embedding: List[float],
        content: str,
        role: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UUID]:
        """
        Store embedding for a chat message
        
        Args:
            message_id: ID of the message
            user_id: ID of the user
            project_id: ID of the project
            session_id: ID of the session
            embedding: Embedding vector
            content: Message content (truncated to 500 chars for snippet)
            role: Message role ('user', 'assistant', 'system')
            metadata: Optional metadata
            
        Returns:
            ID of the created embedding record
        """
        try:
            # Truncate content for snippet
            content_snippet = content[:500] if len(content) > 500 else content
            
            embedding_data = {
                "embedding_id": str(uuid4()),
                "message_id": str(message_id),
                "user_id": str(user_id),
                "project_id": str(project_id),
                "session_id": str(session_id),
                "embedding": embedding,
                "content_snippet": content_snippet,
                "role": role,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("message_embeddings").insert([embedding_data]).execute()
            
            if result.data:
                print(f"SUCCESS: Stored embedding for message {message_id}")
                return UUID(result.data[0]["embedding_id"])
            else:
                print(f"ERROR: Failed to store embedding for message {message_id}")
                return None
                
        except Exception as e:
            print(f"ERROR: Failed to store message embedding: {e}")
            return None
    
    async def get_similar_user_messages(
        self,
        query_embedding: List[float],
        user_id: UUID,
        project_id: Optional[UUID] = None,
        match_count: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar messages for a user using vector similarity search
        
        Args:
            query_embedding: Query embedding vector
            user_id: ID of the user
            project_id: Optional project ID to filter by
            match_count: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of similar messages with similarity scores
        """
        try:
            # Call the Supabase function
            result = self.supabase.rpc(
                'get_similar_user_messages',
                {
                    'query_embedding': query_embedding,
                    'query_user_id': str(user_id),
                    'query_project_id': str(project_id) if project_id else None,
                    'match_count': match_count,
                    'similarity_threshold': similarity_threshold
                }
            ).execute()
            
            if result.data:
                print(f"SUCCESS: Found {len(result.data)} similar user messages")
                # Debug: Check user isolation
                for message in result.data:
                    msg_user_id = message.get('user_id')
                    if msg_user_id != str(user_id):
                        print(f"🚨 SECURITY WARNING: Found message from different user! Expected: {user_id}, Found: {msg_user_id}")
                return result.data
            else:
                print("INFO: No similar user messages found")
                return []
                
        except Exception as e:
            print(f"ERROR: Failed to retrieve similar user messages: {e}")
            return []
    
    async def get_similar_global_knowledge(
        self,
        query_embedding: List[float],
        match_count: int = 5,
        similarity_threshold: float = 0.7,
        min_quality_score: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar patterns from global knowledge base
        
        Args:
            query_embedding: Query embedding vector
            match_count: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            min_quality_score: Minimum quality score (0-1)
            
        Returns:
            List of similar knowledge patterns with similarity scores
        """
        try:
            result = self.supabase.rpc(
                'get_similar_global_knowledge',
                {
                    'query_embedding': query_embedding,
                    'match_count': match_count,
                    'similarity_threshold': similarity_threshold,
                    'min_quality_score': min_quality_score
                }
            ).execute()
            
            if result.data:
                print(f"SUCCESS: Found {len(result.data)} similar global knowledge items")
                return result.data
            else:
                print("INFO: No similar global knowledge found")
                return []
                
        except Exception as e:
            print(f"ERROR: Failed to retrieve similar global knowledge: {e}")
            return []
    
    async def store_global_knowledge(
        self,
        category: str,
        pattern_type: str,
        embedding: List[float],
        example_text: str,
        description: Optional[str] = None,
        quality_score: float = 0.5,
        tags: Optional[List[str]] = None
    ) -> Optional[UUID]:
        """
        Store a pattern in the global knowledge base
        
        Args:
            category: Category of knowledge ('character', 'plot', etc.)
            pattern_type: Type of pattern ('story_arc', 'character_development', etc.)
            embedding: Embedding vector
            example_text: Example text demonstrating the pattern
            description: Optional description
            quality_score: Quality score (0-1)
            tags: Optional tags
            
        Returns:
            ID of the created knowledge record
        """
        try:
            knowledge_data = {
                "knowledge_id": str(uuid4()),
                "category": category,
                "pattern_type": pattern_type,
                "embedding": embedding,
                "example_text": example_text,
                "description": description,
                "quality_score": quality_score,
                "tags": tags or [],
                "usage_count": 1,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("global_knowledge").insert([knowledge_data]).execute()
            
            if result.data:
                print(f"SUCCESS: Stored global knowledge pattern ({category}/{pattern_type})")
                return UUID(result.data[0]["knowledge_id"])
            else:
                print(f"ERROR: Failed to store global knowledge")
                return None
                
        except Exception as e:
            print(f"ERROR: Failed to store global knowledge: {e}")
            return None
    
    async def update_knowledge_usage(self, knowledge_id: UUID):
        """
        Increment usage count for a knowledge pattern
        
        Args:
            knowledge_id: ID of the knowledge record
        """
        try:
            self.supabase.rpc(
                'increment',
                {
                    'row_id': str(knowledge_id),
                    'table_name': 'global_knowledge',
                    'column_name': 'usage_count'
                }
            ).execute()
            
        except Exception as e:
            print(f"ERROR: Failed to update knowledge usage: {e}")
    
    async def get_pending_embeddings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get pending messages from embedding queue
        
        Args:
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of pending embedding queue items
        """
        try:
            result = self.supabase.table("embedding_queue")\
                .select("*")\
                .eq("status", "pending")\
                .order("created_at")\
                .limit(limit)\
                .execute()
            
            if result.data:
                return result.data
            return []
                
        except Exception as e:
            print(f"ERROR: Failed to get pending embeddings: {e}")
            return []
    
    async def store_document_embedding(
        self,
        asset_id: UUID,
        user_id: UUID,
        project_id: UUID,
        document_type: str,
        chunk_index: int,
        chunk_text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UUID]:
        """
        Store embedding for a document chunk
        
        Args:
            asset_id: ID of the asset
            user_id: ID of the user
            project_id: ID of the project
            document_type: Type of document ('pdf', 'docx', 'txt', etc.)
            chunk_index: Index of the chunk within the document
            chunk_text: Text content of the chunk
            embedding: Embedding vector
            metadata: Optional metadata
            
        Returns:
            ID of the created embedding record
        """
        try:
            embedding_data = {
                "embedding_id": str(uuid4()),
                "asset_id": str(asset_id),
                "user_id": str(user_id),
                "project_id": str(project_id),
                "document_type": document_type,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "embedding": embedding,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            print(f"🔍 VectorStorage: Storing embedding with user_id: {str(user_id)}")
            print(f"🔍 VectorStorage: Embedding data user_id: {embedding_data['user_id']}")
            
            result = self.supabase.table("document_embeddings").insert([embedding_data]).execute()
            
            if result.data:
                print(f"SUCCESS: Stored document embedding for asset {asset_id}, chunk {chunk_index}")
                print(f"🔍 VectorStorage: Stored with user_id: {result.data[0].get('user_id')}")
                return UUID(result.data[0]["embedding_id"])
            else:
                print(f"ERROR: Failed to store document embedding for asset {asset_id}")
                return None
                
        except Exception as e:
            print(f"ERROR: Failed to store document embedding: {e}")
            return None

    async def update_queue_status(
        self,
        queue_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update status of an embedding queue item
        
        Args:
            queue_id: ID of the queue item
            status: New status ('processing', 'completed', 'failed')
            error_message: Optional error message for failed items
        """
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if error_message:
                update_data["error_message"] = error_message
            
            if status == "failed":
                # Increment retry count
                result = self.supabase.table("embedding_queue")\
                    .select("retry_count")\
                    .eq("queue_id", str(queue_id))\
                    .execute()
                
                if result.data:
                    current_retries = result.data[0].get("retry_count", 0)
                    update_data["retry_count"] = current_retries + 1
            
            self.supabase.table("embedding_queue")\
                .update(update_data)\
                .eq("queue_id", str(queue_id))\
                .execute()
                
        except Exception as e:
            print(f"ERROR: Failed to update queue status: {e}")


# Convenience function for storing image analysis in RAG
async def store_global_knowledge(content: str, metadata: Dict[str, Any]) -> Optional[UUID]:
    """
    Convenience function to store image analysis in global knowledge base
    
    Args:
        content: The image analysis content
        metadata: Metadata including type, image_type, asset_id, etc.
        
    Returns:
        ID of the created knowledge record
    """
    try:
        from .embedding_service import get_embedding_service
        
        # Get embedding for the content
        embedding_service = get_embedding_service()
        embedding = await embedding_service.generate_embedding(content)
        
        # Extract metadata
        image_type = metadata.get("image_type", "general")
        asset_id = metadata.get("asset_id", "unknown")
        
        # Store in global knowledge using existing schema
        return await vector_storage.store_global_knowledge(
            category="image_analysis",
            pattern_type=image_type,
            embedding=embedding,
            example_text=content,
            description=f"Image analysis for {image_type} (Asset: {asset_id})",
            quality_score=0.8,  # High quality for AI-generated analysis
            tags=[image_type, "ai_analysis", "image"]
        )
        
    except Exception as e:
        print(f"ERROR: Failed to store image analysis in RAG: {e}")
        return None

# Global singleton instance
vector_storage = VectorStorageService()

