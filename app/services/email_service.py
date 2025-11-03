"""
Email Service for Stories We Tell
Handles email notifications when stories are captured
"""

import os
import resend
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    """Service for sending email notifications"""
    
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@storieswetell.com")
        self.client_email = os.getenv("CLIENT_EMAIL", "client@storieswetell.com")
        
        if self.api_key:
            resend.api_key = self.api_key
            self.available = True
        else:
            self.available = False
            print("⚠️ RESEND_API_KEY not found - email service disabled")
    
    async def send_story_captured_email(
        self, 
        user_email: str,
        user_name: str,
        story_data: Dict[str, Any],
        generated_script: str,
        project_id: str,
        client_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Send email notification when story is captured
        
        Args:
            user_email: User's email address
            user_name: User's name
            story_data: Captured story data from dossier
            generated_script: Generated video script
            project_id: Project ID for reference
            
        Returns:
            bool: True if email sent successfully
        """
        if not self.available:
            print("⚠️ Email service not available - skipping email notification")
            return False
        
        try:
            # Build email content
            subject = f"Your Story is Ready! - {story_data.get('title', 'Untitled Story')}"
            
            # Create story summary
            story_summary = self._build_story_summary(story_data)
            
            # Create email HTML content
            html_content = self._build_email_html(
                user_name=user_name,
                story_data=story_data,
                story_summary=story_summary,
                generated_script=generated_script,
                project_id=project_id
            )
            
            # Prepare CC emails (use provided client_emails or fallback to single client_email)
            cc_emails = client_emails if client_emails else [self.client_email]
            
            # Ensure we have an email to send to
            if not user_email:
                print("⚠️ No user_email provided - cannot deliver story")
                return False
            
            final_user_email = user_email
            
            # Send email
            email_data = {
                "from": self.from_email,
                "to": [final_user_email],
                "cc": cc_emails,  # CC to multiple clients as requested
                "subject": subject,
                "html": html_content
            }
            
            response = resend.Emails.send(email_data)
            
            if response and response.get('id'):
                print(f"✅ Email sent successfully to {final_user_email} (ID: {response['id']})")
                return True
            else:
                print(f"❌ Failed to send email to {final_user_email}")
                return False
                
        except Exception as e:
            print(f"❌ Email sending error: {str(e)}")
            return False
    
    async def send_validation_request(
        self,
        internal_emails: List[str],
        project_id: str,
        story_data: Dict[str, Any],
        transcript: str,
        generated_script: str,
        client_email: Optional[str] = None,
        client_name: Optional[str] = None,
        validation_id: Optional[str] = None
    ) -> bool:
        """Send validation request to internal team for script review."""
        if not self.available:
            return False
        
        # Use the provided client email for display purposes  
        display_client_email = client_email or "Anonymous User"
        
        try:
            # Build validation request email
            subject = f"Story Validation Required - {story_data.get('title', 'Untitled Story')}"
            
            # Create validation HTML content
            validation_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                    .content {{ padding: 20px; }}
                    .highlight {{ background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107; margin: 20px 0; }}
                    .script-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .transcript-section {{ background: #e9ecef; padding: 20px; border-radius: 8px; margin: 20px 0; max-height: 400px; overflow-y: auto; }}
                    .action-buttons {{ text-align: center; margin: 30px 0; }}
                    .approve-btn {{ background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 0 10px; }}
                    .edit-btn {{ background: #ffc107; color: #212529; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 0 10px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔍 Story Validation Request</h1>
                        <p>A completed story requires validation before client delivery</p>
                    </div>
                    
                    <div class="content">
                        <div class="highlight">
                            <strong>Project ID:</strong> {project_id}<br>
                            <strong>Client:</strong> {client_name or 'Anonymous'} ({client_email or 'No email'})<br>
                            <strong>Story Title:</strong> {story_data.get('title', 'Untitled Story')}
                        </div>
                        
                        <h2>📋 Action Required</h2>
                        <p>Please review the conversation transcript and generated script below. Once validated:</p>
                        <ol>
                            <li><strong>Approve</strong> - Send as-is to client</li>
                            <li><strong>Edit</strong> - Modify script then send to client</li>
                        </ol>
                        
                        <div class="action-buttons">
                            <a href="https://app.storiesweetell.com/admin/validate/{validation_id or project_id}?action=approve" class="approve-btn">✅ Approve & Send</a>
                            <a href="https://app.storiesweetell.com/admin/validate/{validation_id or project_id}?action=edit" class="edit-btn">✏️ Edit Script</a>
                        </div>
                        
                        <h2>💬 Conversation Transcript</h2>
                        <div class="transcript-section">
                            <pre>{transcript}</pre>
                        </div>
                        
                        <h2>🎥 Generated Video Script</h2>
                        <div class="script-section">
                            <pre>{generated_script}</pre>
                        </div>
                        
                        <div class="highlight">
                            <strong>Next Steps:</strong><br>
                            • Review transcript for story completeness<br>
                            • Validate script accuracy and quality<br>
                            • Approve or edit before client delivery
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send validation email to all internal team members
            email_params = {
                'from': f"Stories We Tell Validation <{self.from_email}>",
                'to': internal_emails,
                'subject': subject,
                'html': validation_html
            }
            
            response = resend.Emails.send(email_params)
            if response and response.get('id'):
                print(f"✅ Validation request sent to {', '.join(internal_emails)} (ID: {response.get('id')})")
                return True
            else:
                print(f"❌ Failed to send validation request - no response ID")
                return False
            
        except Exception as e:
            print(f"❌ Failed to send validation request: {e}")
            return False
    
    def _build_story_summary(self, story_data: Dict[str, Any]) -> str:
        """Build a formatted story summary"""
        summary_parts = []
        
        # Story Frame
        if story_data.get('story_timeframe') and story_data.get('story_timeframe') != 'Unknown':
            summary_parts.append(f"📅 Time: {story_data['story_timeframe']}")
        
        if story_data.get('story_location') and story_data.get('story_location') != 'Unknown':
            summary_parts.append(f"📍 Location: {story_data['story_location']}")
        
        if story_data.get('story_world_type') and story_data.get('story_world_type') != 'Unknown':
            summary_parts.append(f"🌍 World: {story_data['story_world_type']}")
        
        # Character
        if story_data.get('subject_full_name') and story_data.get('subject_full_name') != 'Unknown':
            summary_parts.append(f"👤 Character: {story_data['subject_full_name']}")
        
        if story_data.get('subject_relationship_to_writer') and story_data.get('subject_relationship_to_writer') != 'Unknown':
            summary_parts.append(f"💝 Relationship: {story_data['subject_relationship_to_writer']}")
        
        # Story Craft
        if story_data.get('problem_statement') and story_data.get('problem_statement') != 'Unknown':
            summary_parts.append(f"🎯 Problem: {story_data['problem_statement']}")
        
        if story_data.get('actions_taken') and story_data.get('actions_taken') != 'Unknown':
            summary_parts.append(f"⚡ Actions: {story_data['actions_taken']}")
        
        if story_data.get('outcome') and story_data.get('outcome') != 'Unknown':
            summary_parts.append(f"🏆 Outcome: {story_data['outcome']}")
        
        if story_data.get('likes_in_story') and story_data.get('likes_in_story') != 'Unknown':
            summary_parts.append(f"❤️ Why This Story: {story_data['likes_in_story']}")
        
        return "\n".join(summary_parts) if summary_parts else "Story details captured successfully."
    
    def _build_email_html(
        self, 
        user_name: str,
        story_data: Dict[str, Any],
        story_summary: str,
        generated_script: str,
        project_id: str
    ) -> str:
        """Build HTML email content"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your Story is Ready!</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .story-summary {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .script-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .script-content {{ background: #f5f5f5; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                h1 {{ margin: 0; font-size: 28px; }}
                h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                .highlight {{ background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 Your Story is Ready!</h1>
                    <p>Thank you for sharing your story with Stories We Tell</p>
                </div>
                
                <div class="content">
                    <p>Dear {user_name},</p>
                    
                    <p>We're excited to let you know that your story has been successfully captured and we've generated a video script for you!</p>
                    
                    <div class="highlight">
                        <strong>Project ID:</strong> {project_id}<br>
                        <strong>Story Title:</strong> {story_data.get('title', 'Untitled Story')}
                    </div>
                    
                    <h2>📖 Your Story Summary</h2>
                    <div class="story-summary">
                        {story_summary.replace(chr(10), '<br>')}
                    </div>
                    
                    <h2>🎥 Generated Video Script</h2>
                    <div class="script-section">
                        <p>Here's your personalized video script, ready for production:</p>
                        <div class="script-content">{generated_script}</div>
                    </div>
                    
                    <div class="highlight">
                        <strong>Next Steps:</strong><br>
                        • Review your story summary and script<br>
                        • Contact us if you'd like any modifications<br>
                        • We'll be in touch about video production options
                    </div>
                    
                    <p>Thank you for trusting us with your story. We can't wait to help bring it to life!</p>
                    
                    <p>Best regards,<br>
                    The Stories We Tell Team</p>
                </div>
                
                <div class="footer">
                    <p>This email was automatically generated when your story was captured.</p>
                    <p>© 2025 Stories We Tell. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

# Global instance
email_service = EmailService()
