import asyncio
import os
from dotenv import load_dotenv
from app.ai.rag_service import rag_service
from uuid import uuid4

# Load environment variables from .env file
load_dotenv()

async def test_rag():
    # Test embedding generation
    print("1. Testing embedding service...")
    from app.ai.embedding_service import embedding_service
    embedding = await embedding_service.generate_embedding("Hello, this is a test message about a brave knight.")
    print(f"✅ Generated embedding with {len(embedding)} dimensions")
    
    # Test storing an embedding
    print("\n2. Testing vector storage...")
    test_user_id = uuid4()
    test_project_id = uuid4()
    test_session_id = uuid4()
    test_message_id = uuid4()
    
    success = await rag_service.embed_and_store_message(
        message_id=test_message_id,
        user_id=test_user_id,
        project_id=test_project_id,
        session_id=test_session_id,
        content="The brave knight embarked on a quest to save the kingdom.",
        role="user"
    )
    print(f"✅ Stored embedding: {success}")
    
    # Test RAG context retrieval
    print("\n3. Testing RAG context retrieval...")
    context = await rag_service.get_rag_context(
        user_message="Tell me about the knight's journey",
        user_id=test_user_id,
        project_id=test_project_id
    )
    print(f"✅ Retrieved context:")
    print(f"   - User contexts: {context['metadata']['user_context_count']}")
    print(f"   - Global contexts: {context['metadata']['global_context_count']}")
    
    print("\n✅ All RAG services working!")

if __name__ == "__main__":
    asyncio.run(test_rag())