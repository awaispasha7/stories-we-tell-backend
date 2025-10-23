"""
Knowledge Extraction Worker
Automatically extracts and stores knowledge patterns from conversations
"""

import asyncio
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from ..database.supabase import get_supabase_client
from ..ai.rag_service import rag_service
from ..ai.embedding_service import get_embedding_service


class KnowledgeExtractor:
    """Extracts knowledge patterns from conversations and stores in global knowledge base"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.embedding_service = get_embedding_service()
        
    async def extract_knowledge_from_conversations(self, limit: int = 10):
        """
        Extract knowledge from recent successful conversations
        
        Args:
            limit: Number of conversations to process
        """
        try:
            print(f"🧠 Knowledge Extractor: Starting knowledge extraction...")
            
            # Get recent conversations that haven't been processed for knowledge extraction
            conversations = await self._get_recent_conversations(limit)
            
            if not conversations:
                print("🧠 No conversations found for knowledge extraction")
                return
            
            print(f"🧠 Processing {len(conversations)} conversations for knowledge extraction")
            
            for conversation in conversations:
                try:
                    await self._extract_knowledge_from_conversation(conversation)
                except Exception as e:
                    print(f"❌ Error extracting knowledge from conversation {conversation.get('session_id')}: {e}")
                    continue
            
            print(f"✅ Knowledge extraction completed for {len(conversations)} conversations")
            
        except Exception as e:
            print(f"❌ Error in knowledge extraction: {e}")
    
    async def _get_recent_conversations(self, limit: int) -> List[Dict[str, Any]]:
        """Get recent conversations that are good candidates for knowledge extraction"""
        try:
            # Get sessions with multiple messages (indicating successful conversations)
            result = self.supabase.rpc(
                'get_conversations_for_knowledge_extraction',
                {
                    'result_limit': limit,
                    'min_messages': 4,  # At least 4 messages (2 user + 2 assistant)
                    'days_back': 7     # Last 7 days
                }
            ).execute()
            
            if result.data:
                return result.data
            return []
            
        except Exception as e:
            print(f"❌ Error getting recent conversations: {e}")
            return []
    
    async def _extract_knowledge_from_conversation(self, conversation: Dict[str, Any]):
        """Extract knowledge patterns from a single conversation"""
        try:
            session_id = conversation['session_id']
            user_id = conversation['user_id']
            project_id = conversation['project_id']
            
            # Get all messages for this conversation
            messages_result = self.supabase.table("chat_messages")\
                .select("*")\
                .eq("session_id", session_id)\
                .order("created_at")\
                .execute()
            
            if not messages_result.data or len(messages_result.data) < 4:
                return
            
            messages = messages_result.data
            
            # Extract different types of knowledge
            await self._extract_character_knowledge(messages, user_id, project_id)
            await self._extract_plot_knowledge(messages, user_id, project_id)
            await self._extract_dialogue_knowledge(messages, user_id, project_id)
            await self._extract_setting_knowledge(messages, user_id, project_id)
            
            # Note: We don't mark conversations as processed since sessions table doesn't have metadata column
            # This means conversations might be processed multiple times, but that's okay for now
            
        except Exception as e:
            print(f"❌ Error extracting knowledge from conversation: {e}")
    
    async def _extract_character_knowledge(self, messages: List[Dict], user_id: str, project_id: str):
        """Extract character development patterns"""
        try:
            character_keywords = ['character', 'protagonist', 'hero', 'villain', 'personality', 'trait', 'backstory']
            
            for message in messages:
                if message['role'] == 'user':
                    content = message['content'].lower()
                    if any(keyword in content for keyword in character_keywords):
                        # Extract character-related patterns
                        embedding = await self.embedding_service.generate_embedding(message['content'])
                        
                        await rag_service.vector_storage.store_global_knowledge(
                            category='character',
                            pattern_type='character_development',
                            embedding=embedding,
                            example_text=message['content'][:500],  # Truncate for storage
                            description=f"Character development pattern from user conversation",
                            quality_score=0.7,
                            tags=['auto_extracted', 'character']
                        )
                        
        except Exception as e:
            print(f"❌ Error extracting character knowledge: {e}")
    
    async def _extract_plot_knowledge(self, messages: List[Dict], user_id: str, project_id: str):
        """Extract plot development patterns"""
        try:
            plot_keywords = ['plot', 'story', 'conflict', 'climax', 'resolution', 'twist', 'ending']
            
            for message in messages:
                if message['role'] == 'user':
                    content = message['content'].lower()
                    if any(keyword in content for keyword in plot_keywords):
                        embedding = await self.embedding_service.generate_embedding(message['content'])
                        
                        await rag_service.vector_storage.store_global_knowledge(
                            category='plot',
                            pattern_type='plot_development',
                            embedding=embedding,
                            example_text=message['content'][:500],
                            description=f"Plot development pattern from user conversation",
                            quality_score=0.7,
                            tags=['auto_extracted', 'plot']
                        )
                        
        except Exception as e:
            print(f"❌ Error extracting plot knowledge: {e}")
    
    async def _extract_dialogue_knowledge(self, messages: List[Dict], user_id: str, project_id: str):
        """Extract dialogue patterns"""
        try:
            dialogue_keywords = ['dialogue', 'conversation', 'speech', 'quote', 'said', 'told']
            
            for message in messages:
                if message['role'] == 'user':
                    content = message['content'].lower()
                    if any(keyword in content for keyword in dialogue_keywords):
                        embedding = await self.embedding_service.generate_embedding(message['content'])
                        
                        await rag_service.vector_storage.store_global_knowledge(
                            category='dialogue',
                            pattern_type='dialogue_development',
                            embedding=embedding,
                            example_text=message['content'][:500],
                            description=f"Dialogue pattern from user conversation",
                            quality_score=0.6,
                            tags=['auto_extracted', 'dialogue']
                        )
                        
        except Exception as e:
            print(f"❌ Error extracting dialogue knowledge: {e}")
    
    async def _extract_setting_knowledge(self, messages: List[Dict], user_id: str, project_id: str):
        """Extract setting and world-building patterns"""
        try:
            setting_keywords = ['setting', 'world', 'place', 'location', 'time', 'era', 'environment']
            
            for message in messages:
                if message['role'] == 'user':
                    content = message['content'].lower()
                    if any(keyword in content for keyword in setting_keywords):
                        embedding = await self.embedding_service.generate_embedding(message['content'])
                        
                        await rag_service.vector_storage.store_global_knowledge(
                            category='setting',
                            pattern_type='world_building',
                            embedding=embedding,
                            example_text=message['content'][:500],
                            description=f"Setting pattern from user conversation",
                            quality_score=0.6,
                            tags=['auto_extracted', 'setting']
                        )
                        
        except Exception as e:
            print(f"❌ Error extracting setting knowledge: {e}")
    


# Global instance
knowledge_extractor = KnowledgeExtractor()


async def run_knowledge_extraction():
    """Run knowledge extraction process"""
    while True:
        try:
            await knowledge_extractor.extract_knowledge_from_conversations(limit=5)
            # Run every 2 hours
            await asyncio.sleep(7200)
        except Exception as e:
            print(f"❌ Error in knowledge extraction worker: {e}")
            await asyncio.sleep(3600)  # Wait 1 hour on error
