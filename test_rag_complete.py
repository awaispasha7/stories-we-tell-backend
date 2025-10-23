#!/usr/bin/env python3
"""
Complete RAG System Test
Tests all RAG components: embedding service, vector storage, RAG service, and knowledge extraction
"""

import asyncio
import os
import sys
from uuid import uuid4, UUID
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

async def test_rag_system():
    """Test the complete RAG system"""
    print("Testing Complete RAG System")
    print("=" * 60)
    
    # Test 1: Embedding Service
    print("\n1. Testing Embedding Service...")
    try:
        from app.ai.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()
        
        test_text = "I'm writing a story about a brave knight who saves a princess"
        embedding = await embedding_service.generate_embedding(test_text)
        
        if embedding and len(embedding) == 1536:
            print(f"SUCCESS: Embedding service working - Generated {len(embedding)}-dimensional vector")
        else:
            print(f"FAILED: Embedding service failed - Got {len(embedding) if embedding else 0} dimensions")
            return False
            
    except Exception as e:
        print(f"ERROR: Embedding service error: {e}")
        return False
    
    # Test 2: Vector Storage
    print("\n2. Testing Vector Storage...")
    try:
        from app.ai.vector_storage import vector_storage
        
        # Test storing a message embedding
        test_user_id = UUID(str(uuid4()))
        test_project_id = UUID(str(uuid4()))
        test_session_id = UUID(str(uuid4()))
        test_message_id = UUID(str(uuid4()))
        
        result = await vector_storage.store_message_embedding(
            message_id=test_message_id,
            user_id=test_user_id,
            project_id=test_project_id,
            session_id=test_session_id,
            embedding=embedding,
            content=test_text,
            role="user",
            metadata={"test": True}
        )
        
        if result:
            print(f"SUCCESS: Vector storage working - Stored embedding with ID: {result}")
        else:
            print("FAILED: Vector storage failed - No embedding ID returned")
            return False
            
    except Exception as e:
        print(f"ERROR: Vector storage error: {e}")
        return False
    
    # Test 3: RAG Service
    print("\n3. Testing RAG Service...")
    try:
        from app.ai.rag_service import rag_service
        
        # Test getting RAG context
        rag_context = await rag_service.get_rag_context(
            user_message="Tell me about character development",
            user_id=test_user_id,
            project_id=test_project_id,
            conversation_history=[]
        )
        
        if rag_context:
            print(f"SUCCESS: RAG service working - Retrieved context:")
            print(f"   - User context: {rag_context.get('user_context_count', 0)} items")
            print(f"   - Global context: {rag_context.get('global_context_count', 0)} items")
            print(f"   - Document context: {rag_context.get('document_context_count', 0)} items")
        else:
            print("FAILED: RAG service failed - No context returned")
            return False
            
    except Exception as e:
        print(f"ERROR: RAG service error: {e}")
        return False
    
    # Test 4: Document Processor
    print("\n4. Testing Document Processor...")
    try:
        from app.ai.document_processor import document_processor
        
        # Test processing a simple text document
        test_content = "This is a test document about a brave knight. The knight has a sword and shield. He fights dragons to save the kingdom."
        
        result = await document_processor.process_document(
            asset_id=UUID(str(uuid4())),
            user_id=test_user_id,
            project_id=test_project_id,
            content=test_content,
            filename="test_document.txt",
            content_type="text/plain"
        )
        
        if result:
            print(f"SUCCESS: Document processor working - Processed {result.get('chunks_created', 0)} chunks")
        else:
            print("FAILED: Document processor failed - No result returned")
            return False
            
    except Exception as e:
        print(f"ERROR: Document processor error: {e}")
        return False
    
    # Test 5: Knowledge Extractor
    print("\n5. Testing Knowledge Extractor...")
    try:
        from app.workers.knowledge_extractor import knowledge_extractor
        
        # Test knowledge extraction (this will be empty initially)
        await knowledge_extractor.extract_knowledge_from_conversations(limit=1)
        print("SUCCESS: Knowledge extractor working - No errors during extraction")
        
    except Exception as e:
        print(f"ERROR: Knowledge extractor error: {e}")
        return False
    
    # Test 6: Database Functions
    print("\n6. Testing Database Functions...")
    try:
        from app.database.supabase import get_supabase_client
        supabase = get_supabase_client()
        
        # Test if RAG functions exist
        functions_to_test = [
            'get_similar_user_messages',
            'get_similar_global_knowledge', 
            'get_similar_document_chunks',
            'get_conversations_for_knowledge_extraction'
        ]
        
        for func_name in functions_to_test:
            try:
                # Try to call the function with minimal parameters
                if func_name == 'get_similar_user_messages':
                    result = supabase.rpc(func_name, {
                        'query_embedding': embedding,
                        'query_user_id': str(test_user_id),
                        'match_count': 1
                    }).execute()
                elif func_name == 'get_similar_global_knowledge':
                    result = supabase.rpc(func_name, {
                        'query_embedding': embedding,
                        'match_count': 1
                    }).execute()
                elif func_name == 'get_similar_document_chunks':
                    result = supabase.rpc(func_name, {
                        'query_embedding': embedding,
                        'query_user_id': str(test_user_id),
                        'match_count': 1
                    }).execute()
                elif func_name == 'get_conversations_for_knowledge_extraction':
                    result = supabase.rpc(func_name, {
                        'result_limit': 1,
                        'min_messages': 2,
                        'days_back': 7
                    }).execute()
                
                print(f"SUCCESS: Function {func_name} exists and callable")
                
            except Exception as e:
                print(f"ERROR: Function {func_name} error: {e}")
                return False
                
    except Exception as e:
        print(f"ERROR: Database functions error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("ALL RAG COMPONENTS WORKING PERFECTLY!")
    print("=" * 60)
    
    print("\nRAG System Status:")
    print("SUCCESS: Embedding Service - OpenAI text-embedding-3-small")
    print("SUCCESS: Vector Storage - Supabase pgvector")
    print("SUCCESS: RAG Service - Context retrieval and building")
    print("SUCCESS: Document Processor - File processing and chunking")
    print("SUCCESS: Knowledge Extractor - Pattern learning from conversations")
    print("SUCCESS: Database Functions - Vector similarity search")
    
    print("\nYour RAG system is fully operational!")
    print("Start chatting to see RAG-enhanced responses")
    print("Upload documents to enable document-aware AI")
    print("The system will learn from conversations over time")
    
    return True

async def main():
    """Main test function"""
    try:
        success = await test_rag_system()
        if success:
            print("\n✅ RAG system test completed successfully!")
            return 0
        else:
            print("\n❌ RAG system test failed!")
            return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
