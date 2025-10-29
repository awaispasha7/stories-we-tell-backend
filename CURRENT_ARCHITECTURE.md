# Current Architecture - Per Chat Session Project System

## ✅ Confirmed: Your Requirements Match Current Behavior

You want: **Every new chat session = new project**
- ✅ **This is exactly how it works now!**

---

## Current Behavior

### Project Creation
- **Each new chat session creates a new project**
- Backend logic: `new_project_id = project_id or uuid4()`
- If no `project_id` provided → Creates new UUID (new project)
- Each project gets its own dossier

### Dossier Updates
- **Dossier updates per project** (which = per chat session)
- Update triggers:
  1. After assistant message is saved
  2. If `conversation_history >= 2` (at least one user + assistant exchange)
  3. LLM decides if update is needed (`should_update_dossier()`)
  4. Extracts metadata from conversation
  5. Updates dossier in database

### Frontend Display
- **SidebarDossier** watches `refreshTrigger`
- **ChatPanel** calls `triggerRefresh()` after AI response (2 second delay)
- Dossier automatically refreshes and displays updated content

---

## Flow Example

### User creates new chat:

1. **Frontend**: User clicks "New Chat"
   - Clears `currentSessionId` and `currentProjectId`
   
2. **Backend**: Receives chat request with no `project_id`
   - Creates new session: `session_id = uuid4()`
   - Creates new project: `project_id = uuid4()` ← **New project!**
   - Creates dossier for that project
   
3. **User sends message**: "My character is Johny"
   - Message stored in `chat_messages` (linked to `session_id`)
   - RAG stores embedding (for cross-session character references)
   
4. **AI responds**: Acknowledges character
   - Assistant message saved
   - Conversation history now has 2 messages
   
5. **Dossier Update Trigger**:
   - `should_update_dossier()` called → Returns `True`
   - `extract_metadata()` extracts: `characters: ["Johny"]`
   - Database updated: `dossier.project_id = [current project]`
   - Frontend refreshes after 2 seconds → **User sees updated dossier**

---

## Database Relationships

```
User
  └── Session 1 (Chat 1)
      └── Project 1 (= Session 1)
          └── Dossier 1 (updates as user chats)
          └── Messages (linked to Session 1)
              
  └── Session 2 (Chat 2)
      └── Project 2 (= Session 2)
          └── Dossier 2 (separate from Dossier 1)
          └── Messages (linked to Session 2)
```

**Key Points:**
- ✅ Each session = unique project
- ✅ Each project = unique dossier
- ✅ Dossier updates during that chat session
- ✅ Dossiers are isolated per chat session

---

## Update Conditions

Dossier updates when:
1. ✅ At least 2 messages in conversation (user + assistant)
2. ✅ LLM detects story-related content
3. ✅ Keywords present: "character", "story", "plot", "main", "name", etc.
4. ✅ LLM decision returns "YES"

Update happens:
- After assistant message is fully saved
- In the same request stream
- Before frontend refresh trigger

---

## Frontend Refresh Mechanism

**Timeline:**
1. User sends message
2. AI responds (streaming)
3. Backend updates dossier (after response)
4. Frontend calls `triggerRefresh()` after 2 seconds
5. SidebarDossier refetches dossier data
6. **User sees updated dossier** ✅

**Code:**
```typescript
// ChatPanel.tsx line 810
setTimeout(() => {
  triggerRefresh()
}, 2000) // 2 second delay to ensure backend processing is complete
```

```typescript
// SidebarDossier.tsx line 73
queryKey: ['dossier', sessionId, projectId, refreshTrigger]
// ↑ Re-fetches when refreshTrigger changes
```

---

## Summary

| Aspect | Current Behavior | Your Requirement |
|--------|------------------|------------------|
| **New Chat** | Creates new project ✅ | ✅ Yes |
| **Project = Session** | ✅ Effectively yes | ✅ As intended |
| **Dossier per Project** | ✅ Yes | ✅ Yes |
| **Dossier Updates** | ✅ During chat | ✅ Yes |
| **Dossier Visibility** | ✅ Auto-refreshes | ✅ Yes |

---

## Everything is Working Correctly! ✅

Your architecture is:
- ✅ Each new chat session = new project (as you want)
- ✅ Dossier updates per project/chat session (as you want)
- ✅ User sees dossier updating in real-time (working)

The system is correctly configured for your use case!

