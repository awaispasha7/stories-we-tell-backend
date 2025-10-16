# User Sessions and Chat Persistence Architecture

## Overview

This document outlines the new database schema and API architecture for supporting multi-user chat sessions with message persistence, similar to ChatGPT and other modern chat platforms.

## Database Schema

### New Tables

#### 1. `users` Table
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp
);
```

#### 2. `sessions` Table
```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_id UUID REFERENCES dossier(project_id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp,
    last_message_at TIMESTAMPTZ DEFAULT current_timestamp,
    is_active BOOLEAN DEFAULT true
);
```

#### 3. `chat_messages` Table
```sql
CREATE TABLE chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE,
    turn_id UUID REFERENCES turns(turn_id) ON DELETE SET NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp
);
```

#### 4. `user_projects` Table
```sql
CREATE TABLE user_projects (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_id UUID REFERENCES dossier(project_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, project_id)
);
```

### Updated Tables

#### `turns` Table (Enhanced)
```sql
ALTER TABLE turns ADD COLUMN session_id UUID REFERENCES sessions(session_id);
ALTER TABLE turns ADD COLUMN user_id UUID REFERENCES users(user_id);
```

## API Endpoints

### New Session-Based Chat API (`/api/v1/`)

#### 1. Chat with Session Support
```
POST /api/v1/chat
```
- **Request Body:**
  ```json
  {
    "text": "User message",
    "session_id": "optional-existing-session-id",
    "project_id": "optional-project-id"
  }
  ```
- **Headers:** `X-User-ID: user-uuid`
- **Response:** Streaming response with session metadata

#### 2. Get User Sessions
```
GET /api/v1/sessions?limit=10
```
- **Headers:** `X-User-ID: user-uuid`
- **Response:** List of user's chat sessions with message counts and previews

#### 3. Get Session Messages
```
GET /api/v1/sessions/{session_id}/messages?limit=50&offset=0
```
- **Headers:** `X-User-ID: user-uuid`
- **Response:** Paginated messages for a specific session

#### 4. Update Session Title
```
PUT /api/v1/sessions/{session_id}/title
```
- **Request Body:** `{"title": "New Session Title"}`
- **Headers:** `X-User-ID: user-uuid`

#### 5. Delete Session
```
DELETE /api/v1/sessions/{session_id}
```
- **Headers:** `X-User-ID: user-uuid`

#### 6. User Management
```
POST /api/v1/users
GET /api/v1/users/me
```

## Key Features

### 1. **Session Management**
- Users can have multiple chat sessions
- Each session is associated with a project/dossier
- Sessions can be titled, updated, and deleted
- Automatic session creation when starting new conversations

### 2. **Message Persistence**
- All chat messages are stored in the database
- Messages are linked to sessions and users
- Support for different message roles (user, assistant, system)
- Metadata storage for AI model information

### 3. **User Isolation**
- Row Level Security (RLS) policies ensure users only see their own data
- User-project associations control access to projects
- Session ownership verification on all operations

### 4. **Performance Optimizations**
- Indexes on frequently queried columns
- Pagination for message retrieval
- Efficient session listing with message counts
- Database functions for common operations

### 5. **Backward Compatibility**
- Legacy `/chat` endpoint still works
- Existing dossier and turns tables remain functional
- Gradual migration path for existing data

## Database Functions

### 1. `get_user_sessions(user_id, limit)`
Returns user's recent sessions with message counts and previews.

### 2. `get_session_messages(session_id, limit, offset)`
Returns paginated messages for a session.

### 3. `update_session_last_message()`
Trigger function that updates session timestamp when new messages are added.

## Security Features

### Row Level Security (RLS)
- Users can only access their own sessions and messages
- Project access is controlled through user-project associations
- All operations verify user ownership

### Data Validation
- Message roles are constrained to valid values
- UUID validation for all ID fields
- Proper foreign key constraints

## Migration Strategy

### Phase 1: Database Setup
1. Run the migration script to create new tables
2. Set up RLS policies
3. Create database functions and triggers

### Phase 2: Backend Implementation
1. Deploy new API endpoints
2. Test session management functionality
3. Verify message persistence

### Phase 3: Frontend Integration
1. Update frontend to use new session-based API
2. Implement user authentication
3. Add session management UI

### Phase 4: Data Migration
1. Migrate existing conversation data to new schema
2. Create user accounts for existing sessions
3. Associate historical data with users

## Usage Examples

### Starting a New Chat Session
```javascript
// Frontend code
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-User-ID': 'user-uuid'
  },
  body: JSON.stringify({
    text: "I want to write a horror story",
    project_id: "project-uuid" // Optional: create new project
  })
});
```

### Continuing an Existing Session
```javascript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-User-ID': 'user-uuid'
  },
  body: JSON.stringify({
    text: "What should happen next?",
    session_id: "existing-session-uuid"
  })
});
```

### Getting User's Sessions
```javascript
const sessions = await fetch('/api/v1/sessions', {
  headers: {
    'X-User-ID': 'user-uuid'
  }
}).then(r => r.json());
```

## Benefits

1. **User Experience**: Users can see their chat history and continue conversations
2. **Data Persistence**: No more lost conversations on page refresh
3. **Multi-User Support**: Proper user isolation and session management
4. **Scalability**: Efficient database design with proper indexing
5. **Flexibility**: Support for multiple projects per user
6. **Security**: Row-level security and proper access controls

## Next Steps

1. **Run Migration**: Execute the database migration script
2. **Test Backend**: Verify all API endpoints work correctly
3. **Update Frontend**: Integrate session management into the UI
4. **User Authentication**: Implement proper user authentication system
5. **Data Migration**: Migrate existing data to new schema
6. **Performance Testing**: Test with multiple users and large message volumes

This architecture provides a solid foundation for a modern, multi-user chat application with proper data persistence and user management.
