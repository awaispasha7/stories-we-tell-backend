# RAG (Retrieval Augmented Generation) Implementation

## 🎯 Overview

This document describes the RAG implementation for the Stories We Tell chatbot. RAG enhances AI responses by retrieving relevant context from:
1. **User-specific conversations** (70% weight) - Personalized context
2. **Global knowledge base** (30% weight) - Aggregated patterns from all users

## 📊 Architecture

```
User Message → Generate Embedding → Vector Search → Build Context → LLM Response
                                     ↓
                              [Two-tier Storage]
                              ├─ message_embeddings (user-specific)
                              └─ global_knowledge (anonymized patterns)
```

## 🗄️ Database Schema

### Tables Created

1. **`message_embeddings`** - User-specific message embeddings
   - Stores 1536-dim vectors for each chat message
   - Linked to user_id, project_id, session_id
   - Enables personalized context retrieval

2. **`global_knowledge`** - Anonymized knowledge patterns
   - Stores storytelling patterns extracted from conversations
   - Categories: character, plot, dialogue, setting, theme
   - Quality-scored and usage-tracked

3. **`embedding_queue`** - Background processing queue
   - Auto-queues new messages for embedding
   - Status tracking: pending → processing → completed/failed
   - Retry mechanism for failed embeddings

### Functions Created

1. **`get_similar_user_messages()`** - Cosine similarity search for user context
2. **`get_similar_global_knowledge()`** - Global pattern retrieval
3. **`queue_message_for_embedding()`** - Auto-queue trigger

## 🔧 Services Implemented

### 1. Embedding Service (`app/ai/embedding_service.py`)

**Key Features:**
- Uses OpenAI `text-embedding-3-small` (1536 dimensions)
- Batch embedding generation for efficiency
- Query-optimized embeddings with context
- Conversation context embedding
- Story element embedding (character, plot, etc.)

**Main Methods:**
```python
- generate_embedding(text) → List[float]
- generate_embeddings_batch(texts) → List[List[float]]
- generate_query_embedding(query, context) → List[float]
- embed_conversation_context(messages) → List[float]
- embed_story_element(type, content, metadata) → List[float]
- cosine_similarity(vec1, vec2) → float
```

### 2. Vector Storage Service (`app/ai/vector_storage.py`)

**Key Features:**
- Stores embeddings in Supabase with pgvector
- IVFFlat indexing for fast similarity search
- User-specific and global knowledge storage
- Queue management for background processing

**Main Methods:**
```python
- store_message_embedding(message_id, user_id, ...) → UUID
- get_similar_user_messages(query_embedding, user_id, ...) → List[Dict]
- get_similar_global_knowledge(query_embedding, ...) → List[Dict]
- store_global_knowledge(category, pattern_type, ...) → UUID
- get_pending_embeddings(limit) → List[Dict]
- update_queue_status(queue_id, status, ...)
```

### 3. RAG Service (`app/ai/rag_service.py`)

**Key Features:**
- Combines embedding + retrieval + context building
- Weighted context (70% user, 30% global)
- Automatic knowledge extraction from conversations
- Formatted context for LLM prompts

**Main Methods:**
```python
- get_rag_context(user_message, user_id, ...) → Dict
- embed_and_store_message(message_id, user_id, ...) → bool
- extract_and_store_knowledge(conversation, user_id, ...)
```

## 🚀 Next Steps (To Complete)

### 1. Run the Migration
```sql
-- Apply the migration to create tables
psql -h <supabase-host> -U postgres -d postgres -f supabase/migrations/20251021000000_create_rag_tables.sql
```

Or use Supabase CLI:
```bash
supabase db push
```

### 2. Integrate RAG into Chat Pipeline

In `chat_sessions.py`, add RAG context retrieval:

```python
from ..ai.rag_service import rag_service

# In generate_stream():
# After getting conversation history
rag_context = await rag_service.get_rag_context(
    user_message=text,
    user_id=user_id,
    project_id=session.project_id,
    conversation_history=history_for_ai
)

# Inject RAG context into system prompt
if rag_context['combined_context_text']:
    system_prompt = f"""You are a creative storytelling assistant.

{rag_context['combined_context_text']}

Help the user develop their story using the context above."""
    
    history_for_ai.insert(0, {"role": "system", "content": system_prompt})
```

### 3. Add Background Embedding Worker

Create a background job to process the embedding queue:

```python
# app/workers/embedding_worker.py
import asyncio
from ..ai.rag_service import rag_service
from ..database.supabase import get_supabase_client

async def process_embedding_queue():
    while True:
        try:
            pending = await vector_storage.get_pending_embeddings(limit=10)
            
            for item in pending:
                await vector_storage.update_queue_status(
                    item['queue_id'], 'processing'
                )
                
                # Get message content
                message = supabase.table("chat_messages")\
                    .select("*")\
                    .eq("message_id", item['message_id'])\
                    .execute()
                
                if message.data:
                    msg = message.data[0]
                    success = await rag_service.embed_and_store_message(
                        message_id=msg['message_id'],
                        user_id=item['user_id'],
                        project_id=item['project_id'],
                        session_id=msg['session_id'],
                        content=msg['content'],
                        role=msg['role']
                    )
                    
                    status = 'completed' if success else 'failed'
                    await vector_storage.update_queue_status(
                        item['queue_id'], status
                    )
            
            await asyncio.sleep(5)  # Wait 5 seconds between batches
            
        except Exception as e:
            print(f"ERROR in embedding worker: {e}")
            await asyncio.sleep(10)
```

### 4. Configure API Keys for Different Models

Based on the client's specifications:
- **GPT-5 Nano/Mini**: For chat responses
- **Gemini**: For description/dossier files
- **GPT**: For scripts  
- **GPT/Claude**: For scenes

Update `app/ai/models.py` to route to the correct model based on task type.

## 📈 Benefits

1. **Personalized Context**: Each user gets responses informed by their previous conversations
2. **Cross-User Learning**: Global patterns help new users benefit from collective knowledge
3. **Scalable**: Background processing doesn't slow down chat responses
4. **Quality Control**: Knowledge base has quality scores to filter low-quality patterns
5. **Privacy-Aware**: User-specific data is isolated; global KB is anonymized

## 🔍 Monitoring & Optimization

### Key Metrics to Track:
- Embedding generation time
- Vector search latency
- Context relevance scores
- Knowledge base growth rate
- Queue processing throughput

### Optimization Tips:
1. Adjust `similarity_threshold` based on results (currently 0.6)
2. Tune `match_count` for balance between context and performance
3. Periodically update IVFFlat index (`lists` parameter) as data grows
4. Monitor and clean low-quality global knowledge (score < 0.5)
5. Implement caching for frequently accessed embeddings

## 🛠️ Troubleshooting

### Common Issues:

1. **Slow vector search**
   - Solution: Rebuild IVFFlat index, increase `lists` parameter

2. **Poor context relevance**
   - Solution: Lower `similarity_threshold`, increase `match_count`

3. **Queue backlog**
   - Solution: Scale up embedding workers, batch process more aggressively

4. **Memory issues**
   - Solution: Implement embedding caching, paginate large result sets

## 📚 Resources

- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [Supabase pgvector Docs](https://supabase.com/docs/guides/database/extensions/pgvector)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

## ✅ Checklist

- [x] Database migrations created
- [x] Embedding service implemented
- [x] Vector storage service implemented  
- [x] RAG service implemented
- [ ] Integrate RAG into chat pipeline
- [ ] Deploy background embedding worker
- [ ] Test with real conversations
- [ ] Monitor and optimize performance
- [ ] Configure model routing for different tasks

