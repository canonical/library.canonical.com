# flake8: noqa
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from webapp.models import Document


class LinkValidator:
    def __init__(
        self,
        base_url="http://localhost:8051",
        timeout=20,
        max_workers=10,
        page_timeout=20,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout  # Timeout for checking external links
        self.page_timeout = page_timeout  # Timeout for fetching site pages
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def extract_links_from_html(self, html_content, page_url):
        """Extract all links from HTML content."""
        soup = BeautifulSoup(html_content, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Skip anchors, mailto, javascript, tel links
            if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue

            # Convert relative URLs to absolute
            absolute_url = urljoin(page_url, href)
            links.append(
                {
                    "url": absolute_url,
                    "text": a_tag.get_text(strip=True)[
                        :100
                    ],  # First 100 chars
                    "source_page": page_url,
                }
            )

        return links

    def check_link(self, link_info):
        """Check if a single link is working."""
        url = link_info["url"]
        # Handle both 'source_page' (singular) and 'source_pages' (plural list)
        source_page = link_info.get("source_page") or (
            link_info.get("source_pages", [""])[0]
            if link_info.get("source_pages")
            else ""
        )

        try:
            # Use HEAD request for faster checking
            response = self.session.head(
                url, timeout=self.timeout, allow_redirects=True
            )

            # If HEAD not allowed, try GET
            if response.status_code == 405:
                response = self.session.get(
                    url, timeout=self.timeout, allow_redirects=True
                )

            return {
                "url": url,
                "status_code": response.status_code,
                "status": "ok" if response.status_code < 400 else "broken",
                "error": None,
                "source_page": source_page,
                "link_text": link_info["text"],
            }
        except requests.exceptions.Timeout:
            return {
                "url": url,
                "status_code": None,
                "status": "broken",
                "error": "Timeout",
                "source_page": source_page,
                "link_text": link_info["text"],
            }
        except requests.exceptions.ConnectionError:
            return {
                "url": url,
                "status_code": None,
                "status": "broken",
                "error": "Connection Error",
                "source_page": source_page,
                "link_text": link_info["text"],
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "status": "broken",
                "error": str(e)[:100],
                "source_page": source_page,
                "link_text": link_info["text"],
            }

    def validate_site_links(self, url_list):
        """
        Validate all links across the site.
        Returns a report dictionary with broken links categorized.
        """
        print(
            f"[link-validator] Starting validation of {len(url_list)} pages",
            flush=True,
        )

        all_links = []
        unique_links = {}  # url -> [source_pages]

        # Step 1: Extract all links from all pages
        for url_path in url_list:
            full_url = f"{self.base_url}{url_path}"
            try:
                # Use longer timeout for fetching site pages, with retry
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        response = self.session.get(
                            full_url, timeout=self.page_timeout
                        )
                        if response.status_code == 200:
                            links = self.extract_links_from_html(
                                response.text, full_url
                            )
                            all_links.extend(links)
                        break  # Success, exit retry loop
                    except requests.exceptions.Timeout:
                        if attempt < max_retries - 1:
                            print(
                                f"[link-validator] Timeout fetching {url_path}, retrying...",
                                flush=True,
                            )
                        else:
                            raise  # Re-raise on final attempt
            except Exception as e:
                print(
                    f"[link-validator] Failed to fetch {url_path}: {e}",
                    flush=True,
                )
                continue  # Skip this page and move to next

        print(
            f"[link-validator] Extracted {len(all_links)} total links",
            flush=True,
        )

        # Step 2: Deduplicate links but track all source pages
        for link in all_links:
            url = link["url"]
            if url not in unique_links:
                unique_links[url] = {
                    "url": url,
                    "text": link["text"],
                    "source_pages": [link["source_page"]],
                }
            else:
                if (
                    link["source_page"]
                    not in unique_links[url]["source_pages"]
                ):
                    unique_links[url]["source_pages"].append(
                        link["source_page"]
                    )

        print(
            f"[link-validator] Checking {len(unique_links)} unique links",
            flush=True,
        )

        # Step 3: Check all unique links in parallel
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_link = {
                executor.submit(self.check_link, link_info): link_info
                for link_info in unique_links.values()
            }

            for future in as_completed(future_to_link):
                result = future.result()
                # Add all source pages to result
                result["source_pages"] = unique_links[result["url"]][
                    "source_pages"
                ]
                results.append(result)

        # Step 4: Categorize results
        broken_links = [r for r in results if r["status"] == "broken"]
        working_links = [r for r in results if r["status"] == "ok"]

        # Categorize broken links by type
        internal_broken = []
        external_broken = []

        for link in broken_links:
            parsed = urlparse(link["url"])
            if parsed.netloc == urlparse(self.base_url).netloc or link[
                "url"
            ].startswith("/"):
                internal_broken.append(link)
            else:
                external_broken.append(link)

        report = {
            "total_links_checked": len(results),
            "working_links": len(working_links),
            "broken_links": len(broken_links),
            "internal_broken": internal_broken,
            "external_broken": external_broken,
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(
            f"[link-validator] Validation complete: {len(working_links)} working, {len(broken_links)} broken",
            flush=True,
        )

        return report

    def validate_site_links_from_db(self):
        """
        Validate all links across the site using HTML from database.
        Much faster than fetching pages over HTTP.
        Returns a report dictionary with broken links categorized.
        """
        print(
            "[link-validator] Starting validation using database HTML",
            flush=True,
        )

        # Query all documents from database
        documents = Document.query.all()
        print(
            f"[link-validator] Found {len(documents)} documents in database",
            flush=True,
        )

        all_links = []
        unique_links = {}  # url -> [source_pages]

        # Step 1: Extract all links from database HTML
        for doc in documents:
            if not doc.full_html:
                continue

            # Construct the full URL for this document
            doc_url = (
                f"{self.base_url}/{doc.path}" if doc.path else self.base_url
            )

            try:
                links = self.extract_links_from_html(doc.full_html, doc_url)
                all_links.extend(links)
            except Exception as e:
                print(
                    f"[link-validator] Failed to parse HTML for {doc.path}: {e}",
                    flush=True,
                )
                continue

        print(
            f"[link-validator] Extracted {len(all_links)} total links from database",
            flush=True,
        )

        # Step 2: Deduplicate links but track all source pages
        for link in all_links:
            url = link["url"]
            if url not in unique_links:
                unique_links[url] = {
                    "url": url,
                    "text": link["text"],
                    "source_pages": [link["source_page"]],
                }
            else:
                if (
                    link["source_page"]
                    not in unique_links[url]["source_pages"]
                ):
                    unique_links[url]["source_pages"].append(
                        link["source_page"]
                    )

        print(
            f"[link-validator] Checking {len(unique_links)} unique links",
            flush=True,
        )

        # Step 3: Check all unique links in parallel
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_link = {
                executor.submit(self.check_link, link_info): link_info
                for link_info in unique_links.values()
            }

            for future in as_completed(future_to_link):
                result = future.result()
                # Add all source pages to result
                result["source_pages"] = unique_links[result["url"]][
                    "source_pages"
                ]
                results.append(result)

        # Step 4: Categorize results
        broken_links = [r for r in results if r["status"] == "broken"]
        working_links = [r for r in results if r["status"] == "ok"]

        # Categorize broken links by type
        internal_broken = []
        external_broken = []

        for link in broken_links:
            parsed = urlparse(link["url"])
            if parsed.netloc == urlparse(self.base_url).netloc or link[
                "url"
            ].startswith("/"):
                internal_broken.append(link)
            else:
                external_broken.append(link)

        report = {
            "total_links_checked": len(results),
            "working_links": len(working_links),
            "broken_links": len(broken_links),
            "internal_broken": internal_broken,
            "external_broken": external_broken,
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(
            f"[link-validator] Validation complete: {len(working_links)} working, {len(broken_links)} broken",
            flush=True,
        )

        return report

    def generate_html_report(self, report):
        """Generate an HTML email report from validation results."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; margin-top: 30px; }}
                .summary {{ 
                    background: #f5f5f5; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 20px 0; 
                }}
                .summary p {{ margin: 5px 0; }}
                table {{ 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin: 20px 0; 
                }}
                th {{ 
                    background: #e74c3c; 
                    color: white; 
                    padding: 10px; 
                    text-align: left; 
                }}
                td {{ 
                    padding: 8px; 
                    border-bottom: 1px solid #ddd; 
                }}
                tr:hover {{ background: #f5f5f5; }}
                .url {{ 
                    color: #3498db; 
                    word-break: break-all; 
                }}
                .error {{ color: #e74c3c; }}
                .status-code {{ font-weight: bold; }}
                .source-page {{ 
                    font-size: 0.9em; 
                    color: #666; 
                    margin-top: 5px; 
                }}
                .ok {{ color: #27ae60; }}
            </style>
        </head>
        <body>
            <h1>📊 Weekly Link Validation Report</h1>
            <p><strong>Generated:</strong> {report['timestamp']}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Total Links Checked:</strong> {report['total_links_checked']}</p>
                <p class="ok"><strong>✓ Working Links:</strong> {report['working_links']}</p>
                <p class="error"><strong>✗ Broken Links:</strong> {report['broken_links']}</p>
                <p style="margin-left: 20px;"><strong>Internal Broken:</strong> {len(report['internal_broken'])}</p>
                <p style="margin-left: 20px;"><strong>External Broken:</strong> {len(report['external_broken'])}</p>
            </div>
        """

        if report["internal_broken"]:
            html += """
            <h2>🔴 Broken Internal Links</h2>
            <p>These links point to pages within your site that are not working:</p>
            <table>
                <tr>
                    <th>Link URL</th>
                    <th>Status / Error</th>
                    <th>Link Text</th>
                    <th>Found On Pages</th>
                </tr>
            """
            for link in report["internal_broken"]:
                status = (
                    f"<span class='status-code'>{link['status_code']}</span>"
                    if link["status_code"]
                    else f"<span class='error'>{link['error']}</span>"
                )
                source_pages = "<br>".join(
                    [
                        f"<div class='source-page'>{page}</div>"
                        for page in link["source_pages"][:5]
                    ]
                )
                if len(link["source_pages"]) > 5:
                    source_pages += f"<div class='source-page'>... and {len(link['source_pages']) - 5} more</div>"

                html += f"""
                <tr>
                    <td class="url">{link['url']}</td>
                    <td>{status}</td>
                    <td>{link['link_text']}</td>
                    <td>{source_pages}</td>
                </tr>
                """
            html += "</table>"

        if report["external_broken"]:
            html += """
            <h2>🟠 Broken External Links</h2>
            <p>These links point to external sites that are not working:</p>
            <table>
                <tr>
                    <th>Link URL</th>
                    <th>Status / Error</th>
                    <th>Link Text</th>
                    <th>Found On Pages</th>
                </tr>
            """
            for link in report["external_broken"]:
                status = (
                    f"<span class='status-code'>{link['status_code']}</span>"
                    if link["status_code"]
                    else f"<span class='error'>{link['error']}</span>"
                )
                source_pages = "<br>".join(
                    [
                        f"<div class='source-page'>{page}</div>"
                        for page in link["source_pages"][:5]
                    ]
                )
                if len(link["source_pages"]) > 5:
                    source_pages += f"<div class='source-page'>... and {len(link['source_pages']) - 5} more</div>"

                html += f"""
                <tr>
                    <td class="url">{link['url']}</td>
                    <td>{status}</td>
                    <td>{link['link_text']}</td>
                    <td>{source_pages}</td>
                </tr>
                """
            html += "</table>"

        if not report["internal_broken"] and not report["external_broken"]:
            html += """
            <h2 class="ok">✅ All Links Are Working!</h2>
            <p>No broken links were found during this validation run.</p>
            """

        html += """
        </body>
        </html>
        """

        return html

    def send_email_report(self, report, recipient_email):
        """Send the validation report via email."""
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        if not smtp_user or not smtp_password:
            print(
                "[link-validator] SMTP credentials not configured", flush=True
            )
            return False

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"Link Validation Report - {report['broken_links']} Broken Links"
        )
        msg["From"] = smtp_user
        msg["To"] = recipient_email

        # Generate HTML report
        html_content = self.generate_html_report(report)

        # Attach HTML
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Send email
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            print(
                f"[link-validator] Email report sent to {recipient_email}",
                flush=True,
            )
            return True
        except Exception as e:
            print(f"[link-validator] Failed to send email: {e}", flush=True)
            return False


def validate_and_report(app, base_url="http://localhost:8051"):
    """
    Main function to run link validation and send report.
    Uses database HTML when available (much faster), falls back to HTTP fetching.
    Designed to be called from the scheduler.
    """
    with app.app_context():
        # Get recipient email from environment
        recipient_email = os.getenv("LINK_REPORT_EMAIL") or os.getenv(
            "SMTP_USER"
        )

        if not recipient_email:
            print("[link-validator] No recipient email configured", flush=True)
            return

        # Get configurable timeouts from environment
        link_timeout = int(
            os.getenv("LINK_CHECK_TIMEOUT", "10")
        )  # Timeout for checking links
        max_workers = int(
            os.getenv("LINK_CHECK_WORKERS", "10")
        )  # Parallel workers

        # Create validator
        validator = LinkValidator(
            base_url=base_url, timeout=link_timeout, max_workers=max_workers
        )

        # Try to use database first (much faster)
        if "POSTGRESQL_DB_CONNECT_STRING" in os.environ:
            try:
                print(
                    "[link-validator] Using database HTML for validation",
                    flush=True,
                )
                report = validator.validate_site_links_from_db()
            except Exception as e:
                print(
                    f"[link-validator] Database method failed: {e}, falling back to HTTP",
                    flush=True,
                )
                # Fallback to HTTP method
                report = None
        else:
            report = None

        # Fallback to HTTP fetching if database not available or failed
        if report is None:
            print(
                "[link-validator] Using HTTP fetching for validation",
                flush=True,
            )
            # Get URL list
            url_file_path = os.path.join(
                app.static_folder, "assets", "url_list.txt"
            )

            if not os.path.exists(url_file_path):
                print(
                    f"[link-validator] URL list not found at {url_file_path}",
                    flush=True,
                )
                return

            with open(url_file_path, "r") as f:
                urls = [line.strip() for line in f if line.strip()]

            if not urls:
                print("[link-validator] No URLs to validate", flush=True)
                return

            page_timeout = int(
                os.getenv("PAGE_FETCH_TIMEOUT", "60")
            )  # Timeout for fetching pages
            validator.page_timeout = page_timeout
            report = validator.validate_site_links(urls)

        # Send report
        validator.send_email_report(report, recipient_email)

        print(
            f"[link-validator] Validation complete: {report['broken_links']} broken links found",
            flush=True,
        )
