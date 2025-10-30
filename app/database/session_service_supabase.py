"""
Session and Chat Message Database Service (Supabase Version)
Handles user sessions, chat messages, and related operations using Supabase client
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from ..models import (
    User, UserCreate, Session, SessionCreate, SessionSummary,
    ChatMessage, ChatMessageCreate, UserProject, Dossier, DossierCreate, DossierUpdate
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
        """Create a new user or update existing one"""
        supabase = self.get_supabase()
        
        # If user_id is provided, use it; otherwise generate a new one
        user_id = user_data.user_id if hasattr(user_data, 'user_id') and user_data.user_id else uuid4()
        
        user_record = {
            "user_id": str(user_id),
            "email": user_data.email,
            "display_name": user_data.display_name,
            "avatar_url": user_data.avatar_url
        }
        
        # Try to insert first, if it fails due to conflict, try to update
        try:
            result = supabase.table("users").insert(user_record).execute()
        except Exception as e:
            # If insert fails (likely due to email conflict), try to update
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                result = supabase.table("users").update({
                    "display_name": user_data.display_name,
                    "avatar_url": user_data.avatar_url,
                    "updated_at": datetime.now().isoformat()
                }).eq("email", user_data.email).execute()
            else:
                raise e
        
        if result.data:
            return User(**result.data[0])
        else:
            raise Exception("Failed to create/update user")
    
    def create_user_from_auth(self, auth_user_id: str, email: str, display_name: str = None, avatar_url: str = None) -> User:
        """Create a user from Supabase auth user data using the auth user's ID"""
        supabase = self.get_supabase()
        
        # First, check if a user with this email already exists
        existing_user = supabase.table("users").select("*").eq("email", email).execute()
        if existing_user.data:
            print(f"User with email {email} already exists with ID {existing_user.data[0]['user_id']}")
            # Update the existing user with new auth data
            update_result = supabase.table("users").update({
                "user_id": auth_user_id,  # Update to the new auth user ID
                "display_name": display_name or email.split('@')[0] if email else None,
                "avatar_url": avatar_url,
                "updated_at": datetime.now().isoformat()
            }).eq("email", email).execute()
            
            # Fetch the updated user data
            result = supabase.table("users").select("*").eq("user_id", auth_user_id).execute()
            if result.data:
                return User(**result.data[0])
            else:
                raise Exception(f"Failed to update existing user {email} with new auth ID {auth_user_id}")
        
        user_record = {
            "user_id": auth_user_id,  # Use the auth user's ID directly
            "email": email,
            "display_name": display_name or email.split('@')[0] if email else None,
            "avatar_url": avatar_url
        }
        
        # Try to insert first, if it fails due to conflict, try to update
        try:
            result = supabase.table("users").insert(user_record).execute()
            if not result.data:
                raise Exception("No data returned from insert")
        except Exception as e:
            # If insert fails (likely due to user_id conflict), try to update
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower() or "409" in str(e):
                print(f"User {auth_user_id} already exists, updating...")
                update_data = {
                    "email": email,
                    "display_name": display_name or email.split('@')[0] if email else None,
                    "avatar_url": avatar_url,
                    "updated_at": datetime.now().isoformat()
                }
                print(f"Update data: {update_data}")
                update_result = supabase.table("users").update(update_data).eq("user_id", auth_user_id).execute()
                print(f"Update result: {update_result.data}")
                
                # Add a small delay to ensure the update is committed
                import time
                time.sleep(0.1)
                
                # Fetch the updated user data
                result = supabase.table("users").select("*").eq("user_id", auth_user_id).execute()
                print(f"User fetch result: {result.data}")
                if not result.data:
                    # Try fetching by email as well
                    email_result = supabase.table("users").select("*").eq("email", email).execute()
                    print(f"User fetch by email result: {email_result.data}")
                    
                    # Try to fetch all users to debug
                    all_users = supabase.table("users").select("*").execute()
                    print(f"All users in database: {all_users.data}")
                    raise Exception(f"User {auth_user_id} not found after update")
            else:
                print(f"Insert error: {e}")
                raise e
        
        if result.data:
            return User(**result.data[0])
        else:
            raise Exception("Failed to create/update user from auth")
    
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
        
        # First, ensure the project/dossier exists
        self.ensure_project_exists(session_data.project_id, session_data.user_id)
        
        # Then, ensure user owns the project
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
        
        print(f"🗑️ Deactivating session {session_id} for user {user_id}")
        
        update_data = {
            "is_active": False,
            "updated_at": datetime.now().isoformat()
        }
        
        print(f"🗑️ Update data: {update_data}")
        
        try:
            result = supabase.table("sessions").update(update_data).eq("session_id", str(session_id)).eq("user_id", str(user_id)).execute()
            print(f"🗑️ Supabase update result: {result}")
            print(f"🗑️ Result data: {result.data}")
            print(f"🗑️ Result count: {result.count}")
            
            success = len(result.data) > 0 if result.data else False
            print(f"🗑️ Deactivation success: {success}")
            return success
        except Exception as e:
            print(f"❌ Error in deactivate_session: {e}")
            raise
    
    # Dossier Management
    def create_dossier(self, dossier_data: DossierCreate) -> Dossier:
        """Create a new dossier for a user"""
        supabase = self.get_supabase()
        
        dossier_record = {
            "project_id": str(dossier_data.project_id),
            "user_id": str(dossier_data.user_id),
            "snapshot_json": dossier_data.snapshot_json or {
                "title": "New Project",
                "logline": "",
                "characters": [],
                "scenes": []
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("dossier").insert(dossier_record).execute()
        
        if result.data:
            return Dossier(**result.data[0])
        else:
            raise Exception("Failed to create dossier")
    
    def get_user_dossiers(self, user_id: UUID) -> List[Dossier]:
        """Get all dossiers for a user"""
        supabase = self.get_supabase()
        
        result = supabase.table("dossier").select("*").eq("user_id", str(user_id)).order("updated_at", desc=True).execute()
        
        if result.data:
            return [Dossier(**dossier) for dossier in result.data]
        return []
    
    def get_dossier(self, project_id: UUID, user_id: UUID) -> Optional[Dossier]:
        """Get a specific dossier for a user"""
        supabase = self.get_supabase()
        
        print(f"🔍 [DB] get_dossier query - project_id: {project_id}, user_id: {user_id}")
        result = supabase.table("dossier").select("*").eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
        print(f"🔍 [DB] get_dossier result.data: {result.data}")
        print(f"🔍 [DB] get_dossier result.data length: {len(result.data) if result.data else 0}")
        
        if result.data and len(result.data) > 0:
            print(f"✅ [DB] Found dossier, returning: {result.data[0].get('project_id', 'unknown')}")
            return Dossier(**result.data[0])
        print(f"❌ [DB] No dossier found, returning None")
        return None
    
    def update_dossier(self, project_id: UUID, user_id: UUID, dossier_data: DossierUpdate) -> Optional[Dossier]:
        """Update a dossier for a user"""
        supabase = self.get_supabase()
        
        update_data = {
            "updated_at": datetime.now().isoformat()
        }
        
        if dossier_data.snapshot_json is not None:
            update_data["snapshot_json"] = dossier_data.snapshot_json
        
        print(f"📝 [DB] update_dossier: project_id={project_id}, user_id={user_id}, keys={list(update_data.keys())}")
        result = supabase.table("dossier").update(update_data).eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
        updated_rows = len(result.data) if result.data else 0
        print(f"📝 [DB] update_dossier rows updated: {updated_rows}")

        if result.data and updated_rows > 0:
            return Dossier(**result.data[0])

        # Fallback: if no rows updated, try upsert (handles RLS timing or missing row)
        try:
            print("📝 [DB] update_dossier fallback to upsert")
            upsert_record = {
                "project_id": str(project_id),
                "user_id": str(user_id),
                **update_data
            }
            upsert_res = supabase.table("dossier").upsert(upsert_record).execute()
            if upsert_res.data:
                return Dossier(**upsert_res.data[0])
        except Exception as e:
            print(f"❌ [DB] update_dossier upsert error: {e}")

        return None
    
    
    def delete_dossier(self, project_id: UUID, user_id: UUID) -> bool:
        """Delete a dossier for a user"""
        supabase = self.get_supabase()
        
        result = supabase.table("dossier").delete().eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
        
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
    
    # Project/Dossier Management
    def ensure_project_exists(self, project_id: UUID, user_id: UUID) -> None:
        """Ensure a project/dossier exists, create if it doesn't"""
        supabase = self.get_supabase()
        
        # Check if project exists
        result = supabase.table("dossier").select("project_id").eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
        
        if not result.data:
            # Create a default dossier/project
            dossier_record = {
                "project_id": str(project_id),
                "user_id": str(user_id),
                "snapshot_json": {
                    "title": "New Project",
                    "logline": "",
                    "characters": [],
                    "scenes": []
                },
                "updated_at": datetime.now().isoformat()
            }
            
            supabase.table("dossier").insert(dossier_record).execute()
    
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
        
        # Create new session - use provided session_id if available, otherwise generate new one
        if session_id:
            # Use the provided session_id
            supabase = self.get_supabase()
            
            # First, ensure the project/dossier exists
            self.ensure_project_exists(project_id, user_id)
            
            # Then, ensure user owns the project
            self.associate_user_project(user_id, project_id)
            
            session_record = {
                "session_id": str(session_id),
                "user_id": str(user_id),
                "project_id": str(project_id),
                "title": title or f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
            
            result = supabase.table("sessions").insert(session_record).execute()
            
            if result.data:
                return Session(**result.data[0])
            else:
                raise Exception("Failed to create session with provided ID")
        else:
            # Create new session with generated ID
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
