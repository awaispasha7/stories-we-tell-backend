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
        client_emails: Optional[List[str]] = None,
        genre_predictions: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send email notification when story is captured to CLIENT (admins).
        NOTE: "client" refers to the admin team, not the story writer.
        
        Args:
            user_email: Story writer's email (for context in email, not recipient)
            user_name: Story writer's name (for context)
            story_data: Captured story data from dossier
            generated_script: Generated video script (kept for backward compatibility, not displayed)
            project_id: Project ID for reference
            client_emails: Optional list of admin emails (if not provided, uses CLIENT_EMAIL env var)
            genre_predictions: Optional list of genre predictions with confidence scores
            
        Returns:
            bool: True if email sent successfully
        """
        if not self.available:
            print("⚠️ Email service not available - skipping email notification")
            return False
        
        try:
            # Build email content
            story_title = story_data.get('title', 'Untitled Story')
            subject = f"New Story Captured: {story_title}"
            
            # Create story summary
            story_summary = self._build_story_summary(story_data)
            
            # Get genre predictions from story_data if not provided
            if not genre_predictions and story_data:
                genre_predictions = story_data.get('genre_predictions')
            
            # Get admin emails (CLIENT = admins)
            if client_emails:
                admin_emails = client_emails
            elif self.client_email:
                # Parse comma-separated CLIENT_EMAIL env var
                admin_emails = [email.strip() for email in self.client_email.split(",") if email.strip()]
            else:
                print("⚠️ No admin emails configured (CLIENT_EMAIL env var is empty)")
                return False
            
            if not admin_emails:
                print("⚠️ No admin emails to send to")
                return False
            
            # Build email HTML for admins
            html_content = self._build_story_captured_admin_email_html(
                story_writer_name=user_name or "Anonymous",
                story_writer_email=user_email or "N/A",
                story_data=story_data,
                story_summary=story_summary,
                project_id=project_id,
                genre_predictions=genre_predictions
            )
            
            # Send email to admins (CLIENT)
            if self.provider == "smtp":
                return self._send_via_smtp(
                    to_emails=admin_emails,
                    subject=subject,
                    html_content=html_content
                )
            else:  # resend
                return self._send_via_resend(
                    to_emails=admin_emails,
                    subject=subject,
                    html_content=html_content,
                    from_name="Stories We Tell"
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
            
            # Create validation HTML content - Updated for multi-step validation workflow
            validation_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }}
                    .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .email-wrapper {{ background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 24px; }}
                    .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                    .content {{ padding: 30px; }}
                    .highlight {{ background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 20px 0; }}
                    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
                    .info-item {{ padding: 10px; background: #f8f9fa; border-radius: 6px; }}
                    .info-label {{ font-weight: 600; color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
                    .info-value {{ color: #333; font-size: 14px; }}
                    .action-button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; margin: 20px 0; text-align: center; }}
                    .action-button:hover {{ opacity: 0.9; }}
                    .workflow-steps {{ background: #f0f4ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                    .workflow-steps h3 {{ margin-top: 0; color: #667eea; }}
                    .workflow-steps ol {{ margin: 10px 0; padding-left: 20px; }}
                    .workflow-steps li {{ margin: 8px 0; color: #555; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; border-top: 1px solid #e5e7eb; }}
                    @media only screen and (max-width: 600px) {{
                        .container {{ padding: 10px; }}
                        .content {{ padding: 20px; }}
                        .info-grid {{ grid-template-columns: 1fr; }}
                        .action-button {{ display: block; width: 100%; box-sizing: border-box; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="email-wrapper">
                        <div class="header">
                            <h1>📋 New Story Validation Request</h1>
                            <p>A completed story has been submitted and requires validation</p>
                        </div>
                        
                        <div class="content">
                            <div class="highlight">
                                <div class="info-grid">
                                    <div class="info-item">
                                        <div class="info-label">Project ID</div>
                                        <div class="info-value">{project_id}</div>
                                    </div>
                                    <div class="info-item">
                                        <div class="info-label">Validation ID</div>
                                        <div class="info-value">{validation_id or 'N/A'}</div>
                                    </div>
                                    <div class="info-item">
                                        <div class="info-label">Client Name</div>
                                        <div class="info-value">{client_name or 'Anonymous'}</div>
                                    </div>
                                    <div class="info-item">
                                        <div class="info-label">Client Email</div>
                                        <div class="info-value">{client_email or 'No email provided'}</div>
                                    </div>
                                </div>
                                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ffc107;">
                                    <div class="info-label">Story Title</div>
                                    <div class="info-value" style="font-size: 18px; font-weight: 600; color: #333;">{story_data.get('title', 'Untitled Story')}</div>
                                </div>
                            </div>
                            
                            <div class="workflow-steps">
                                <h3>📝 Validation Workflow</h3>
                                <p style="margin-bottom: 15px; color: #555;">This story will go through the following validation steps:</p>
                                <ol>
                                    <li><strong>Step 9 - Dossier Review:</strong> Review story completeness, character logic, photos, timeline, setting, tone, and perspective</li>
                                    <li><strong>Step 10 - Synopsis Generation:</strong> Generate a comprehensive synopsis (500-800 words)</li>
                                    <li><strong>Step 11 - Synopsis Review:</strong> Review and approve the synopsis</li>
                                    <li><strong>Step 12 - Script Generation:</strong> Generate multiple genre-specific scripts (user selects preferred genre)</li>
                                    <li><strong>Step 13 - Shot List Creation:</strong> Create detailed shot list from selected script</li>
                                    <li><strong>Step 14+ - Final Review & Delivery:</strong> Complete final review and deliver to client</li>
                                </ol>
                            </div>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{self.frontend_url}/admin/validate/{validation_id or project_id}" class="action-button" style="color: white !important; text-decoration: none;">
                                    🔍 Review Story in Admin Panel
                                </a>
                            </div>
                            
                            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                                <p style="margin: 0; color: #666; font-size: 14px;">
                                    <strong>Note:</strong> The validation process includes multiple review steps. Use the admin panel to navigate through each step and complete the validation workflow.
                                </p>
                            </div>
                        </div>
                        
                        <div class="footer">
                            <p>This is an automated notification from Stories We Tell</p>
                            <p>© 2026 Stories We Tell. All rights reserved.</p>
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
        project_id: str,
        genre_predictions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build HTML email content - Note: generated_script parameter is kept for backward compatibility but not displayed"""
        
        # Build genre predictions HTML if available
        genre_predictions_html = ""
        if genre_predictions:
            genre_predictions_html = """
            <div style="background: #e0f7fa; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #00bcd4;">
                <h3 style="margin-top: 0; color: #00838f;">Detected Genres</h3>
                <p style="margin-bottom: 10px; font-size: 14px; color: #333;">Based on your story, here are the top predicted genres:</p>
                <ul style="list-style: none; padding: 0; margin: 0;">
            """
            for gp in genre_predictions:
                genre_name = gp.get('genre', 'Unknown')
                confidence = gp.get('confidence', 0.0)
                genre_predictions_html += f"""
                    <li style="padding: 5px 0; font-size: 15px; color: #333;">
                        <strong>{genre_name}:</strong> {confidence:.0%}
                    </li>
                """
            genre_predictions_html += """
                </ul>
                <p style="margin: 10px 0 0 0; font-size: 13px; color: #666;">Click the 'Set Genre' button below to select your preferred genre.</p>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your Story is Ready!</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .story-summary {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                h1 {{ margin: 0; font-size: 28px; }}
                h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                .highlight {{ background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107; }}
                .button-container {{ margin: 30px 0; text-align: center; }}
                .email-button {{ display: inline-block; margin: 10px 5px; padding: 15px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; min-width: 200px; box-sizing: border-box; }}
                .email-button.secondary {{ background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color: white !important; }}
                .email-button:hover {{ opacity: 0.9; color: white !important; }}
                @media only screen and (max-width: 600px) {{
                    .container {{ padding: 10px; width: 100% !important; max-width: 100% !important; }}
                    .content {{ padding: 20px; }}
                    .button-container {{ margin: 20px 0; text-align: center; }}
                    .email-button {{ display: block; width: 100% !important; margin: 10px 0 !important; min-width: auto !important; max-width: 100% !important; box-sizing: border-box !important; }}
                    h1 {{ font-size: 24px; }}
                    h2 {{ font-size: 20px; }}
                }}
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
                    
                    <p>We're excited to let you know that your story has been successfully captured!</p>
                    
                    <div class="highlight">
                        <strong>Story Title:</strong> {story_data.get('title', 'Untitled Story')}
                    </div>
                    
                    {genre_predictions_html}
                    
                    <p>Your story is now in our system and is being reviewed by our team. We want to make sure everything is perfect before we proceed with the next steps.</p>
                    
                    <p style="font-size: 15px; color: #333; margin: 15px 0; padding: 15px; background: #f0f9ff; border-left: 4px solid #3b82f6; border-radius: 4px;">
                        <strong>What happens next?</strong><br>
                        Our team will review your story and may reach out if we need any additional information. Please keep an eye on your email for updates from us.
                    </p>
                    
                    <div class="button-container">
                        <a href="{self.frontend_url}/chat?projectId={project_id}" class="email-button" style="color: white !important; text-decoration: none; display: inline-block;">View Story in Dashboard</a>
                    </div>
                    
                    <p>Thank you for sharing your story with us. We're honored to help bring it to life!</p>
                    
                    <p>Best regards,<br>
                    The Stories We Tell Team</p>
                </div>
                
                <div class="footer">
                    <p>This email was automatically generated when the story was captured.</p>
                    <p>© 2026 Stories We Tell. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_story_captured_admin_email_html(
        self,
        story_writer_name: str,
        story_writer_email: str,
        story_data: Dict[str, Any],
        story_summary: str,
        project_id: str,
        genre_predictions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build HTML email content for admins (CLIENT) when story is captured"""
        
        # Build genre predictions HTML if available
        genre_predictions_html = ""
        if genre_predictions:
            genre_predictions_html = """
            <div style="background: #e0f7fa; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #00bcd4;">
                <h3 style="margin-top: 0; color: #00838f;">🎭 Detected Genres</h3>
                <p style="margin-bottom: 10px; font-size: 14px; color: #333;">Based on the story, here are the top predicted genres:</p>
                <ul style="list-style: none; padding: 0; margin: 0;">
            """
            for gp in genre_predictions:
                genre_name = gp.get('genre', 'Unknown')
                confidence = gp.get('confidence', 0.0)
                genre_predictions_html += f"""
                    <li style="padding: 5px 0; font-size: 15px; color: #333;">
                        <strong>{genre_name}:</strong> {confidence:.0%}
                    </li>
                """
            genre_predictions_html += """
                </ul>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>New Story Captured</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .story-summary {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                h1 {{ margin: 0; font-size: 28px; }}
                h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                .highlight {{ background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107; }}
                .button-container {{ margin: 30px 0; text-align: center; }}
                .email-button {{ display: inline-block; margin: 10px 5px; padding: 15px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; min-width: 200px; box-sizing: border-box; }}
                .email-button.secondary {{ background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color: white !important; }}
                .email-button:hover {{ opacity: 0.9; color: white !important; }}
                @media only screen and (max-width: 600px) {{
                    .container {{ padding: 10px; width: 100% !important; max-width: 100% !important; }}
                    .content {{ padding: 20px; }}
                    .button-container {{ margin: 20px 0; text-align: center; }}
                    .email-button {{ display: block; width: 100% !important; margin: 10px 0 !important; min-width: auto !important; max-width: 100% !important; box-sizing: border-box !important; }}
                    h1 {{ font-size: 24px; }}
                    h2 {{ font-size: 20px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 New Story Captured!</h1>
                    <p>A new story has been submitted and is ready for review</p>
                </div>
                
                <div class="content">
                    <p>Dear Team,</p>
                    
                    <p>A new story has been successfully captured and is ready for your review!</p>
                    
                    <div class="highlight">
                        <strong>Story Title:</strong> {story_data.get('title', 'Untitled Story')}
                    </div>
                    
                    <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0;"><strong>Story Writer:</strong> {story_writer_name}</p>
                        <p style="margin: 0;"><strong>Writer Email:</strong> {story_writer_email}</p>
                    </div>
                    
                    {genre_predictions_html}
                    
                    <p>The story is now in the validation queue and ready for your review. Please proceed to the admin panel to begin the review process.</p>
                    
                    <div class="button-container">
                        <a href="{self.frontend_url}/admin/validate?projectId={project_id}" class="email-button" style="color: white !important; text-decoration: none; display: inline-block;">Review Story in Admin Panel</a>
                    </div>
                    
                    <p>Best regards,<br>
                    The Stories We Tell System</p>
                </div>
                
                <div class="footer">
                    <p>This email was automatically generated when the story was captured.</p>
                    <p>© 2026 Stories We Tell. All rights reserved.</p>
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
            story_title = dossier_data.get('title', 'Your Story')
            
            # Get genre predictions for email
            genre_predictions = dossier_data.get('genre_predictions', [])
            genre_predictions_html = ""
            if genre_predictions:
                genre_predictions_html = "<div style='margin: 20px 0; padding: 15px; background: #f0f4ff; border-radius: 8px; border-left: 4px solid #667eea;'>"
                genre_predictions_html += "<h3 style='margin: 0 0 10px 0; color: #333; font-size: 16px;'>🎭 Detected Genres (with confidence):</h3>"
                genre_predictions_html += "<ul style='margin: 0; padding-left: 20px;'>"
                for pred in genre_predictions[:5]:  # Top 5
                    genre = pred.get('genre', 'Unknown')
                    confidence = pred.get('confidence', 0.0)
                    percentage = int(confidence * 100)
                    genre_predictions_html += f"<li style='margin: 5px 0; color: #555;'><strong>{genre}</strong>: {percentage}%</li>"
                genre_predictions_html += "</ul>"
                genre_predictions_html += "</div>"
            
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
                        <p>Dear Admin,</p>
                        
                        <p>The story synopsis for <strong>"{story_title}"</strong> has been reviewed and approved.</p>
                        
                        <div class="synopsis-box">
                            <h3 style="margin-top: 0; color: #4F46E5;">Story Synopsis</h3>
                            <div class="synopsis-text">{synopsis}</div>
                        </div>
                        
                        {genre_predictions_html}
                        
                        <div class="checklist">
                            <h3>Review Checklist</h3>
                            {''.join([f'<div class="checklist-item">{item}</div>' for item in checklist_status])}
                        </div>
                        
                        {f'<p><strong>Review Notes:</strong> {review_notes}</p>' if review_notes else ''}
                        
                        <p>The story is now moving to the script generation phase. Before generating scripts, please set the genre for this story.</p>
                        
                        <div style="margin: 30px 0; text-align: center;">
                            <a href="{self.frontend_url}/admin/validate/{validation_id}" 
                               style="display: inline-block; padding: 12px 30px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 5px;">
                                View & Manage Validation
                            </a>
                            <a href="{self.frontend_url}/chat?setGenre=true&projectId={project_id}" 
                               style="display: inline-block; padding: 12px 30px; background-color: #8b5cf6; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 5px;">
                                Set Genre
                            </a>
                        </div>
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

    async def send_validation_approval_notification(
        self,
        internal_emails: List[str],
        project_id: str,
        validation_id: str,
        story_data: Dict[str, Any],
        reviewed_by: str,
        review_notes: Optional[str] = None
    ) -> bool:
        """
        Send validation approval notification email to all admins.
        
        Args:
            internal_emails: List of admin email addresses
            project_id: Project ID
            validation_id: Validation ID
            story_data: Story dossier data
            reviewed_by: Admin who approved
            review_notes: Optional review notes
        
        Returns:
            bool: True if email sent successfully
        """
        if not self.available:
            print("⚠️ Email service not available - skipping validation approval notification")
            return False
        
        try:
            story_title = story_data.get('title', 'Your Story')
            subject = f"Validation Approved: {story_title}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
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
                        border-bottom: 3px solid #10b981;
                        padding-bottom: 20px;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        color: #10b981;
                        margin: 0;
                        font-size: 24px;
                    }}
                    .content {{
                        margin-bottom: 30px;
                    }}
                    .info-grid {{
                        display: grid;
                        grid-template-columns: 1fr;
                        gap: 10px;
                        background-color: #f9fafb;
                        border: 1px solid #e5e7eb;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .info-item strong {{
                        color: #1f2937;
                    }}
                    .button-container {{
                        text-align: center;
                        margin: 30px 0;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 24px;
                        background-color: #10b981;
                        color: #ffffff;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                    }}
                    .footer {{
                        text-align: center;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Validation Approved</h1>
                        <p>A validation request has been approved.</p>
                    </div>
                    
                    <div class="content">
                        <p>Dear Team,</p>
                        
                        <p>The validation request for <strong>"{story_title}"</strong> has been approved by <strong>{reviewed_by}</strong>.</p>
                        
                        <div class="info-grid">
                            <div class="info-item"><strong>Project ID:</strong> {project_id}</div>
                            <div class="info-item"><strong>Validation ID:</strong> {validation_id}</div>
                            <div class="info-item"><strong>Reviewed By:</strong> {reviewed_by}</div>
                            {f'<div class="info-item"><strong>Review Notes:</strong> {review_notes}</div>' if review_notes else ''}
                        </div>
                        
                        <p>The story is now approved and ready for the next steps in the workflow.</p>
                        
                        <div class="button-container">
                            <a href="{self.frontend_url}/admin/validate/{validation_id}" class="button">
                                View Validation Details
                            </a>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated notification from Stories We Tell</p>
                        <p>© 2026 Stories We Tell. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            if self.provider == "smtp":
                print(f"📧 [EMAIL] Sending validation approval notification via SMTP to {len(internal_emails)} recipients...")
                result = self._send_via_smtp(
                    to_emails=internal_emails,
                    subject=subject,
                    html_content=html_content
                )
                if result:
                    print(f"✅ [EMAIL] Validation approval notification sent successfully to {', '.join(internal_emails)}")
                else:
                    print(f"❌ [EMAIL] Failed to send validation approval notification")
                return result
            else:
                print("⚠️ Resend is disabled. Validation approval notification not sent via Resend.")
                return False
            
        except Exception as e:
            print(f"❌ [EMAIL] Failed to send validation approval notification: {e}")
            import traceback
            print(f"❌ [EMAIL] Traceback: {traceback.format_exc()}")
            return False

    async def send_revision_request_email(
        self,
        user_email: str,
        user_name: str,
        project_id: str,
        story_data: Dict[str, Any],
        missing_items: List[str],
        flagged_issues: Dict[str, List[str]]
    ) -> bool:
        """
        Send email to client (story writer) when revision is needed (missing information).
        
        Args:
            user_email: Client email address
            user_name: Client name
            project_id: Project ID
            story_data: Story dossier data
            missing_items: List of unchecked checklist items
            flagged_issues: Dictionary of flagged issues (missing_info, conflicts, factual_gaps)
        
        Returns:
            bool: True if email sent successfully
        """
        if not self.available:
            print("⚠️ Email service not available - skipping revision request email")
            return False
        
        try:
            story_title = story_data.get('title', 'Your Story')
            subject = f"Additional Information Needed for Your Story: {story_title}"
            
            # Build missing items list
            missing_items_html = ""
            if missing_items:
                missing_items_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
                for item in missing_items:
                    # Convert key to readable format
                    readable_item = item.replace('_', ' ').title()
                    missing_items_html += f"<li style='margin: 5px 0;'>{readable_item}</li>"
                missing_items_html += "</ul>"
            
            # Build flagged issues list
            issues_html = ""
            if flagged_issues:
                issues_html = "<div style='margin: 15px 0;'>"
                for issue_type, issues in flagged_issues.items():
                    if issues:
                        issue_title = issue_type.replace('_', ' ').title()
                        issues_html += f"<h4 style='color: #dc2626; margin: 10px 0 5px 0;'>{issue_title}:</h4>"
                        issues_html += "<ul style='margin: 5px 0; padding-left: 20px;'>"
                        for issue in issues:
                            issues_html += f"<li style='margin: 5px 0;'>{issue}</li>"
                        issues_html += "</ul>"
                issues_html += "</div>"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{subject}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .alert-box {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                    .button-container {{ margin: 30px 0; text-align: center; }}
                    .email-button {{ display: inline-block; padding: 15px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                    @media only screen and (max-width: 600px) {{
                        .container {{ padding: 10px; width: 100% !important; max-width: 100% !important; }}
                        .content {{ padding: 20px; }}
                        .button-container {{ margin: 20px 0; text-align: center; }}
                        .email-button {{ display: block; width: 100% !important; margin: 10px 0 !important; box-sizing: border-box !important; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📝 Additional Information Needed</h1>
                    </div>
                    
                    <div class="content">
                        <p>Dear {user_name},</p>
                        
                        <p>Thank you for sharing your story <strong>"{story_title}"</strong> with us!</p>
                        
                        <div class="alert-box">
                            <p style="margin: 0; font-weight: bold;">We need a bit more information to complete your story dossier.</p>
                        </div>
                        
                        {f'<p><strong>Missing Information:</strong></p>{missing_items_html}' if missing_items_html else ''}
                        {issues_html if issues_html else ''}
                        
                        <p>Please visit your story dashboard to provide the missing details. Our AI assistant Ariel will guide you through the process.</p>
                        
                        <div class="button-container">
                            <a href="{self.frontend_url}/chat?projectId={project_id}" class="email-button" style="color: white !important; text-decoration: none;">
                                Continue Your Story
                            </a>
                        </div>
                        
                        <p>Thank you for your patience!</p>
                        
                        <p>Best regards,<br>
                        The Stories We Tell Team</p>
                    </div>
                    
                    <div class="footer">
                        <p>© 2026 Stories We Tell. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            if self.provider == "smtp":
                print(f"📧 [EMAIL] Sending revision request email via SMTP to {user_email}...")
                result = self._send_via_smtp(
                    to_emails=[user_email],
                    subject=subject,
                    html_content=html_content
                )
                if result:
                    print(f"✅ [EMAIL] Revision request email sent successfully to {user_email}")
                else:
                    print(f"❌ [EMAIL] Failed to send revision request email")
                return result
            else:
                print("⚠️ Resend is disabled. Revision request email not sent.")
                return False
            
        except Exception as e:
            print(f"❌ [EMAIL] Failed to send revision request email: {e}")
            import traceback
            print(f"❌ [EMAIL] Traceback: {traceback.format_exc()}")
            return False

    async def send_synopsis_approval_client_email(
        self,
        user_email: str,
        user_name: str,
        story_data: Dict[str, Any],
        project_id: str,
        synopsis: str,
        genre_predictions: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send synopsis approval email to the client with Set Genre button.
        
        Args:
            user_email: Client email address
            user_name: Client name
            story_data: Story dossier data
            project_id: Project ID
            synopsis: The approved synopsis text
            genre_predictions: List of genre predictions with confidence scores
        
        Returns:
            bool: True if email sent successfully
        """
        if not self.available:
            print("⚠️ Email service not available - skipping client synopsis approval email")
            return False
        
        try:
            story_title = story_data.get('title', 'Your Story')
            subject = f"Your Story Synopsis Has Been Approved: {story_title}"
            
            # Build genre predictions HTML if available
            genre_predictions_html = ""
            if genre_predictions:
                genre_predictions_html = """
                <div style="background: #e0f7fa; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #00bcd4;">
                    <h3 style="margin-top: 0; color: #00838f;">Detected Genres</h3>
                    <p style="margin-bottom: 10px; font-size: 14px; color: #333;">Based on your story, here are the top predicted genres:</p>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                """
                for gp in genre_predictions:
                    genre_name = gp.get('genre', 'Unknown')
                    confidence = gp.get('confidence', 0.0)
                    genre_predictions_html += f"""
                        <li style="padding: 5px 0; font-size: 15px; color: #333;">
                            <strong>{genre_name}:</strong> {confidence:.0%}
                        </li>
                    """
                genre_predictions_html += """
                    </ul>
                    <p style="margin: 10px 0 0 0; font-size: 13px; color: #666;">Click the 'Set Genre' button below to select your preferred genre.</p>
                </div>
                """
            
            # Build email HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{subject}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .synopsis-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                    h1 {{ margin: 0; font-size: 28px; }}
                    h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
                    .highlight {{ background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107; }}
                    .button-container {{ margin: 30px 0; text-align: center; }}
                    .email-button {{ display: inline-block; margin: 10px 5px; padding: 15px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; min-width: 200px; box-sizing: border-box; }}
                    .email-button.secondary {{ background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color: white !important; }}
                    .email-button:hover {{ opacity: 0.9; color: white !important; }}
                    @media only screen and (max-width: 600px) {{
                        .container {{ padding: 10px; width: 100% !important; max-width: 100% !important; }}
                        .content {{ padding: 20px; }}
                        .button-container {{ margin: 20px 0; text-align: center; }}
                        .email-button {{ display: block; width: 100% !important; margin: 10px 0 !important; min-width: auto !important; max-width: 100% !important; box-sizing: border-box !important; }}
                        h1 {{ font-size: 24px; }}
                        h2 {{ font-size: 20px; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Your Synopsis Has Been Approved!</h1>
                        <p>Your story is moving to the next phase</p>
                    </div>
                    
                    <div class="content">
                        <p>Dear {user_name},</p>
                        
                        <p>Great news! Your story synopsis for <strong>"{story_title}"</strong> has been reviewed and approved by our team.</p>
                        
                        <div class="highlight">
                            <strong>Story Title:</strong> {story_title}
                        </div>
                        
                        <div class="synopsis-box">
                            <h3 style="margin-top: 0; color: #667eea;">Your Approved Synopsis</h3>
                            <div style="white-space: pre-wrap; line-height: 1.8; color: #1f2937;">{synopsis}</div>
                        </div>
                        
                        {genre_predictions_html}
                        
                        <p>Your story is now ready for script generation. Before we proceed, we'd love for you to help us categorize your story by selecting a genre. This helps us create the perfect script tailored to your story's style.</p>
                        
                        <p style="font-size: 14px; color: #666; margin: 12px 0;">Our featured genres include: <strong>Historic Romance</strong>, <strong>Family Saga</strong>, <strong>Childhood Adventure</strong>, <strong>Documentary</strong>, and <strong>Historical Epic</strong>. You can also choose from other genre options or enter a custom genre.</p>
                        
                        <div class="button-container">
                            <a href="{self.frontend_url}/chat?projectId={project_id}" class="email-button" style="color: white !important; text-decoration: none; display: inline-block;">View Story in Dashboard</a>
                            <a href="{self.frontend_url}/chat?setGenre=true&projectId={project_id}" class="email-button secondary" style="color: white !important; text-decoration: none; display: inline-block;">Set Genre</a>
                        </div>
                        
                        <p>Thank you for trusting us with your story. We can't wait to help bring it to life!</p>
                        
                        <p>Best regards,<br>
                        The Stories We Tell Team</p>
                    </div>
                    
                    <div class="footer">
                        <p>This email was automatically generated when your synopsis was approved.</p>
                        <p>© 2026 Stories We Tell. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            if self.provider == "smtp":
                print(f"📧 [EMAIL] Sending client synopsis approval email via SMTP to {user_email}...")
                result = self._send_via_smtp(
                    to_emails=[user_email],
                    subject=subject,
                    html_content=html_content
                )
                if result:
                    print(f"✅ [EMAIL] Client synopsis approval email sent successfully to {user_email}")
                else:
                    print(f"❌ [EMAIL] Failed to send client synopsis approval email")
                return result
            else:  # resend
                print("⚠️ Resend is disabled. Client synopsis approval email not sent via Resend.")
                return False
            
        except Exception as e:
            print(f"❌ [EMAIL] Failed to send client synopsis approval email: {e}")
            import traceback
            print(f"❌ [EMAIL] Traceback: {traceback.format_exc()}")
            return False

# Global instance
email_service = EmailService()
