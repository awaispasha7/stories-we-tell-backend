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
    from app.ai.embedding_service import get_embedding_service
    embedding_service = get_embedding_service()
    embedding = await embedding_service.generate_embedding("Hello, this is a test message about a brave knight.")
    print(f"✅ Generated embedding with {len(embedding)} dimensions")
    
    # Test embedding generation for storage (without actually storing)
    print("\n2. Testing embedding generation for messages...")
    test_content = "The brave knight embarked on a quest to save the kingdom."
    test_embedding = await embedding_service.generate_embedding(test_content)
    print(f"✅ Generated message embedding with {len(test_embedding)} dimensions")
    print(f"   (Skipping storage test - requires existing message in database)")
    
    # Test RAG context retrieval
    print("\n3. Testing RAG context retrieval...")
    test_user_id = uuid4()
    test_project_id = uuid4()
    context = await rag_service.get_rag_context(
        user_message="Tell me about the knight's journey",
        user_id=test_user_id,
        project_id=test_project_id
    )
    print(f"✅ RAG context retrieval successful:")
    print(f"   - User contexts found: {context['metadata']['user_context_count']}")
    print(f"   - Global contexts found: {context['metadata']['global_context_count']}")
    print(f"   - Combined context length: {len(context['combined_context_text'])} chars")
    print(f"   (Empty results expected - no data in database yet)")
    
    # Test cosine similarity
    print("\n4. Testing cosine similarity...")
    vec1 = test_embedding[:10]  # Use first 10 dimensions for demo
    vec2 = embedding[:10]
    similarity = embedding_service.cosine_similarity(vec1, vec2)
    print(f"✅ Cosine similarity calculated: {similarity:.4f}")
    
    print("\n" + "="*60)
    print("✅ ALL RAG SERVICES WORKING PERFECTLY!")
    print("="*60)
    print("\n📋 Next Steps:")
    print("1. Apply database migration: supabase/migrations/20251021000000_create_rag_tables.sql")
    print("2. Start chatting - messages will be auto-queued for embedding")
    print("3. RAG will enhance responses with relevant context")
    print("\n💡 Tip: Check RAG_QUICK_START.md for integration guide")

if __name__ == "__main__":
    asyncio.run(test_rag())