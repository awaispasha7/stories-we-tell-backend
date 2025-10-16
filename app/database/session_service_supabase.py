"""
Session and Chat Message Database Service (Supabase Version)
Handles user sessions, chat messages, and related operations using Supabase client
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from ..models import (
    User, UserCreate, Session, SessionCreate, SessionSummary,
    ChatMessage, ChatMessageCreate, UserProject
)
from .supabase import get_supabase_client


class SessionService:
    """Service for managing user sessions and chat messages using Supabase"""
    
    def __init__(self):
        self.supabase = None
    
    def get_supabase(self):
        """Get Supabase client"""
        if not self.supabase:
            self.supabase = get_supabase_client()
        return self.supabase
    
    # User Management
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        supabase = self.get_supabase()
        user_id = uuid4()
        
        user_record = {
            "user_id": str(user_id),
            "email": user_data.email,
            "display_name": user_data.display_name,
            "avatar_url": user_data.avatar_url,
            "password_hash": user_data.password_hash
        }
        
        result = supabase.table("users").insert(user_record).execute()
        
        if result.data:
            return User(**result.data[0])
        else:
            raise Exception("Failed to create user")
    
    def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        supabase = self.get_supabase()
        
        result = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
        
        if result.data:
            return User(**result.data[0])
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID (string version for JWT)"""
        return self.get_user(UUID(user_id))
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        supabase = self.get_supabase()
        
        result = supabase.table("users").select("*").eq("email", email).execute()
        
        if result.data:
            return User(**result.data[0])
        return None
    
    def update_user(self, user_id: UUID, user_data: UserCreate) -> Optional[User]:
        """Update user information"""
        supabase = self.get_supabase()
        
        update_data = {
            "email": user_data.email,
            "display_name": user_data.display_name,
            "avatar_url": user_data.avatar_url,
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("users").update(update_data).eq("user_id", str(user_id)).execute()
        
        if result.data:
            return User(**result.data[0])
        return None
    
    # Session Management
    def create_session(self, session_data: SessionCreate) -> Session:
        """Create a new chat session"""
        supabase = self.get_supabase()
        session_id = uuid4()
        
        # First, ensure user owns the project
        self.associate_user_project(session_data.user_id, session_data.project_id)
        
        session_record = {
            "session_id": str(session_id),
            "user_id": str(session_data.user_id),
            "project_id": str(session_data.project_id),
            "title": session_data.title
        }
        
        result = supabase.table("sessions").insert(session_record).execute()
        
        if result.data:
            return Session(**result.data[0])
        else:
            raise Exception("Failed to create session")
    
    def get_session(self, session_id: UUID, user_id: UUID) -> Optional[Session]:
        """Get session by ID (with user ownership check)"""
        supabase = self.get_supabase()
        
        result = supabase.table("sessions").select("*").eq("session_id", str(session_id)).eq("user_id", str(user_id)).eq("is_active", True).execute()
        
        if result.data:
            return Session(**result.data[0])
        return None
    
    def get_user_sessions(self, user_id: UUID, limit: int = 10) -> List[SessionSummary]:
        """Get user's recent sessions with message counts and previews"""
        supabase = self.get_supabase()
        
        # Use the secure function for better RLS enforcement
        try:
            result = supabase.rpc("get_my_sessions", {"p_limit": limit}).execute()
            
            sessions = []
            for row in result.data:
                session_summary = SessionSummary(
                    session_id=UUID(row["session_id"]),
                    project_id=UUID(row["project_id"]),
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"].replace('Z', '+00:00')) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace('Z', '+00:00')) if row["updated_at"] else None,
                    last_message_at=datetime.fromisoformat(row["last_message_at"].replace('Z', '+00:00')) if row["last_message_at"] else None,
                    message_count=row["message_count"],
                    last_message_preview=row["last_message_preview"],
                    project_title=row["project_title"],
                    project_logline=row["project_logline"]
                )
                sessions.append(session_summary)
            
            return sessions
            
        except Exception as e:
            print(f"Error using secure function, falling back to direct query: {e}")
            # Fallback to direct query if the function doesn't exist yet
            result = supabase.table("sessions").select("*").eq("user_id", str(user_id)).eq("is_active", True).order("last_message_at", desc=True).limit(limit).execute()
            
            sessions = []
            for row in result.data:
                # Get message count for this session
                msg_result = supabase.table("chat_messages").select("message_id").eq("session_id", row["session_id"]).execute()
                message_count = len(msg_result.data) if msg_result.data else 0
                
                # Get last message preview
                last_msg_result = supabase.table("chat_messages").select("content").eq("session_id", row["session_id"]).order("created_at", desc=True).limit(1).execute()
                last_message_preview = last_msg_result.data[0]["content"] if last_msg_result.data else None
                
                # Get project info
                project_result = supabase.table("dossier").select("snapshot_json").eq("project_id", row["project_id"]).execute()
                project_data = project_result.data[0]["snapshot_json"] if project_result.data else {}
                
                session_summary = SessionSummary(
                    session_id=UUID(row["session_id"]),
                    project_id=UUID(row["project_id"]),
                    title=row["title"],
                    created_at=datetime.fromisoformat(row["created_at"].replace('Z', '+00:00')) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace('Z', '+00:00')) if row["updated_at"] else None,
                    last_message_at=datetime.fromisoformat(row["last_message_at"].replace('Z', '+00:00')) if row["last_message_at"] else None,
                    message_count=message_count,
                    last_message_preview=last_message_preview,
                    project_title=project_data.get("title"),
                    project_logline=project_data.get("logline")
                )
                sessions.append(session_summary)
            
            return sessions
    
    def update_session_title(self, session_id: UUID, user_id: UUID, title: str) -> Optional[Session]:
        """Update session title"""
        supabase = self.get_supabase()
        
        update_data = {
            "title": title,
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("sessions").update(update_data).eq("session_id", str(session_id)).eq("user_id", str(user_id)).eq("is_active", True).execute()
        
        if result.data:
            return Session(**result.data[0])
        return None
    
    def deactivate_session(self, session_id: UUID, user_id: UUID) -> bool:
        """Deactivate a session (soft delete)"""
        supabase = self.get_supabase()
        
        update_data = {
            "is_active": False,
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("sessions").update(update_data).eq("session_id", str(session_id)).eq("user_id", str(user_id)).execute()
        
        return len(result.data) > 0 if result.data else False
    
    # Chat Message Management
    def create_message(self, message_data: ChatMessageCreate) -> ChatMessage:
        """Create a new chat message"""
        supabase = self.get_supabase()
        message_id = uuid4()
        
        message_record = {
            "message_id": str(message_id),
            "session_id": str(message_data.session_id),
            "turn_id": str(message_data.turn_id) if message_data.turn_id else None,
            "role": message_data.role,
            "content": message_data.content,
            "metadata": message_data.metadata
        }
        
        result = supabase.table("chat_messages").insert(message_record).execute()
        
        if result.data:
            return ChatMessage(**result.data[0])
        else:
            raise Exception("Failed to create message")
    
    def get_session_messages(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get messages for a session (with user ownership check)"""
        supabase = self.get_supabase()
        
        # Use the secure function for better RLS enforcement
        try:
            result = supabase.rpc("get_my_session_messages", {
                "p_session_id": str(session_id),
                "p_limit": limit,
                "p_offset": offset
            }).execute()
            
            messages = []
            for row in result.data:
                message = ChatMessage(
                    message_id=UUID(row["message_id"]),
                    session_id=UUID(session_id),
                    turn_id=None,  # Not returned by the function
                    role=row["role"],
                    content=row["content"],
                    metadata=row["metadata"],
                    created_at=datetime.fromisoformat(row["created_at"].replace('Z', '+00:00')) if row["created_at"] else None,
                    updated_at=None  # Not returned by the function
                )
                messages.append(message)
            
            return messages
            
        except Exception as e:
            print(f"Error using secure function, falling back to direct query: {e}")
            # Fallback to direct query if the function doesn't exist yet
            # First verify session ownership
            session = self.get_session(session_id, user_id)
            if not session:
                return []
            
            result = supabase.table("chat_messages").select("*").eq("session_id", str(session_id)).order("created_at", desc=False).range(offset, offset + limit - 1).execute()
            
            messages = []
            for row in result.data:
                message = ChatMessage(
                    message_id=UUID(row["message_id"]),
                    session_id=UUID(row["session_id"]),
                    turn_id=UUID(row["turn_id"]) if row["turn_id"] else None,
                    role=row["role"],
                    content=row["content"],
                    metadata=row["metadata"],
                    created_at=datetime.fromisoformat(row["created_at"].replace('Z', '+00:00')) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace('Z', '+00:00')) if row["updated_at"] else None
                )
                messages.append(message)
            
            return messages
    
    def get_latest_session_messages(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        limit: int = 10
    ) -> List[ChatMessage]:
        """Get the latest messages for a session"""
        supabase = self.get_supabase()
        
        # First verify session ownership
        session = self.get_session(session_id, user_id)
        if not session:
            return []
        
        result = supabase.table("chat_messages").select("*").eq("session_id", str(session_id)).order("created_at", desc=True).limit(limit).execute()
        
        messages = []
        for row in reversed(result.data):  # Reverse to get chronological order
            message = ChatMessage(
                message_id=UUID(row["message_id"]),
                session_id=UUID(row["session_id"]),
                turn_id=UUID(row["turn_id"]) if row["turn_id"] else None,
                role=row["role"],
                content=row["content"],
                metadata=row["metadata"],
                created_at=datetime.fromisoformat(row["created_at"].replace('Z', '+00:00')) if row["created_at"] else None,
                updated_at=datetime.fromisoformat(row["updated_at"].replace('Z', '+00:00')) if row["updated_at"] else None
            )
            messages.append(message)
        
        return messages
    
    # User-Project Association
    def associate_user_project(self, user_id: UUID, project_id: UUID) -> UserProject:
        """Associate a user with a project (create if not exists)"""
        supabase = self.get_supabase()
        
        user_project_record = {
            "user_id": str(user_id),
            "project_id": str(project_id)
        }
        
        # Try to insert, ignore if already exists
        result = supabase.table("user_projects").upsert(user_project_record).execute()
        
        if result.data:
            return UserProject(**result.data[0])
        else:
            # If upsert didn't work, try to get existing
            existing = supabase.table("user_projects").select("*").eq("user_id", str(user_id)).eq("project_id", str(project_id)).execute()
            if existing.data:
                return UserProject(**existing.data[0])
            else:
                raise Exception("Failed to associate user with project")
    
    def get_user_projects(self, user_id: UUID) -> List[UUID]:
        """Get all project IDs associated with a user"""
        supabase = self.get_supabase()
        
        result = supabase.table("user_projects").select("project_id").eq("user_id", str(user_id)).order("created_at", desc=True).execute()
        
        return [UUID(row["project_id"]) for row in result.data] if result.data else []
    
    # Utility Methods
    def get_or_create_session(
        self, 
        user_id: UUID, 
        project_id: UUID, 
        session_id: Optional[UUID] = None,
        title: Optional[str] = None
    ) -> Session:
        """Get existing session or create new one"""
        if session_id:
            session = self.get_session(session_id, user_id)
            if session:
                return session
        
        # Create new session
        session_data = SessionCreate(
            user_id=user_id,
            project_id=project_id,
            title=title or f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        return self.create_session(session_data)
    
    def get_session_context(
        self, 
        session_id: UUID, 
        user_id: UUID, 
        context_limit: int = 10
    ) -> List[ChatMessage]:
        """Get recent messages for context (for AI processing)"""
        return self.get_latest_session_messages(session_id, user_id, context_limit)


# Global service instance
session_service = SessionService()
