"""
RAG (Retrieval Augmented Generation) Service
Combines embedding generation, vector search, and context building for LLM prompts
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from .embedding_service import get_embedding_service
from .vector_storage import vector_storage
from .document_processor import document_processor


class RAGService:
    """Service for RAG-enhanced chat responses"""
    
    def __init__(self):
        self.embedding_service = None  # Lazy initialization
        self.vector_storage = vector_storage
        
        # Configuration for retrieval
        self.user_context_weight = 0.4  # 40% weight on user-specific context
        self.global_context_weight = 0.3  # 30% weight on global patterns (includes image analysis)
        self.document_context_weight = 0.3  # 30% weight on document context
        self.user_match_count = 15  # Retrieve more user messages for stronger continuity
        self.global_match_count = 5  # A few more global patterns
        self.document_match_count = 6  # Broaden document context (images/docs)
        self.similarity_threshold = 0.05  # Broader net to avoid misses
    
    def _get_embedding_service(self):
        """Lazy initialization of embedding service"""
        if self.embedding_service is None:
            self.embedding_service = get_embedding_service()
        return self.embedding_service
    
    async def get_rag_context(
        self,
        user_message: str,
        user_id: UUID,
        project_id: Optional[UUID] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Get RAG context for a user message
        
        Args:
            user_message: Current user message
            user_id: ID of the user
            project_id: Optional project ID
            conversation_history: Optional recent conversation history
            
        Returns:
            Dict containing:
            - user_context: Relevant user-specific messages
            - global_context: Relevant global knowledge patterns
            - combined_context_text: Formatted context for LLM prompt
            - metadata: Metadata about retrieval
        """
        try:
            print(f"RAG: Building context for user {user_id}")
            
            # Step 1: Generate query embedding (include conversation context if available)
            if conversation_history:
                # Combine recent conversation for better context
                recent_context = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    for msg in conversation_history[-5:]  # include last 5 turns
                ])
                query_text = f"{recent_context}\nUser: {user_message}"
            else:
                query_text = user_message
            
            query_embedding = await self._get_embedding_service().generate_query_embedding(query_text)
            
            # Step 2: Retrieve user-specific context
            user_context = await self.vector_storage.get_similar_user_messages(
                query_embedding=query_embedding,
                user_id=user_id,
                project_id=project_id,
                match_count=self.user_match_count,
                similarity_threshold=self.similarity_threshold
            )
            
            # Step 3: Retrieve global knowledge patterns
            global_context = await self.vector_storage.get_similar_global_knowledge(
                query_embedding=query_embedding,
                match_count=self.global_match_count,
                similarity_threshold=self.similarity_threshold,
                min_quality_score=0.6
            )
            
            # Step 4: Debug - Check if there are any document embeddings for this user
            try:
                from app.database.supabase import get_supabase_client
                supabase = get_supabase_client()
                print(f"🔍 RAG Debug: Querying for user_id: {str(user_id)} (type: {type(user_id)})")
                debug_result = supabase.table('document_embeddings').select('*').eq('user_id', str(user_id)).execute()
                print(f"🔍 RAG Debug: Found {len(debug_result.data)} document embeddings for user {user_id}")
                
                # Also check all embeddings to see what's in the database
                all_embeddings = supabase.table('document_embeddings').select('user_id, asset_id, project_id').execute()
                print(f"🔍 RAG Debug: Total embeddings in database: {len(all_embeddings.data)}")
                for row in all_embeddings.data:
                    print(f"  - User: {row.get('user_id')}, Asset: {row.get('asset_id')}, Project: {row.get('project_id')}")
                
                if debug_result.data:
                    for row in debug_result.data:
                        print(f"  - Asset: {row.get('asset_id')}, Project: {row.get('project_id')}, Type: {row.get('document_type')}")
            except Exception as e:
                print(f"🔍 RAG Debug: Error checking embeddings: {e}")
            
            # Step 4: Retrieve document context (search across all projects for user)
            print(f"🔍 RAG: Calling get_document_context with user_id: {user_id} (type: {type(user_id)})")
            document_context = await document_processor.get_document_context(
                query_embedding=query_embedding,
                user_id=user_id,
                project_id=None,  # Search across all projects for this user
                match_count=self.document_match_count,
                similarity_threshold=self.similarity_threshold
            )
            
            # Step 5: Build combined context text for LLM prompt
            combined_context_text = self._format_rag_context(user_context, global_context, document_context)
            
            # Step 6: Build metadata
            metadata = {
                "user_context_count": len(user_context),
                "global_context_count": len(global_context),
                "document_context_count": len(document_context),
                "query_length": len(user_message),
                "has_conversation_history": bool(conversation_history)
            }
            
            print(f"RAG: Retrieved {len(user_context)} user contexts, {len(global_context)} global patterns, {len(document_context)} document chunks")
            
            return {
                "user_context": user_context,
                "global_context": global_context,
                "document_context": document_context,
                "combined_context_text": combined_context_text,
                "metadata": metadata
            }
            
        except Exception as e:
            print(f"ERROR: Failed to get RAG context: {e}")
            return {
                "user_context": [],
                "global_context": [],
                "document_context": [],
                "combined_context_text": "",
                "metadata": {"error": str(e)}
            }
    
    def _format_rag_context(
        self,
        user_context: List[Dict[str, Any]],
        global_context: List[Dict[str, Any]],
        document_context: List[Dict[str, Any]]
    ) -> str:
        """
        Format retrieved context into a prompt-friendly string
        
        Args:
            user_context: User-specific messages
            global_context: Global knowledge patterns
            document_context: Document chunks
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        # Add user-specific context
        if user_context:
            context_parts.append("## Relevant Context from Your Previous Conversations:")
            for i, item in enumerate(user_context[:5], 1):  # Limit to top 5
                role = item.get('role', 'unknown')
                content = item.get('content', '')
                similarity = item.get('similarity', 0)
                context_parts.append(f"{i}. [{role.upper()}] (relevance: {similarity:.2f}) {content[:200]}...")
            context_parts.append("")
        
        # Add document context
        if document_context:
            context_parts.append("## Relevant Information from Your Uploaded Documents:")
            for i, item in enumerate(document_context, 1):
                doc_type = item.get('document_type', 'unknown')
                chunk_text = item.get('chunk_text', '')
                similarity = item.get('similarity', 0)
                context_parts.append(
                    f"{i}. [{doc_type.upper()}] (relevance: {similarity:.2f}) {chunk_text[:200]}..."
                )
            context_parts.append("")
        
        # Add global knowledge context
        if global_context:
            context_parts.append("## Relevant Storytelling Patterns and Knowledge:")
            for i, item in enumerate(global_context, 1):
                category = item.get('category', 'general')
                pattern = item.get('pattern_type', 'unknown')
                example = item.get('example_text', '')
                similarity = item.get('similarity', 0)
                context_parts.append(
                    f"{i}. [{category}/{pattern}] (relevance: {similarity:.2f}) {example[:150]}..."
                )
            context_parts.append("")
        
        if not context_parts:
            return ""
        
        return "\n".join(context_parts)
    
    async def embed_and_store_message(
        self,
        message_id: UUID,
        user_id: UUID,
        project_id: UUID,
        session_id: UUID,
        content: str,
        role: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Generate and store embedding for a message
        
        Args:
            message_id: ID of the message
            user_id: ID of the user
            project_id: ID of the project
            session_id: ID of the session
            content: Message content
            role: Message role
            metadata: Optional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = await self._get_embedding_service().generate_embedding(content)
            
            # Store embedding
            embedding_id = await self.vector_storage.store_message_embedding(
                message_id=message_id,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                embedding=embedding,
                content=content,
                role=role,
                metadata=metadata
            )
            
            return embedding_id is not None
            
        except Exception as e:
            print(f"ERROR: Failed to embed and store message: {e}")
            return False
    
    async def extract_and_store_knowledge(
        self,
        conversation: List[Dict[str, str]],
        user_id: UUID,
        project_id: UUID
    ):
        """
        Extract knowledge patterns from a conversation and store in global knowledge base
        This is called after successful conversations to build the knowledge base
        
        Args:
            conversation: List of messages in the conversation
            user_id: ID of the user (for attribution, not stored in global KB)
            project_id: ID of the project
        """
        try:
            print(f"RAG: Extracting knowledge from conversation (user: {user_id})")
            
            # Analyze conversation for patterns
            # This is a simplified version - you can make this more sophisticated
            
            # Example: Extract character development patterns
            character_mentions = self._extract_character_patterns(conversation)
            for char_pattern in character_mentions:
                embedding = await self._get_embedding_service().generate_embedding(char_pattern['text'])
                await self.vector_storage.store_global_knowledge(
                    category='character',
                    pattern_type='character_development',
                    embedding=embedding,
                    example_text=char_pattern['text'],
                    description=char_pattern.get('description'),
                    quality_score=0.7,
                    tags=['conversation_extracted']
                )
            
            # Example: Extract plot patterns
            plot_patterns = self._extract_plot_patterns(conversation)
            for plot_pattern in plot_patterns:
                embedding = await self._get_embedding_service().generate_embedding(plot_pattern['text'])
                await self.vector_storage.store_global_knowledge(
                    category='plot',
                    pattern_type='story_arc',
                    embedding=embedding,
                    example_text=plot_pattern['text'],
                    description=plot_pattern.get('description'),
                    quality_score=0.7,
                    tags=['conversation_extracted']
                )
            
            print(f"RAG: Extracted {len(character_mentions)} character patterns, {len(plot_patterns)} plot patterns")
            
        except Exception as e:
            print(f"ERROR: Failed to extract and store knowledge: {e}")
    
    def _extract_character_patterns(self, conversation: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Extract character-related patterns from conversation"""
        patterns = []
        # Simplified extraction - look for character-related keywords
        keywords = ['character', 'protagonist', 'antagonist', 'hero', 'villain']
        
        for msg in conversation:
            content = msg.get('content', '').lower()
            if any(keyword in content for keyword in keywords):
                patterns.append({
                    'text': msg.get('content', '')[:500],
                    'description': 'Character discussion pattern'
                })
        
        return patterns[:3]  # Limit to 3 patterns
    
    def _extract_plot_patterns(self, conversation: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Extract plot-related patterns from conversation"""
        patterns = []
        # Simplified extraction - look for plot-related keywords
        keywords = ['plot', 'story', 'conflict', 'resolution', 'climax', 'arc']
        
        for msg in conversation:
            content = msg.get('content', '').lower()
            if any(keyword in content for keyword in keywords):
                patterns.append({
                    'text': msg.get('content', '')[:500],
                    'description': 'Plot development pattern'
                })
        
        return patterns[:3]  # Limit to 3 patterns


# Global singleton instance
rag_service = RAGService()

