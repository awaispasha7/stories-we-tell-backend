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
        # For free Resend accounts, use Resend's sandbox domain
        # Default: onboarding@resend.dev (Resend's free tier sandbox domain)
        self.from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
        # CLIENT_EMAIL can be comma-separated for multiple internal team members
        self.client_email = os.getenv("CLIENT_EMAIL", "")
        
        if self.api_key:
            resend.api_key = self.api_key
            self.available = True
            print(f"✅ Email service initialized - FROM: {self.from_email}")
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
            
            # Prepare CC emails (use provided client_emails or fallback to CLIENT_EMAIL env var)
            if client_emails:
                cc_emails = client_emails
            elif self.client_email:
                # Parse comma-separated CLIENT_EMAIL env var
                cc_emails = [email.strip() for email in self.client_email.split(",") if email.strip()]
            else:
                cc_emails = []
            
            # Ensure we have an email to send to
            if not user_email:
                print("⚠️ No user_email provided - cannot deliver story")
                return False
            
            final_user_email = user_email
            
            # Send email
            email_data = {
                "from": self.from_email,
                "to": [final_user_email],
                "subject": subject,
                "html": html_content
            }
            
            # Only add CC if there are emails to CC
            if cc_emails:
                email_data["cc"] = cc_emails
                print(f"📧 CC emails: {cc_emails}")
            
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
        """Build a formatted story summary - Simplified to match client intake requirements only"""
        summary_parts = []
        
        # Story Overview
        if story_data.get('title'):
            summary_parts.append(f"📖 Title: {story_data['title']}")
        
        if story_data.get('logline'):
            summary_parts.append(f"📝 Logline: {story_data['logline']}")
        
        if story_data.get('genre'):
            summary_parts.append(f"🎭 Genre: {story_data['genre']}")
        
        if story_data.get('tone'):
            summary_parts.append(f"🎨 Tone: {story_data['tone']}")
        
        # Hero Characters (Step 2)
        heroes = story_data.get('heroes', [])
        if heroes:
            for idx, hero in enumerate(heroes, 1):
                hero_parts = []
                if hero.get('name'):
                    hero_parts.append(f"Name: {hero['name']}")
                if hero.get('age_at_story'):
                    hero_parts.append(f"Age: {hero['age_at_story']}")
                if hero.get('relationship_to_user'):
                    hero_parts.append(f"Relationship: {hero['relationship_to_user']}")
                if hero.get('physical_descriptors'):
                    hero_parts.append(f"Physical: {hero['physical_descriptors']}")
                if hero.get('personality_traits'):
                    hero_parts.append(f"Personality: {hero['personality_traits']}")
                if hero_parts:
                    summary_parts.append(f"👤 Hero {idx}: {' | '.join(hero_parts)}")
        
        # Supporting Characters (Step 3)
        supporting = story_data.get('supporting_characters', [])
        if supporting:
            for idx, char in enumerate(supporting, 1):
                char_parts = []
                if char.get('name'):
                    char_parts.append(f"Name: {char['name']}")
                if char.get('role'):
                    char_parts.append(f"Role: {char['role']}")
                if char.get('description'):
                    char_parts.append(f"Description: {char['description']}")
                if char_parts:
                    summary_parts.append(f"👥 Supporting {idx}: {' | '.join(char_parts)}")
        
        # Setting & Time (Step 5)
        if story_data.get('story_location') and story_data.get('story_location') != 'Unknown':
            summary_parts.append(f"📍 Location: {story_data['story_location']}")
        
        if story_data.get('story_timeframe') and story_data.get('story_timeframe') != 'Unknown':
            summary_parts.append(f"📅 Timeframe: {story_data['story_timeframe']}")
        
        if story_data.get('season_time_of_year'):
            summary_parts.append(f"🍂 Season/Time of Year: {story_data['season_time_of_year']}")
        
        if story_data.get('environmental_details'):
            summary_parts.append(f"🌿 Environmental Details: {story_data['environmental_details']}")
        
        # Story Type (Step 6)
        if story_data.get('story_type'):
            summary_parts.append(f"📚 Story Type: {story_data['story_type'].replace('_', ' ').title()}")
        
        # Audience & Perspective (Step 7)
        audience = story_data.get('audience', {})
        if isinstance(audience, dict):
            if audience.get('who_will_see_first'):
                summary_parts.append(f"👥 Audience: {audience['who_will_see_first']}")
            if audience.get('desired_feeling'):
                summary_parts.append(f"💭 Desired Feeling: {audience['desired_feeling']}")
        
        if story_data.get('perspective'):
            summary_parts.append(f"🎬 Perspective: {story_data['perspective'].replace('_', ' ').title()}")
        
        return "\n".join(summary_parts) if summary_parts else "Story details captured successfully."
    
    def _build_dossier_html(self, story_data: Dict[str, Any]) -> str:
        """Build HTML for simplified dossier matching EXACT client workflow order"""
        html_parts = []
        
        # STEP 2: Hero Characters (Primary)
        heroes = story_data.get('heroes', [])
        if heroes:
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 2: Hero Characters</h3>")
            for idx, hero in enumerate(heroes, 1):
                html_parts.append(f"<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #3b82f6;'>")
                html_parts.append(f"<h4 style='margin-top: 0;'>Hero {idx}</h4>")
                if hero.get('name'):
                    html_parts.append(f"<p><strong>Name:</strong> {hero['name']}</p>")
                if hero.get('age_at_story'):
                    html_parts.append(f"<p><strong>Age at time of story:</strong> {hero['age_at_story']}</p>")
                if hero.get('relationship_to_user'):
                    html_parts.append(f"<p><strong>Relationship to user:</strong> {hero['relationship_to_user']}</p>")
                if hero.get('physical_descriptors'):
                    html_parts.append(f"<p><strong>Physical descriptors:</strong> {hero['physical_descriptors']}</p>")
                if hero.get('personality_traits'):
                    html_parts.append(f"<p><strong>Personality traits:</strong> {hero['personality_traits']}</p>")
                if hero.get('photo_url'):
                    html_parts.append(f"<p><strong>Photo:</strong> <a href='{hero['photo_url']}' target='_blank'>View Photo</a></p>")
                html_parts.append("</div>")
        
        # STEP 3: Supporting Characters
        supporting = story_data.get('supporting_characters', [])
        if supporting:
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 3: Supporting Characters</h3>")
            for idx, char in enumerate(supporting, 1):
                html_parts.append(f"<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #8b5cf6;'>")
                html_parts.append(f"<h4 style='margin-top: 0;'>Supporting Character {idx}</h4>")
                if char.get('name'):
                    html_parts.append(f"<p><strong>Name:</strong> {char['name']}</p>")
                if char.get('role'):
                    html_parts.append(f"<p><strong>Role:</strong> {char['role']}</p>")
                if char.get('description'):
                    html_parts.append(f"<p><strong>Description:</strong> {char['description']}</p>")
                if char.get('photo_url'):
                    html_parts.append(f"<p><strong>Photo:</strong> <a href='{char['photo_url']}' target='_blank'>View Photo</a></p>")
                html_parts.append("</div>")
        
        # STEP 4: Photo Upload (if any photos were uploaded)
        has_photos = False
        photo_parts = []
        if heroes:
            for hero in heroes:
                if hero.get('photo_url'):
                    has_photos = True
                    photo_parts.append(f"<p><strong>{hero.get('name', 'Hero')}:</strong> <a href='{hero['photo_url']}' target='_blank'>View Photo</a></p>")
        if supporting:
            for char in supporting:
                if char.get('photo_url'):
                    has_photos = True
                    photo_parts.append(f"<p><strong>{char.get('name', 'Supporting Character')}:</strong> <a href='{char['photo_url']}' target='_blank'>View Photo</a></p>")
        
        if has_photos:
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 4: Character Photos</h3>")
            html_parts.append("<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;'>")
            html_parts.extend(photo_parts)
            html_parts.append("</div>")
        
        # STEP 5: Setting & Time
        setting_parts = []
        if story_data.get('story_location') and story_data.get('story_location') != 'Unknown':
            setting_parts.append(f"<p><strong>Where does the story happen?</strong> {story_data['story_location']}</p>")
        if story_data.get('story_timeframe') and story_data.get('story_timeframe') != 'Unknown':
            setting_parts.append(f"<p><strong>What time period?</strong> {story_data['story_timeframe']}</p>")
        if story_data.get('season_time_of_year'):
            setting_parts.append(f"<p><strong>Season/time of year?</strong> {story_data['season_time_of_year']}</p>")
        if story_data.get('environmental_details'):
            setting_parts.append(f"<p><strong>Any meaningful environmental details?</strong> {story_data['environmental_details']}</p>")
        
        if setting_parts:
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 5: Setting & Time</h3>")
            html_parts.append("<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;'>")
            html_parts.extend(setting_parts)
            html_parts.append("</div>")
        
        # STEP 6: Story Type
        if story_data.get('story_type') and story_data.get('story_type') != 'other':
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 6: Story Type</h3>")
            html_parts.append("<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;'>")
            story_type_display = story_data['story_type'].replace('_', ' ').title()
            html_parts.append(f"<p><strong>What type of story do you want?</strong> {story_type_display}</p>")
            html_parts.append("</div>")
        
        # STEP 7: Audience & Perspective
        audience_parts = []
        audience = story_data.get('audience', {})
        if isinstance(audience, dict):
            if audience.get('who_will_see_first'):
                audience_parts.append(f"<p><strong>Who will see this first?</strong> {audience['who_will_see_first']}</p>")
            if audience.get('desired_feeling'):
                audience_parts.append(f"<p><strong>What do you want them to feel?</strong> {audience['desired_feeling']}</p>")
        
        if story_data.get('perspective'):
            perspective_display = story_data['perspective'].replace('_', ' ').title()
            audience_parts.append(f"<p><strong>What perspective?</strong> {perspective_display}</p>")
        
        if audience_parts:
            html_parts.append("<h3 style='color: #667eea; margin-top: 20px;'>Step 7: Audience & Perspective</h3>")
            html_parts.append("<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;'>")
            html_parts.extend(audience_parts)
            html_parts.append("</div>")
        
        return "\n".join(html_parts) if html_parts else "<p>Story details captured successfully.</p>"
    
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
                    
                    <h2>📖 Your Story Dossier</h2>
                    <div class="story-summary">
                        {self._build_dossier_html(story_data)}
                    </div>
                    
                    <h2>🎥 Generated Video Script</h2>
                    <div class="script-section">
                        <p>Here's your personalized video script, ready for production:</p>
                        <div class="script-content">{generated_script}</div>
                    </div>
                    
                    <div class="highlight">
                        <strong>Next Steps:</strong><br>
                        • Review your story dossier above<br>
                        • Check if any information is missing or needs correction<br>
                        • Reply to this email if you'd like any modifications<br>
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
