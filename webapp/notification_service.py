# fmt: off
# flake8: noqa
import os
import socket as _socket
import smtplib
from urllib.parse import urlsplit
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

    def _get_proxy(self):
        """
        Return (host, port) from HTTP_PROXY / HTTPS_PROXY env vars, or None.
        Handles credentials (user:pass@host), IPv6 literals, and validates port.
        """
        proxy_url = None
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            proxy_url = os.getenv(key)
            if proxy_url:
                break
        if not proxy_url:
            return None
        proxy_url = proxy_url.strip()
        # urlsplit requires a scheme to parse host/port correctly
        if "://" not in proxy_url:
            proxy_url = "http://" + proxy_url
        parsed = urlsplit(proxy_url)
        host = parsed.hostname
        if not host:
            return None
        try:
            port = int(parsed.port) if parsed.port is not None else 3128
        except (ValueError, TypeError):
            return None
        return host, port

    def _open_tunnel(self):
        """
        Open an HTTP CONNECT tunnel through the Squid proxy to the SMTP host.
        Returns a connected plain socket, or None if no proxy is configured.
        Raises OSError if the proxy rejects the CONNECT request.
        """
        proxy = self._get_proxy()
        if proxy is None:
            return None
        proxy_host, proxy_port = proxy
        print(
            f"[smtp] CONNECT tunnel via {proxy_host}:{proxy_port}"
            f" -> {self.smtp_host}:{self.smtp_port}",
            flush=True,
        )
        sock = _socket.create_connection((proxy_host, proxy_port), timeout=30)
        connect_req = (
            f"CONNECT {self.smtp_host}:{self.smtp_port} HTTP/1.1\r\n"
            f"Host: {self.smtp_host}:{self.smtp_port}\r\n"
            "\r\n"
        )
        sock.sendall(connect_req.encode())
        # Read until end of response headers
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                raise OSError("Proxy closed connection during CONNECT")
            resp += chunk
        first_line = resp.split(b"\r\n")[0].decode(errors="replace")
        status = first_line.split(" ", 2)
        if len(status) < 2 or status[1] != "200":
            sock.close()
            raise OSError(f"Proxy CONNECT failed: {first_line}")
        print("[smtp] CONNECT tunnel established", flush=True)
        return sock

    def send_email(self, to_email, subject, body_html):
        """
        Send an email using SMTP.  When an HTTP proxy is detected the
        connection is made via an HTTP CONNECT tunnel so that raw TCP to
        port 587/465 is never opened directly from the pod.
        """
        if not self.smtp_user or not self.smtp_password:
            print(
                "SMTP credentials not configured. Skipping email send.",
                flush=True,
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = to_email
            msg.attach(MIMEText(body_html, "html"))

            tunnel_sock = self._open_tunnel()

            # When a proxy tunnel is available, build a thin smtplib subclass
            # that returns the pre-connected socket instead of dialling
            # directly, so the proxy carries the SMTP traffic.
            if tunnel_sock is not None:
                if self.smtp_port == 465:
                    class _SMTP(smtplib.SMTP_SSL):
                        def _get_socket(self, host, port, timeout):
                            return self.context.wrap_socket(
                                tunnel_sock, server_hostname=host
                            )
                else:
                    class _SMTP(smtplib.SMTP):
                        def _get_socket(self, host, port, timeout):
                            return tunnel_sock
            else:
                _SMTP = smtplib.SMTP_SSL if self.smtp_port == 465 else smtplib.SMTP

            if self.smtp_port == 465:
                with _SMTP(self.smtp_host, self.smtp_port) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                with _SMTP(self.smtp_host, self.smtp_port) as server:
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
        owner_names = {}  # email -> display name

        for doc in documents_with_comments:
            owners = doc.get("owners", [])
            doc_entry = {
                "id": doc["id"],
                "name": doc["name"],
                "unresolved_count": doc["unresolved_count"],
                "url": f"https://docs.google.com/document/d/{doc['id']}/edit",
                "path": doc.get("path", ""),
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
                    # Store name keyed by email; prefer a real name over the email itself
                    owner_name = owner.get("name") or owner_email
                    if owner_email not in owner_names:
                        owner_names[owner_email] = owner_name

        return dict(owner_docs), owner_names

    def generate_email_html(self, owner_email, documents, owner_name=None):
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
                    background-color: white;
                    color: #E95420;
                    text-decoration: none;
                    border: 2px solid #E95420;
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
                    <h2>Library documents with unresolved comments</h2>
                </div>
                <div class="content">
                    <p>Hi {owner_name},</p>
                    <p>You have <strong>{doc_count}</strong> document(s) in the Canonical Library with a total of <strong class="comment-count">{total_comments}</strong> unresolved comment(s) that need your attention.</p>
                    
                    <h3>Documents with Unresolved Comments:</h3>
        """

        # Add each document
        for doc in documents:
            html += f"""
                    <div class="document">
                        <div class="document-name">{doc['name']}</div>
                        <div><span class="comment-count">{doc['unresolved_count']}</span> unresolved comment(s)</div>
                        <div>Path: {doc['path']}</div>
                        <a href="{doc['url']}" style="display:inline-block;padding:10px 20px;background-color:white;color:#E95420;text-decoration:none;border:2px solid #E95420;margin-top:10px;">Review Comments</a>
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
        owner_docs, owner_names = self.group_documents_by_owner(
            documents_with_comments
        )

        stats = {
            "total_owners": sum(1 for k in owner_docs if k != "__no_owner__"),
            "emails_sent": 0,
            "emails_failed": 0,
            "total_documents": len(documents_with_comments),
            "total_comments": sum(
                doc["unresolved_count"] for doc in documents_with_comments
            ),
        }

        # Send email to each owner (skip the no-owner sentinel bucket)
        for owner_email, documents in owner_docs.items():
            print(
                f"Processing:{owner_email} with {len(documents)} document(s)",
                flush=True,
            )
            if owner_email == "__no_owner__":
                continue
            owner_name = owner_names.get(owner_email)
            subject = f"Library: {len(documents)} document(s) with comments"
            body_html = self.generate_email_html(
                owner_email, documents, owner_name=owner_name
            )
            if os.getenv("TEST_EMAIL", "").lower() == "true":
                if owner_email == "nicolas.bello@canonical.com":
                    if self.send_email(owner_email, subject, body_html):
                        stats["emails_sent"] += 1
                    else:
                        stats["emails_failed"] += 1  
            else:
                if self.send_email(owner_email, subject, body_html):
                    stats["emails_sent"] += 1
                else:
                    stats["emails_failed"] += 1  

        return stats
