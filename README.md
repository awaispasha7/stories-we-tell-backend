# Backend - Stories We Tell API

A FastAPI-based backend service for the Stories We Tell cinematic intake chatbot application. Provides intelligent AI-powered story development with conversation management, dossier extraction, and multi-user support.

## ✨ Key Features

### 🤖 AI-Powered Story Development
- **Multi-Model LLM System**: Intelligent routing to specialized AI models
  - **Chat**: GPT-4o-mini for conversational story development
  - **Dossier Extraction**: GPT-4o for intelligent story element extraction
  - **Context-Aware Responses**: Full conversation history for coherent storytelling
- **Streaming Responses**: Real-time Server-Sent Events (SSE) for instant feedback
- **Smart Dossier Generation**: AI decides when to extract story elements based on conversation flow
- **Conversation Memory**: Persistent chat history across sessions

### 📊 Story Dossier System
- **Automatic Extraction**: Intelligently extracts story elements from conversations:
  - **Characters**: Names, descriptions, relationships, character arcs
  - **Themes**: Central themes and motifs
  - **Locations**: Settings, environments, and places
  - **Plot Points**: Story structure and key beats
- **Smart Update Logic**: Only updates dossier when meaningful new information is added
- **Structured JSON Storage**: Clean, queryable story data format
- **Project-Based Organization**: Each story has its own dossier linked to project_id

### 💬 Session & User Management
- **Multi-User Support**: Full user authentication and authorization
- **Session Persistence**: Conversations saved and retrievable across devices
- **Anonymous Sessions**: Support for unauthenticated users with session migration
- **Session Migration**: Seamlessly transfer anonymous sessions to authenticated accounts
- **Chat History**: Complete message history with timestamps and metadata
- **Active Session Tracking**: Smart session lifecycle management

### 🗄️ Database & Storage
- **Supabase Integration**: PostgreSQL database with real-time capabilities
- **Efficient Queries**: Optimized database queries for fast retrieval
- **Data Models**:
  - `users`: User profiles and authentication
  - `chat_sessions`: Conversation sessions with metadata
  - `messages`: Individual chat messages with turn tracking
  - `dossiers`: Story element storage with versioning
  - `projects`: Project-level organization
- **Automatic Timestamps**: Created/updated tracking for all records
- **Data Integrity**: Foreign key constraints and validation

### 🔐 Authentication & Security
- **Supabase Auth Integration**: Secure JWT-based authentication
- **User ID Validation**: Request-level user identification
- **Protected Endpoints**: Authorization checks on sensitive operations
- **CORS Configuration**: Secure cross-origin resource sharing
- **Environment-Based Secrets**: Secure API key management

### 🚀 Performance & Scalability
- **Async/Await**: Non-blocking I/O for high concurrency
- **Streaming API**: Memory-efficient response streaming
- **Connection Pooling**: Efficient database connection management
- **Error Handling**: Comprehensive error catching and logging
- **Logging System**: Detailed debugging and monitoring logs

### 🛠️ Developer Experience
- **FastAPI Framework**: Modern Python web framework with automatic docs
- **Type Safety**: Full Pydantic models with validation
- **Auto-Generated API Docs**: Interactive Swagger UI and ReDoc
- **Hot Reload**: Automatic server restart on code changes
- **Structured Logging**: Console logging for debugging

## Prerequisites

- Python 3.8+
- Supabase account and project
- OpenAI API key
- Google Gemini API key (for descriptions)
- Anthropic Claude API key (for scenes)

## Installation

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the backend directory with the following variables:
   ```env
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   OPENAI_API_KEY=your_openai_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

## Database Setup

1. **Install Supabase CLI** (if not already installed):
   ```bash
   # Using Scoop (Windows)
   scoop install supabase
   
   # Or using npm
   npm install -g supabase
   ```

2. **Initialize Supabase project:**
   ```bash
   supabase init
   ```

3. **Start local Supabase services:**
   ```bash
   supabase start
   ```

4. **Run database migrations:**
   ```bash
   supabase db push
   ```

## Running the Application

### Development Mode (with auto-reload)

```bash
uvicorn app.main:app --reload
```

The server will start on `http://127.0.0.1:8000`

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, you can access:

