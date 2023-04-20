import os
from bs4 import BeautifulSoup

from webapp.googledrive import Drive

ROOT = os.getenv("ROOT_FOLDER", "library")


class Parser:
    def __init__(self, google_drive: Drive, document_id: str, nav_dict):
        self.document_id = document_id
        self.nav_dict = nav_dict
        raw_html = google_drive.get_html(document_id)
        self.html = BeautifulSoup(raw_html, features="html.parser")
        self.html = self.clean_html(self.html)
        self.html = self.parse_links(self.html)
        self.parse_metadata()

    def clean_html(self, soup):
        for tag in soup.findAll(True):
            if len(tag.contents) == 0:
                tag.decompose()
            else:
                del tag["style"]
                del tag["id"]
        return soup

    def parse_metadata(self):
        table = self.html.select_one("table")
        if table:
            table.decompose()

    def parse_links(self, soup):
        external_path = "https://www.google.com/url?q="
        google_doc_path = "docs.google.com/document/d/"
        for a in soup.findAll("a", href=True):
            if a["href"].startswith(external_path):
                a["href"] = a["href"].replace(external_path, "")
            if google_doc_path in a["href"]:
                split_url = a["href"].split(google_doc_path)[1]
                doc_id = split_url.split("/")[0]
                if self.nav_dict.get(doc_id):
                    a["href"] = self.nav_dict.get(doc_id)["full_path"].split(
                        f"/{ROOT}"
                    )[1]

        return soup
