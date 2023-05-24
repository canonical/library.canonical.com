import json
import os
from bs4 import BeautifulSoup

from webapp.googledrive import Drive

f = open("webapp/config/bs4_ignores.json")
bs4_ignores = json.load(f)
ROOT = os.getenv("ROOT_FOLDER", "library")


class Parser:
    def __init__(self, google_drive: Drive, doc_id: str, nav_dict, doc_name):
        self.doc_id = doc_id
        self.nav_dict = nav_dict
        raw_html = google_drive.get_html(doc_id)
        self.html = BeautifulSoup(raw_html, features="html.parser")
        self.html = self.clean_html(self.html, doc_name)
        self.html = self.parse_links(self.html)
        self.parse_metadata()

    def clean_html(self, soup, doc_name):
        soup.select_one("head").decompose()
        soup.select_one("body").unwrap()
        for tag in soup.findAll(True):
            if tag.has_attr("style"):
                tag_style = tag["style"]
                for style, tag_name in bs4_ignores["styles"].items():
                    if style in tag_style and not tag.find("a"):
                        tag.wrap(soup.new_tag(tag_name))
                del tag["style"]
            del tag["id"]
            if tag.name not in bs4_ignores["tags"] and len(tag.contents) == 0:
                tag.decompose()
        h1 = soup.select_one("h1")
        if not h1:
            inserted_h1 = soup.new_tag("h1")
            inserted_h1.string = doc_name
            soup.select_one("html").insert_before(inserted_h1)
        return soup

    def parse_metadata(self):
        table = self.html.select_one("table")
        if table:
            table.decompose()

    def parse_links(self, soup):
        external_path = "https://www.google.com/url?q="
        google_doc_path = "docs.google.com/document/d/"
        url_garbage = "&sa=D"
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
            if url_garbage in a["href"]:
                a["href"] = a["href"].split(url_garbage)[0]

        return soup
