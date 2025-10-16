"""
Session and Chat Message Database Service
Handles user sessions, chat messages, and related operations
"""

import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import asyncpg
from ..models import (
    User, UserCreate, Session, SessionCreate, SessionSummary,
    ChatMessage, ChatMessageCreate, UserProject
)
from .supabase import get_supabase_client


class SessionService:
    """Service for managing user sessions and chat messages"""
    
    def __init__(self):
        self.db_pool = None
    
    async def get_connection(self):
        """Get database connection"""
        if not self.db_pool:
            # For now, we'll use the Supabase client directly
            # In the future, you might want to set up a proper connection pool
            self.db_pool = get_supabase_client()
        return self.db_pool
    
    # User Management
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        conn = await self.get_connection()
        user_id = uuid4()
        
        query = """
        INSERT INTO users (user_id, email, display_name, avatar_url)
        VALUES ($1, $2, $3, $4)
        RETURNING user_id, email, display_name, avatar_url, created_at, updated_at
        """
        
        row = await conn.fetchrow(
            query, user_id, user_data.email, 
            user_data.display_name, user_data.avatar_url
        )
        
        return User(**dict(row))
    
    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        conn = await self.get_connection()
        
        query = """
        SELECT user_id, email, display_name, avatar_url, created_at, updated_at
        FROM users WHERE user_id = $1
        """
        
        row = await conn.fetchrow(query, user_id)
        return User(**dict(row)) if row else None
    
    async def update_user(self, user_id: UUID, user_data: UserCreate) -> Optional[User]:
        """Update user information"""
        conn = await self.get_connection()
        
        query = """
        UPDATE users 
        SET email = $2, display_name = $3, avatar_url = $4, updated_at = current_timestamp
        WHERE user_id = $1
        RETURNING user_id, email, display_name, avatar_url, created_at, updated_at
        """
        
        row = await conn.fetchrow(
            query, user_id, user_data.email, 
            user_data.display_name, user_data.avatar_url
        )
        
        return User(**dict(row)) if row else None
    
    # Session Management
    async def create_session(self, session_data: SessionCreate) -> Session:
        """Create a new chat session"""
        conn = await self.get_connection()
        session_id = uuid4()
        
        # First, ensure user owns the project
        await self.associate_user_project(session_data.user_id, session_data.project_id)
        
        query = """
        INSERT INTO sessions (session_id, user_id, project_id, title)
        VALUES ($1, $2, $3, $4)
        RETURNING session_id, user_id, project_id, title, created_at, updated_at, last_message_at, is_active
        """
        
        row = await conn.fetchrow(
            query, session_id, session_data.user_id, 
            session_data.project_id, session_data.title
        )
        
        return Session(**dict(row))
    
    async def get_session(self, session_id: UUID, user_id: UUID) -> Optional[Session]:
        """Get session by ID (with user ownership check)"""
        conn = await self.get_connection()
        
        query = """
        SELECT session_id, user_id, project_id, title, created_at, updated_at, last_message_at, is_active
        FROM sessions 
        WHERE session_id = $1 AND user_id = $2 AND is_active = true
        """
        
        row = await conn.fetchrow(query, session_id, user_id)
        return Session(**dict(row)) if row else None
    
    async def get_user_sessions(self, user_id: UUID, limit: int = 10) -> List[SessionSummary]:
        """Get user's recent sessions with message counts and previews"""
        conn = await self.get_connection()
        
        query = """
        SELECT 
            s.session_id,
            s.project_id,
            s.title,
            s.created_at,
            s.updated_at,
            s.last_message_at,
            COUNT(cm.message_id) as message_count,
            (
                SELECT content 
                FROM chat_messages 
                WHERE session_id = s.session_id 
                ORDER BY created_at DESC 
                LIMIT 1
            ) as last_message_preview,
            d.snapshot_json->>'title' as project_title,
            d.snapshot_json->>'logline' as project_logline
        FROM sessions s
        LEFT JOIN chat_messages cm ON s.session_id = cm.session_id
        LEFT JOIN dossier d ON s.project_id = d.project_id
        WHERE s.user_id = $1 AND s.is_active = true
        GROUP BY s.session_id, s.project_id, s.title, s.created_at, s.updated_at, s.last_message_at, d.snapshot_json
        ORDER BY s.last_message_at DESC
        LIMIT $2
        """
        
        rows = await conn.fetch(query, user_id, limit)
        return [SessionSummary(**dict(row)) for row in rows]
    
    async def update_session_title(self, session_id: UUID, user_id: UUID, title: str) -> Optional[Session]:
        """Update session title"""
        conn = await self.get_connection()
        
        query = """
        UPDATE sessions 
        SET title = $3, updated_at = current_timestamp
        WHERE session_id = $1 AND user_id = $2 AND is_active = true
        RETURNING session_id, user_id, project_id, title, created_at, updated_at, last_message_at, is_active
        """
        
        row = await conn.fetchrow(query, session_id, user_id, title)
        return Session(**dict(row)) if row else None
    
    async def deactivate_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Deactivate a session (soft delete)"""
        conn = await self.get_connection()
        
        query = """
        UPDATE sessions 
        SET is_active = false, updated_at = current_timestamp
        WHERE session_id = $1 AND user_id = $2
        """
        
        result = await conn.execute(query, session_id, user_id)
        return result == "UPDATE 1"
    
    # Chat Message Management
    async def create_message(self, message_data: ChatMessageCreate) -> ChatMessage:
        """Create a new chat message"""
        conn = await self.get_connection()
        message_id = uuid4()
        
        query = """
        INSERT INTO chat_messages (message_id, session_id, turn_id, role, content, metadata)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING message_id, session_id, turn_id, role, content, metadata, created_at, updated_at
        """
        
        row = await conn.fetchrow(
            query, message_id, message_data.session_id, message_data.turn_id,
            message_data.role, message_data.content, message_data.metadata
        )
        
        return ChatMessage(**dict(row))
    
    async def get_session_messages(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a session (with user ownership check)"""
        conn = await self.get_connection()
        
        query = """
        SELECT cm.message_id, cm.session_id, cm.turn_id, cm.role, cm.content, cm.metadata, cm.created_at, cm.updated_at
        FROM chat_messages cm
        JOIN sessions s ON cm.session_id = s.session_id
        WHERE cm.session_id = $1 AND s.user_id = $2
        ORDER BY cm.created_at ASC
        LIMIT $3 OFFSET $4
        """
        
        rows = await conn.fetch(query, session_id, user_id, limit, offset)
        return [ChatMessage(**dict(row)) for row in rows]
    
    async def get_latest_session_messages(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        limit: int = 10
    ) -> List[ChatMessage]:
        """Get the latest messages for a session"""
        conn = await self.get_connection()
        
        query = """
        SELECT cm.message_id, cm.session_id, cm.turn_id, cm.role, cm.content, cm.metadata, cm.created_at, cm.updated_at
        FROM chat_messages cm
        JOIN sessions s ON cm.session_id = s.session_id
        WHERE cm.session_id = $1 AND s.user_id = $2
        ORDER BY cm.created_at DESC
        LIMIT $3
        """
        
        rows = await conn.fetch(query, session_id, user_id, limit)
        # Reverse to get chronological order
        return [ChatMessage(**dict(row)) for row in reversed(rows)]
    
    # User-Project Association
    async def associate_user_project(self, user_id: UUID, project_id: UUID) -> UserProject:
        """Associate a user with a project (create if not exists)"""
        conn = await self.get_connection()
        
        # Use INSERT ... ON CONFLICT to avoid duplicates
        query = """
        INSERT INTO user_projects (user_id, project_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id, project_id) DO NOTHING
        RETURNING user_id, project_id, created_at
        """
        
        row = await conn.fetchrow(query, user_id, project_id)
        
        # If no row returned (conflict), fetch existing
        if not row:
            query = """
            SELECT user_id, project_id, created_at
            FROM user_projects
            WHERE user_id = $1 AND project_id = $2
            """
            row = await conn.fetchrow(query, user_id, project_id)
        
        return UserProject(**dict(row))
    
    async def get_user_projects(self, user_id: UUID) -> List[UUID]:
        """Get all project IDs associated with a user"""
        conn = await self.get_connection()
        
        query = """
        SELECT project_id
        FROM user_projects
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        
        rows = await conn.fetch(query, user_id)
        return [row['project_id'] for row in rows]
    
    # Utility Methods
    async def get_or_create_session(
        self, 
        user_id: UUID, 
        project_id: UUID, 
        session_id: Optional[UUID] = None,
        title: Optional[str] = None
    ) -> Session:
        """Get existing session or create new one"""
        if session_id:
            session = await self.get_session(session_id, user_id)
            if session:
                return session
        
        # Create new session
        session_data = SessionCreate(
            user_id=user_id,
            project_id=project_id,
            title=title or f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        return await self.create_session(session_data)
    
    async def get_session_context(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        context_limit: int = 10
    ) -> List[ChatMessage]:
        """Get recent messages for context (for AI processing)"""
        return await self.get_latest_session_messages(session_id, user_id, context_limit)


# Global service instance
session_service = SessionService()