- **Interactive API Docs (Swagger UI)**: `http://127.0.0.1:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

## API Endpoints

### Chat & Messaging

#### **POST** `/chat`

Stream AI chat responses with automatic dossier extraction. Uses Server-Sent Events (SSE) for real-time streaming.

**Request Body:**
```json
{
  "text": "Tell me about John, a detective in 1940s Los Angeles",
  "session_id": "uuid-optional",
  "project_id": "uuid-optional",
  "user_id": "uuid-optional"
}
```

**Response (SSE Stream):**
```
data: {"type": "text", "content": "John is "}
data: {"type": "text", "content": "a hardboiled detective..."}
data: {"type": "metadata", "metadata": {"session_id": "uuid", "project_id": "uuid"}}
data: {"type": "done"}
```

**Headers:**
- `x-user-id`: User ID for authenticated requests (optional)

### Session Management

#### **GET** `/sessions`

Get all active sessions for the authenticated user.

**Response:**
```json
[
  {
    "session_id": "uuid",
    "user_id": "uuid",
    "project_id": "uuid",
    "title": "Detective Story",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "last_message_at": "2024-01-01T12:00:00Z",
    "is_active": true,
    "message_count": 15
  }
]
```

#### **GET** `/sessions/{session_id}/messages`

Get message history for a specific session.

**Query Parameters:**
- `limit`: Number of messages to retrieve (default: 50)
- `offset`: Pagination offset (default: 0)

**Response:**
```json
[
  {
    "message_id": "uuid",
    "session_id": "uuid",
    "role": "user",
    "content": "Tell me about John",
    "created_at": "2024-01-01T12:00:00Z"
  },
  {
    "message_id": "uuid",
    "session_id": "uuid",
    "role": "assistant",
    "content": "John is a detective...",
    "created_at": "2024-01-01T12:00:01Z"
  }
]
```

#### **DELETE** `/sessions/{session_id}`

Delete (deactivate) a session.

**Response:**
```json
{
  "message": "Session deleted successfully"
}
```

#### **POST** `/sessions/migrate`

Migrate an anonymous session to an authenticated user.

**Request Body:**
```json
{
  "temp_user_id": "anonymous-uuid",
  "permanent_user_id": "authenticated-uuid"
}
```

### User Management

#### **POST** `/users`

Create or update a user profile.

**Request Body:**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

**Response:**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Dossier Management

#### **GET** `/dossier/{project_id}`

Get the story dossier for a specific project.

**Response:**
```json
{
  "project_id": "uuid",
  "user_id": "uuid",
  "snapshot_json": {
    "characters": [
      {
        "name": "John",
        "description": "A hardboiled detective in 1940s LA",
        "relationships": ["Partner with Sarah"],
        "character_arc": "Learns to trust again"
      }
    ],
    "themes": ["Justice", "Redemption", "Trust"],
    "locations": ["Los Angeles", "Detective Office"],
    "plot_points": ["John meets a mysterious client", "discovers corruption"]
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

#### **GET** `/dossier`

Get all dossiers for the authenticated user.

**Response:**
```json
[
  {
    "project_id": "uuid",
    "title": "Detective Story",
    "character_count": 5,
    "theme_count": 3,
    "updated_at": "2024-01-01T12:00:00Z"
  }
]
```

#### **POST** `/dossier`

Create a new dossier.

**Request Body:**
```json
{
  "project_id": "uuid",
  "snapshot_json": {
    "characters": [],
    "themes": [],
    "locations": [],
    "plot_points": []
  }
}
```

#### **PUT** `/dossier/{project_id}`

Update an existing dossier.

**Request Body:**
```json
{
  "snapshot_json": {
    "characters": [...],
    "themes": [...],
    "locations": [...],
    "plot_points": [...]
  }
}
```

#### **DELETE** `/dossier/{project_id}`

Delete a dossier.

**Response:**
```json
{
  "message": "Dossier deleted successfully"
}
```


## Project Structure

```
backend/
├── app/
│   ├── ai/
│   │   ├── llm_service.py           # LLM service abstraction
│   │   ├── dossier_extractor.py    # Story element extraction logic
│   │   └── prompts.py               # AI prompt templates
│   ├── api/
│   │   ├── chat.py                  # Chat streaming endpoint
│   │   ├── chat_sessions.py         # Session management endpoints
│   │   ├── dossier.py               # Dossier CRUD endpoints
│   │   └── users.py                 # User management endpoints
│   ├── database/
│   │   ├── supabase_client.py       # Supabase client singleton
│   │   ├── session_service_supabase.py  # Session DB operations
│   │   └── supabase/
│   │       └── migrations/          # Database migration SQL files
│   ├── models/
│   │   ├── chat.py                  # Chat request/response models
│   │   ├── session.py               # Session data models
│   │   ├── dossier.py               # Dossier data models
│   │   └── user.py                  # User data models
│   ├── utils/
│   │   ├── auth.py                  # Authentication utilities
│   │   └── logging.py               # Logging configuration
│   ├── main.py                      # FastAPI application entry point
│   └── config.py                    # Configuration management
├── .env                             # Environment variables (create this)
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## Data Models

### Chat Models

#### ChatRequest
```python
{
  "text": str,                    # User's message
  "session_id": Optional[str],    # Session identifier
  "project_id": Optional[str],    # Project identifier
  "user_id": Optional[str]        # User identifier
}
```

#### ChatMessage
```python
{
  "message_id": str,              # Unique message ID
  "session_id": str,              # Session this message belongs to
  "turn_id": Optional[str],       # Conversation turn ID
  "role": str,                    # "user" or "assistant"
  "content": str,                 # Message text
  "metadata": Optional[dict],     # Additional metadata
  "created_at": datetime,         # Message timestamp
  "updated_at": datetime          # Last update timestamp
}
```

### Session Models

#### ChatSession
```python
{
  "session_id": str,              # Unique session ID
  "user_id": str,                 # Owner user ID
  "project_id": str,              # Associated project ID
  "title": str,                   # Session title
  "created_at": datetime,         # Creation timestamp
  "updated_at": datetime,         # Last update timestamp
  "last_message_at": datetime,    # Last message timestamp
  "is_active": bool,              # Session status
  "message_count": int            # Total messages in session
}
```

#### SessionMigrationRequest
```python
{
  "temp_user_id": str,            # Anonymous user ID
  "permanent_user_id": str        # Authenticated user ID
}
```

### User Models

#### User
```python
{
  "user_id": str,                 # Unique user ID (from Supabase Auth)
  "email": str,                   # User email
  "display_name": Optional[str],  # Display name
  "avatar_url": Optional[str],    # Profile picture URL
  "created_at": datetime,         # Account creation timestamp
  "updated_at": datetime          # Last update timestamp
}
```

### Dossier Models

#### StoryDossier
```python
{
  "project_id": str,              # Associated project ID
  "user_id": str,                 # Owner user ID
  "snapshot_json": {              # Story elements
    "characters": List[Character],
    "themes": List[str],
    "locations": List[str],
    "plot_points": List[str]
  },
  "created_at": datetime,         # Creation timestamp
  "updated_at": datetime          # Last update timestamp
}
```

#### Character
```python
{
  "name": str,                    # Character name
  "description": str,             # Character description
  "relationships": List[str],     # Relationships with other characters
  "character_arc": Optional[str]  # Character development arc
}
```

### Streaming Response Models

#### SSE Text Chunk
```python
{
  "type": "text",
  "content": str                  # Partial response text
}
```

#### SSE Metadata Chunk
```python
{
  "type": "metadata",
  "metadata": {
    "session_id": str,            # Session ID (created or existing)
    "project_id": str,            # Project ID (created or existing)
    "dossier_updated": bool       # Whether dossier was updated
  }
}
```

#### SSE Done Chunk
```python
{
  "type": "done"                  # Signals end of stream
}
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_KEY` | Your Supabase anon/public key | Yes |
| `OPENAI_API_KEY` | Your OpenAI API key | Yes |
| `GEMINI_API_KEY` | Your Google Gemini API key | Yes |
| `ANTHROPIC_API_KEY` | Your Anthropic Claude API key | Yes |

## Development

### Adding New Endpoints

1. Create new router in `app/api/`
2. Import and include in `app/main.py`
3. Add corresponding models in `app/models.py`

### Database Changes

1. Create migration files in `app/database/supabase/migrations/`
2. Update models in `app/models.py`
3. Run `supabase db push` to apply changes

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError**: Make sure you're running from the backend directory
2. **Supabase Connection Error**: Verify your `.env` file has correct credentials
3. **OpenAI API Error**: Check your API key and billing status

### Logs

The application logs connection status and errors to the console. Look for:
- `Connected to Supabase!` - Successful database connection
- `Error connecting to Supabase: {error}` - Database connection issues

## Contributing

1. Follow PEP 8 style guidelines
2. Add type hints to all functions
3. Update this README when adding new features
4. Test all endpoints before submitting changes

## License

This project is part of the Stories We Tell application suite.

