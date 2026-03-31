import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
from datetime import datetime


class NotificationService:
    """
    Service for sending email notifications about documents with unresolved comments.
    """

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_user)

    def send_email(self, to_email, subject, body_html):
        """
        Send an email using SMTP configuration.
        """
        if not self.smtp_user or not self.smtp_password:
            print("SMTP credentials not configured. Skipping email send.", flush=True)
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = to_email

            # Attach HTML body
            html_part = MIMEText(body_html, "html")
            msg.attach(html_part)

            # Connect to SMTP server and send
            if self.smtp_port == 465:
                # Use SSL
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                # Use STARTTLS (port 587)
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

            print(f"Email sent successfully to {to_email}", flush=True)
            return True

        except Exception as error:
            print(f"Error sending email to {to_email}: {error}", flush=True)
            return False

    def group_documents_by_owner(self, documents_with_comments):
        """
        Group documents by their owner email addresses.
        
        Args:
            documents_with_comments: List of dicts with keys:
                - id: document ID
                - name: document name
                - owners: list of owner dicts with 'emailAddress' key
                - unresolved_count: number of unresolved comments
        
        Returns:
            Dict mapping owner email to list of documents they own
        """
        owner_docs = defaultdict(list)
        
        for doc in documents_with_comments:
            owners = doc.get("owners", [])
            doc_entry = {
                "id": doc["id"],
                "name": doc["name"],
                "unresolved_count": doc["unresolved_count"],
                "url": f"https://docs.google.com/document/d/{doc['id']}/edit"
            }
            if not owners:
                # No valid owner email found — bucket under sentinel
                owner_docs["__no_owner__"].append(doc_entry)
                continue
            
            # Add document to each owner's list
            for owner in owners:
                owner_email = owner.get("emailAddress")
                if owner_email:
                    owner_docs[owner_email].append(doc_entry)
        
        return dict(owner_docs)

    def generate_email_html(self, owner_email, documents):
        """
        Generate HTML email body for an owner with their documents that have comments.
        """
        total_comments = sum(doc["unresolved_count"] for doc in documents)
        doc_count = len(documents)
        
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Ubuntu', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #E95420;
                    color: white;
                    padding: 20px;
                    border-radius: 5px 5px 0 0;
                }}
                .content {{
                    background-color: #f7f7f7;
                    padding: 20px;
                    border-radius: 0 0 5px 5px;
                }}
                .document {{
                    background-color: white;
                    padding: 15px;
                    margin: 10px 0;
                    border-left: 4px solid #E95420;
                    border-radius: 3px;
                }}
                .document-name {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 5px;
                }}
                .comment-count {{
                    color: #E95420;
                    font-weight: bold;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #E95420;
                    color: white;
                    text-decoration: none;
                    border-radius: 3px;
                    margin-top: 10px;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📝 Library Documents - Unresolved Comments</h2>
                </div>
                <div class="content">
                    <p>Hi there,</p>
                    <p>You have <strong>{doc_count}</strong> document(s) in the Canonical Library with a total of <strong class="comment-count">{total_comments}</strong> unresolved comment(s) that need your attention.</p>
                    
                    <h3>Documents with Unresolved Comments:</h3>
        """
        
        # Add each document
        for doc in documents:
            html += f"""
                    <div class="document">
                        <div class="document-name">{doc['name']}</div>
                        <div><span class="comment-count">{doc['unresolved_count']}</span> unresolved comment(s)</div>
                        <a href="{doc['url']}" class="button">Review Comments</a>
                    </div>
            """
        
        html += f"""
                    <div class="footer">
                        <p>This is an automated notification from the Canonical Library system.</p>
                        <p>Generated on {datetime.now().strftime("%B %d, %Y at %H:%M UTC")}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

    def send_weekly_comment_notifications(self, documents_with_comments):
        """
        Send notification emails to document owners about unresolved comments.
        
        Args:
            documents_with_comments: List of documents with unresolved comments
            
        Returns:
            Dict with statistics about emails sent
        """
        # Group documents by owner
        owner_docs = self.group_documents_by_owner(documents_with_comments)
        
        stats = {
            "total_owners": sum(1 for k in owner_docs if k != "__no_owner__"),
            "emails_sent": 0,
            "emails_failed": 0,
            "total_documents": len(documents_with_comments),
            "total_comments": sum(doc["unresolved_count"] for doc in documents_with_comments)
        }
        
        # Send email to each owner (skip the no-owner sentinel bucket)
        for owner_email, documents in owner_docs.items():
            if owner_email == "__no_owner__":
                continue
            subject = f"Library: {len(documents)} document(s) with unresolved comments"
            body_html = self.generate_email_html(owner_email, documents)
            
            if self.send_email(owner_email, subject, body_html):
                stats["emails_sent"] += 1
            else:
                stats["emails_failed"] += 1
        
        return stats
