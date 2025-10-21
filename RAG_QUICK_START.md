# RAG Quick Start Guide

## 🚀 Getting Started in 5 Steps

### Step 1: Apply Database Migration (5 minutes)

**Option A: Using Supabase Dashboard**
1. Go to Supabase Dashboard → SQL Editor
2. Copy contents of `supabase/migrations/20251021000000_create_rag_tables.sql`
3. Paste and run in SQL Editor
4. Verify tables created: `message_embeddings`, `global_knowledge`, `embedding_queue`

**Option B: Using Supabase CLI**
```bash
cd stories-we-tell-backend
supabase db push
```

### Step 2: Install Python Dependencies (2 minutes)

Add to `requirements.txt` (if not already present):
```
openai>=1.3.0
numpy>=1.24.0
```

Then install:
```bash
pip install -r requirements.txt
```

### Step 3: Verify API Keys (1 minute)

Check your `.env` file has:
```env
OPENAI_API_KEY=sk-proj-...  # For embeddings
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
```

✅ **Already configured!** Your keys are set.

### Step 4: Test RAG Services (5 minutes)

Create a test script `test_rag.py`:

```python
import asyncio
from app.ai.rag_service import rag_service
from uuid import uuid4

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
```

Run:
```bash
python test_rag.py
```

### Step 5: Basic Integration (10 minutes)

The RAG services are ready to use! Here's a minimal integration example:

```python
# In chat_sessions.py, inside generate_stream() function:

# After getting conversation history, before AI call:
from ..ai.rag_service import rag_service

if user_id:  # Only use RAG for authenticated users
    try:
        rag_context = await rag_service.get_rag_context(
            user_message=text,
            user_id=user_id,
            project_id=session.project_id,
            conversation_history=history_for_ai[-5:]  # Last 5 messages
        )
        
        if rag_context['combined_context_text']:
            # Inject context into system message
            system_message = {
                "role": "system",
                "content": f"""You are a creative storytelling assistant.

{rag_context['combined_context_text']}

Use the above context to provide personalized, contextually-aware responses."""
            }
            history_for_ai.insert(0, system_message)
            print(f"RAG: Injected context with {rag_context['metadata']['user_context_count']} user contexts")
    except Exception as e:
        print(f"RAG: Failed to get context (continuing without RAG): {e}")

# Continue with existing AI call...
```

## 🎯 What You Get Immediately

### ✅ Working Now:
1. **Automatic Embedding**: New messages are auto-queued for embedding
2. **Vector Search**: Can search for similar user messages and global patterns
3. **Context Building**: Formatted context ready for LLM prompts
4. **Two-Tier Storage**: User-specific + global knowledge base

### 🔄 To Enable Later:
1. **Background Worker**: Process embedding queue in background
2. **Knowledge Extraction**: Auto-extract patterns from good conversations
3. **Advanced Routing**: Route to different AI models based on task

## 📊 Monitoring

Check your tables in Supabase Dashboard:

```sql
-- Check embedding queue
SELECT status, COUNT(*) FROM embedding_queue GROUP BY status;

-- Check stored embeddings
SELECT COUNT(*) FROM message_embeddings;

-- Check global knowledge
SELECT category, COUNT(*) FROM global_knowledge GROUP BY category;
```

## 🔧 Configuration

Adjust RAG behavior in `app/ai/rag_service.py`:

```python
class RAGService:
    def __init__(self):
        # Adjust these values:
        self.user_context_weight = 0.7  # 70% weight on user context
        self.global_context_weight = 0.3  # 30% weight on global
        self.user_match_count = 8  # Number of similar user messages
        self.global_match_count = 3  # Number of global patterns
        self.similarity_threshold = 0.6  # Minimum similarity (0-1)
```

## 🚨 Troubleshooting

**Issue**: Migration fails with "extension vector does not exist"
```sql
-- Run this first:
CREATE EXTENSION IF NOT EXISTS vector;
```

**Issue**: "Cannot import embedding_service"
```bash
# Make sure you're in the correct directory:
cd stories-we-tell-backend
python -m app.ai.embedding_service
```

**Issue**: OpenAI API errors
- Check API key is valid
- Check you have credits
- Check rate limits

## 📈 Next Steps

1. **Test with real conversations** - Start chatting and see embeddings being created
2. **Monitor performance** - Watch embedding queue and search latency
3. **Tune parameters** - Adjust similarity thresholds based on results
4. **Add background worker** - Process embeddings asynchronously
5. **Build global KB** - Let it learn from conversations over time

## ✨ Expected Results

After a few conversations:
- Context retrieval will surface relevant past messages
- Responses will be more consistent with user's story
- Knowledge base will start building patterns
- Each chat will benefit from previous conversations

---

**Need help?** Check `RAG_IMPLEMENTATION.md` for detailed documentation.

