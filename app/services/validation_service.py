"""
Validation Service for Stories We Tell
Handles validation queue operations for script review workflow
"""

import os
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from supabase import Client
from ..database.supabase import get_supabase_client


class ValidationService:
    """Service for managing validation queue operations"""
    
    def __init__(self):
        self.supabase: Client = get_supabase_client()
        
    async def create_validation_request(
        self,
        project_id: UUID,
        user_id: UUID,
        session_id: UUID,
        conversation_transcript: str,
        generated_script: str,
        client_email: Optional[str] = None,
        client_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new validation request in the queue."""
        try:
            # Use client_email as provided (authenticated user's email)
            final_client_email = client_email
            if not client_email:
                print("⚠️ No client_email provided - story will be validated but not delivered")
            
            validation_data = {
                'validation_id': str(uuid4()),
                'project_id': str(project_id),
                'user_id': str(user_id),
                'session_id': str(session_id),
                'conversation_transcript': conversation_transcript,
                'generated_script': generated_script,
                'client_email': final_client_email,
                'client_name': client_name,
                'status': 'pending',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table('validation_queue').insert(validation_data).execute()
            
            if result.data:
                print(f"✅ Validation request created: {validation_data['validation_id']}")
                return result.data[0]
            else:
                print(f"❌ Failed to create validation request")
                return None
                
        except Exception as e:
            print(f"❌ Error creating validation request: {e}")
            return None
    
    async def get_pending_validations(self) -> List[Dict[str, Any]]:
        """Get all pending validation requests."""
        try:
            result = self.supabase.table('validation_queue').select(
                '*'
            ).order('created_at', desc=True).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error fetching pending validations: {e}")
            return []
    
    async def get_validations_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get validation requests filtered by status."""
        try:
            result = self.supabase.table('validation_queue').select(
                '*'
            ).eq('status', status).order('created_at', desc=True).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error fetching validations by status {status}: {e}")
            return []
    
    async def get_validation_by_id(self, validation_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a specific validation request by ID."""
        try:
            result = self.supabase.table('validation_queue').select(
                '*'
            ).eq('validation_id', str(validation_id)).single().execute()
            
            return result.data if result.data else None
            
        except Exception as e:
            print(f"❌ Error fetching validation {validation_id}: {e}")
            return None
    
    async def update_validation_status(
        self,
        validation_id: UUID,
        status: str,
        reviewed_by: Optional[str] = None,
        review_notes: Optional[str] = None,
        updated_script: Optional[str] = None
    ) -> bool:
        """Update validation request status and review information."""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            if reviewed_by:
                update_data['reviewed_by'] = reviewed_by
                update_data['reviewed_at'] = datetime.now(timezone.utc).isoformat()
                
            if review_notes:
                update_data['review_notes'] = review_notes
                
            if updated_script:
                update_data['generated_script'] = updated_script
            
            result = self.supabase.table('validation_queue').update(
                update_data
            ).eq('validation_id', str(validation_id)).execute()
            
            if result.data:
                print(f"✅ Validation {validation_id} updated to status: {status}")
                return True
            else:
                print(f"❌ Failed to update validation {validation_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating validation {validation_id}: {e}")
            return False
    
    async def approve_and_send(
        self,
        validation_id: UUID,
        reviewed_by: str,
        review_notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Approve validation request and prepare for client delivery."""
        try:
            # First, get the validation data
            validation = await self.get_validation_by_id(validation_id)
            if not validation:
                print(f"❌ Validation {validation_id} not found")
                return None
            
            # Update status to approved
            success = await self.update_validation_status(
                validation_id=validation_id,
                status='approved',
                reviewed_by=reviewed_by,
                review_notes=review_notes
            )
            
            if success:
                return validation
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error approving validation {validation_id}: {e}")
            return None
    
    async def reject_validation(
        self,
        validation_id: UUID,
        reviewed_by: str,
        review_notes: str
    ) -> bool:
        """Reject validation request with notes."""
        try:
            return await self.update_validation_status(
                validation_id=validation_id,
                status='rejected',
                reviewed_by=reviewed_by,
                review_notes=review_notes
            )
                
        except Exception as e:
            print(f"❌ Error rejecting validation {validation_id}: {e}")
            return False
    
    async def mark_sent_to_client(
        self,
        validation_id: UUID
    ) -> bool:
        """Mark validation as sent to client."""
        try:
            return await self.update_validation_status(
                validation_id=validation_id,
                status='sent_to_client'
            )
                
        except Exception as e:
            print(f"❌ Error marking validation {validation_id} as sent: {e}")
            return False
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation queue statistics."""
        try:
            # Get counts by status
            result = self.supabase.table('validation_queue').select(
                'status, created_at'
            ).execute()
            
            all_validations = result.data if result.data else []
            
            stats = {
                'total_requests': len(all_validations),
                'pending_count': 0,
                'in_review_count': 0,
                'approved_count': 0,
                'rejected_count': 0,
                'sent_count': 0,
                'avg_review_time': 'N/A',
                'today_requests': 0
            }
            
            # Count by status
            for record in all_validations:
                status = record.get('status', 'unknown')
                if status == 'pending':
                    stats['pending_count'] += 1
                elif status == 'in_review':
                    stats['in_review_count'] += 1
                elif status == 'approved':
                    stats['approved_count'] += 1
                elif status == 'rejected':
                    stats['rejected_count'] += 1
                elif status == 'sent_to_client':
                    stats['sent_count'] += 1
            
            # Count today's requests
            from datetime import date
            today = date.today().isoformat()
            stats['today_requests'] = sum(
                1 for r in all_validations 
                if r.get('created_at', '').startswith(today)
            )
            
            return stats
            
        except Exception as e:
            print(f"❌ Error fetching validation stats: {e}")
            return {
                'total_requests': 0,
                'pending_count': 0,
                'in_review_count': 0,
                'approved_count': 0,
                'rejected_count': 0,
                'sent_count': 0,
                'avg_review_time': 'N/A',
                'today_requests': 0
            }


# Global instance
validation_service = ValidationService()
