"""
Email Service for Stories We Tell
Handles email notifications when stories are captured
Supports both Resend API and SMTP (Gmail) providers
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Commented out Resend import - keeping for future use
# import resend

load_dotenv()

class EmailService:
    """Service for sending email notifications"""
    
    def __init__(self):
        # Email provider selection: 'resend' or 'smtp' (default: 'smtp')
        self.provider = os.getenv("EMAIL_PROVIDER", "smtp").lower()
        
        # Resend configuration (commented out but kept for future use)
        # self.resend_api_key = os.getenv("RESEND_API_KEY")
        # self.resend_from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
        
        # SMTP configuration (Gmail)
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "")
        self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "Stories We Tell")
        
        # CLIENT_EMAIL can be comma-separated for multiple internal team members
        self.client_email = os.getenv("CLIENT_EMAIL", "")
        
        # Frontend URL for admin links
        self.frontend_url = os.getenv("FRONTEND_URL", "https://stories-we-tell.vercel.app")
        
        # Determine availability based on provider
        if self.provider == "smtp":
            if self.smtp_user and self.smtp_password and self.smtp_from_email:
                self.available = True
                self.from_email = self.smtp_from_email
                print(f"✅ Email service initialized (SMTP) - FROM: {self.smtp_from_name} <{self.smtp_from_email}>")
                print(f"📧 SMTP Host: {self.smtp_host}:{self.smtp_port}")
            else:
                self.available = False
                print("⚠️ SMTP credentials not found - email service disabled")
                print("   Required: SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL")
        else:  # resend
            # Commented out Resend initialization - keeping for future use
            # if self.resend_api_key:
            #     resend.api_key = self.resend_api_key
            #     self.available = True
            #     self.from_email = self.resend_from_email
            #     print(f"✅ Email service initialized (Resend) - FROM: {self.resend_from_email}")
            # else:
            self.available = False
            print("⚠️ Resend is currently disabled. Using SMTP instead.")
            print("   To use Resend, set EMAIL_PROVIDER=resend and RESEND_API_KEY")
    
    def _send_via_smtp(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        cc_emails: Optional[List[str]] = None,
        attachment_path: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP (Gmail)
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML email content
            cc_emails: Optional list of CC email addresses
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg['To'] = ', '.join(to_emails)
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Add attachment if provided
            if attachment_path and os.path.exists(attachment_path):
                try:
                    with open(attachment_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(attachment_path)}'
                        )
                        msg.attach(part)
                        print(f"📎 [EMAIL] Attached file: {os.path.basename(attachment_path)}")
                except Exception as attach_error:
                    print(f"⚠️ [EMAIL] Error attaching file: {attach_error}")
                    # Continue without attachment if attachment fails
            
            # Connect to SMTP server
            if self.smtp_port == 465:
                # SSL connection
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                # TLS connection
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            
            # Login and send
            server.login(self.smtp_user, self.smtp_password)
            
            # Combine to and cc recipients
            all_recipients = to_emails + (cc_emails if cc_emails else [])
            server.send_message(msg, from_addr=self.smtp_from_email, to_addrs=all_recipients)
            server.quit()
            
            print(f"✅ Email sent via SMTP to {', '.join(to_emails)}")
            if cc_emails:
                print(f"📧 CC: {', '.join(cc_emails)}")
            return True
            
        except Exception as e:
            print(f"❌ SMTP email sending error: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    def _send_via_resend(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        from_name: str = "Stories We Tell",
        cc_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Send email via Resend API (commented out but kept for future use)
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML email content
            from_name: Sender name
            cc_emails: Optional list of CC email addresses
            
        Returns:
            bool: True if email sent successfully
        """
        # Commented out Resend implementation - keeping for future use
        # try:
        #     email_data = {
        #         "from": f"{from_name} <{self.resend_from_email}>",
        #         "to": to_emails,
        #         "subject": subject,
        #         "html": html_content
        #     }
        #     
        #     if cc_emails:
        #         email_data["cc"] = cc_emails
        #     
        #     response = resend.Emails.send(email_data)
        #     
        #     if response and response.get('id'):
        #         print(f"✅ Email sent via Resend to {', '.join(to_emails)} (ID: {response['id']})")
        #         return True
        #     else:
        #         print(f"❌ Failed to send email via Resend")
        #         return False
        #         
        # except Exception as e:
        #     print(f"❌ Resend email sending error: {str(e)}")
        #     return False
        
        print("⚠️ Resend is currently disabled. Please use SMTP provider.")
        return False
    
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
            
            # Send email via configured provider
            if self.provider == "smtp":
                return self._send_via_smtp(
                    to_emails=[final_user_email],
                    subject=subject,
                    html_content=html_content,
                    cc_emails=cc_emails
                )
            else:  # resend
                return self._send_via_resend(
                    to_emails=[final_user_email],
                    subject=subject,
                    html_content=html_content,
                    from_name="Stories We Tell",
                    cc_emails=cc_emails
                )
                
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
                            <a href="{self.frontend_url}/admin/validate/{validation_id or project_id}?action=approve" class="approve-btn">✅ Approve & Send</a>
                            <a href="{self.frontend_url}/admin/validate/{validation_id or project_id}?action=edit" class="edit-btn">✏️ Edit Script</a>
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
            if self.provider == "smtp":
                return self._send_via_smtp(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=validation_html
                )
            else:  # resend
                return self._send_via_resend(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=validation_html,
                    from_name="Stories We Tell Validation"
                )
            
        except Exception as e:
            print(f"❌ Failed to send validation request: {e}")
            return False
    
    async def send_review_notification(
        self,
        internal_emails: List[str],
        project_id: str,
        validation_id: str,
        story_data: Dict[str, Any],
        review_checklist: Dict[str, Any],
        review_issues: Dict[str, Any],
        needs_revision: bool
    ) -> bool:
        """
        Send review notification email to all admins with checklist status and issues.
        
        Args:
            internal_emails: List of admin email addresses
            project_id: Project ID
            validation_id: Validation ID
            story_data: Story dossier data
            review_checklist: Review checklist with checked/unchecked items
            review_issues: Flagged issues (missing_info, conflicts, factual_gaps)
            needs_revision: Whether revision is needed
        
        Returns:
            bool: True if email sent successfully
        """
        print(f"📧 [EMAIL] Starting review notification email send...")
        print(f"📧 [EMAIL] Provider: {self.provider}")
        print(f"📧 [EMAIL] Recipients: {internal_emails}")
        print(f"📧 [EMAIL] Project ID: {project_id}")
        print(f"📧 [EMAIL] Validation ID: {validation_id}")
        print(f"📧 [EMAIL] Needs Revision: {needs_revision}")
        
        if not self.available:
            print("⚠️ [EMAIL] Email service not available - skipping review notification")
            print("⚠️ [EMAIL] Check email provider configuration (SMTP_USER, SMTP_PASSWORD, etc.)")
            return False
        
        try:
            subject = f"Story Review - {story_data.get('title', 'Untitled Story')} {'⚠️ Needs Revision' if needs_revision else '✅ Approved'}"
            
            # Build checklist status HTML
            checklist_html = "<h3>📋 Review Checklist Status</h3><ul>"
            for key, checked in review_checklist.items():
                status_icon = "✅" if checked else "❌"
                status_text = "Reviewed" if checked else "Needs Attention"
                item_name = key.replace("_", " ").title()
                checklist_html += f"<li>{status_icon} <strong>{item_name}:</strong> {status_text}</li>"
            checklist_html += "</ul>"
            
            # Build issues HTML
            issues_html = ""
            if review_issues:
                has_any_issues = any(
                    issues and len(issues) > 0 
                    for issues in review_issues.values() 
                    if isinstance(issues, list)
                )
                if has_any_issues:
                    issues_html = "<h3>⚠️ Flagged Issues</h3>"
                    for issue_type, issues in review_issues.items():
                        if issues and len(issues) > 0:
                            issue_type_name = issue_type.replace("_", " ").title()
                            issues_html += f"<h4>{issue_type_name}:</h4><ul>"
                            for issue in issues[:5]:  # Limit to 5 issues
                                issues_html += f"<li>{issue}</li>"
                            issues_html += "</ul>"
            
            # Build review notification HTML
            review_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: {'#fff3cd' if needs_revision else '#d4edda'}; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid {'#ffc107' if needs_revision else '#28a745'}; }}
                    .content {{ padding: 20px; }}
                    .action-buttons {{ text-align: center; margin: 30px 0; }}
                    .review-btn {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 0 10px; display: inline-block; }}
                    ul {{ margin: 10px 0; padding-left: 20px; }}
                    li {{ margin: 5px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{'⚠️ Story Review - Revision Needed' if needs_revision else '✅ Story Review - Approved'}</h1>
                        <p><strong>Project ID:</strong> {project_id}</p>
                        <p><strong>Story Title:</strong> {story_data.get('title', 'Untitled Story')}</p>
                    </div>
                    
                    <div class="content">
                        {checklist_html}
                        {issues_html if issues_html else '<p>✅ No issues flagged.</p>'}
                        
                        <div class="action-buttons">
                            <a href="{self.frontend_url}/admin/validate/{validation_id}" class="review-btn">📋 View Full Review</a>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px;">
                            <p><strong>Next Steps:</strong></p>
                            {'<p>⚠️ This story needs revision. The chat has been reopened for the user to provide missing information.</p>' if needs_revision else '<p>✅ All checklist items reviewed. Story is ready for next steps.</p>'}
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Generate Excel file from dossier data
            excel_path = None
            try:
                from ..services.excel_generator import generate_dossier_excel
                excel_path = generate_dossier_excel(story_data, project_id)
                if excel_path:
                    print(f"✅ [EMAIL] Excel file generated: {excel_path}")
                else:
                    print(f"⚠️ [EMAIL] Excel file generation failed, continuing without attachment")
            except Exception as excel_error:
                print(f"⚠️ [EMAIL] Error generating Excel file: {excel_error}")
                import traceback
                print(f"⚠️ [EMAIL] Traceback: {traceback.format_exc()}")
                # Continue without Excel attachment if generation fails
            
            # Send email to all admins
            if self.provider == "smtp":
                print(f"📧 [EMAIL] Sending via SMTP to {len(internal_emails)} recipients...")
                result = self._send_via_smtp(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=review_html,
                    attachment_path=excel_path
                )
                if result:
                    print(f"✅ [EMAIL] Review notification email sent successfully to {', '.join(internal_emails)}")
                else:
                    print(f"❌ [EMAIL] Failed to send review notification email")
                
                # Clean up Excel file after sending
                if excel_path and os.path.exists(excel_path):
                    try:
                        os.remove(excel_path)
                        print(f"🗑️ [EMAIL] Cleaned up temporary Excel file: {excel_path}")
                    except Exception as cleanup_error:
                        print(f"⚠️ [EMAIL] Error cleaning up Excel file: {cleanup_error}")
                
                return result
            else:  # resend
                return self._send_via_resend(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=review_html,
                    from_name="Stories We Tell Review"
                )
                
        except Exception as e:
            print(f"❌ [EMAIL] Failed to send review notification: {e}")
            import traceback
            print(f"❌ [EMAIL] Traceback: {traceback.format_exc()}")
            print(f"❌ Failed to send review notification: {e}")
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

    async def send_synopsis_approval(
        self,
        client_email: str,
        client_name: Optional[str],
        project_id: str,
        validation_id: str,
        synopsis: str,
        dossier_data: Dict[str, Any],
        checklist: Dict[str, Any],
        review_notes: Optional[str] = None
    ) -> bool:
        """
        Send synopsis approval email to all admins with the synopsis document.
        
        Args:
            client_email: Client email address (for context in email)
            client_name: Client name (optional)
            project_id: Project ID
            validation_id: Validation ID
            synopsis: The approved synopsis text
            dossier_data: Story dossier data for context
            checklist: Synopsis review checklist
            review_notes: Review notes (optional)
        
        Returns:
            bool: True if email sent successfully
        """
        print(f"📧 [EMAIL] Starting synopsis approval email send...")
        print(f"📧 [EMAIL] Provider: {self.provider}")
        
        # Get admin emails from CLIENT_EMAIL env var (comma-separated)
        internal_emails_str = self.client_email
        if not internal_emails_str:
            print(f"⚠️ [EMAIL] No admin emails configured (CLIENT_EMAIL env var is empty)")
            return False
        
        # Parse comma-separated emails
        internal_emails = [email.strip() for email in internal_emails_str.split(",") if email.strip()]
        if not internal_emails:
            print(f"⚠️ [EMAIL] No valid admin emails found in CLIENT_EMAIL")
            return False
        
        print(f"📧 [EMAIL] Recipients: {internal_emails}")
        print(f"📧 [EMAIL] Project ID: {project_id}")
        print(f"📧 [EMAIL] Validation ID: {validation_id}")
        
        try:
            client_display_name = client_name or "Valued Client"
            story_title = dossier_data.get('title', 'Your Story')
            
            # Build checklist status
            checklist_mapping = {
                'emotional_tone': 'Emotional Tone',
                'accuracy': 'Accuracy vs Intake',
                'clarity': 'Clarity',
                'perspective': 'Perspective',
                'pacing': 'Pacing',
                'sensitivity': 'Sensitivity'
            }
            checklist_status = []
            for key, label in checklist_mapping.items():
                checked = checklist.get(key, False)
                status = "✅" if checked else "⏳"
                checklist_status.append(f"{status} {label}")
            
            # Build email HTML
            synopsis_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Synopsis Approved - {story_title}</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        background-color: #ffffff;
                        border-radius: 8px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        border-bottom: 3px solid #4F46E5;
                        padding-bottom: 20px;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        color: #4F46E5;
                        margin: 0;
                        font-size: 24px;
                    }}
                    .content {{
                        margin-bottom: 30px;
                    }}
                    .synopsis-box {{
                        background-color: #f9fafb;
                        border-left: 4px solid #4F46E5;
                        padding: 20px;
                        margin: 20px 0;
                        border-radius: 4px;
                    }}
                    .synopsis-text {{
                        white-space: pre-wrap;
                        line-height: 1.8;
                        color: #1f2937;
                    }}
                    .checklist {{
                        background-color: #f0f9ff;
                        border: 1px solid #bae6fd;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .checklist h3 {{
                        margin-top: 0;
                        color: #0369a1;
                    }}
                    .checklist-item {{
                        padding: 8px 0;
                        border-bottom: 1px solid #e0f2fe;
                    }}
                    .checklist-item:last-child {{
                        border-bottom: none;
                    }}
                    .footer {{
                        text-align: center;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 24px;
                        background-color: #4F46E5;
                        color: #ffffff;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Synopsis Approved</h1>
                    </div>
                    
                    <div class="content">
                        <p>Dear {client_display_name},</p>
                        
                        <p>We're excited to share that your story synopsis for <strong>"{story_title}"</strong> has been reviewed and approved!</p>
                        
                        <div class="synopsis-box">
                            <h3 style="margin-top: 0; color: #4F46E5;">Your Story Synopsis</h3>
                            <div class="synopsis-text">{synopsis}</div>
                        </div>
                        
                        <div class="checklist">
                            <h3>Review Checklist</h3>
                            {''.join([f'<div class="checklist-item">{item}</div>' for item in checklist_status])}
                        </div>
                        
                        {f'<p><strong>Review Notes:</strong> {review_notes}</p>' if review_notes else ''}
                        
                        <p>Your story is now moving to the script generation phase. We'll keep you updated on the progress.</p>
                        
                        <p>If you have any questions or would like to request changes, please don't hesitate to reach out.</p>
                    </div>
                    
                    <div class="footer">
                        <p>Best regards,<br>
                        The Stories We Tell Team</p>
                        <p>© 2025 Stories We Tell. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            subject = f"Synopsis Approved: {story_title}"
            
            # Send email to all admins
            if self.provider == "smtp":
                print(f"📧 [EMAIL] Sending via SMTP to {len(internal_emails)} recipients...")
                result = self._send_via_smtp(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=synopsis_html
                )
                if result:
                    print(f"✅ [EMAIL] Synopsis approval email sent successfully to {', '.join(internal_emails)}")
                else:
                    print(f"❌ [EMAIL] Failed to send synopsis approval email")
                return result
            else:  # resend
                return self._send_via_resend(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=synopsis_html,
                    from_name="Stories We Tell"
                )
                
        except Exception as e:
            print(f"❌ [EMAIL] Failed to send synopsis approval email: {e}")
            import traceback
            print(f"❌ [EMAIL] Traceback: {traceback.format_exc()}")
            return False

# Global instance
email_service = EmailService()
