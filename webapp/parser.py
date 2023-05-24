import os
import json
from bs4 import BeautifulSoup, NavigableString

from webapp.googledrive import Drive

ROOT = os.getenv("ROOT_FOLDER", "library")


class Parser:
    def __init__(
        self, google_drive: Drive, doc_id: str, nav_dict, doc_name: str
    ):
        self.doc_id = doc_id
        self.nav_dict = nav_dict
        self.html = self.get_html(google_drive)
        self.process_html(doc_name)

    def get_html(self, google_drive: Drive):
        raw_html = google_drive.fetch_document(self.doc_id)
        return BeautifulSoup(raw_html, features="lxml")

    def process_html(self, doc_name):
        self.parse_metadata()
        self.parse_links()
        self.parse_tags()
        self.remove_head()
        self.insert_h1_if_missing(doc_name)

    def remove_head(self):
        head = self.html.select_one("head")
        if head:
            head.decompose()

    def parse_tags(self):
        with open("webapp/config/bs4_ignores.json") as f:
            bs4_ignores = json.load(f)

        for tag in self.html.findAll(lambda tag: tag.name != "span"):
            self.remove_ids_from_tags(tag)
            self.convert_styles_to_tags(tag, bs4_ignores["styles"])
            self.remove_empty_tags(tag, bs4_ignores["tags"])
            self.unwrap_spans(tag)

    def remove_ids_from_tags(self, tag):
        if tag.has_attr("id"):
            del tag["id"]

    def convert_styles_to_tags(self, tag, ignored_styles):
        if tag.has_attr("style"):
            tag_style = tag["style"]
            for style, tag_name in ignored_styles.items():
                if style in tag_style and not tag.find("a"):
                    tag.wrap(self.html.new_tag(tag_name))
            del tag["style"]

    def remove_empty_tags(self, tag, ignored_tags):
        if tag.name not in ignored_tags and self.tag_is_empty(tag):
            tag.extract()

    def unwrap_spans(self, tag):
        for span in tag.find_all("span"):
            span.unwrap()

    def insert_h1_if_missing(self, doc_name):
        h1 = self.html.select_one("h1")
        if not h1 and doc_name != "index":
            inserted_h1 = self.html.new_tag("h1")
            inserted_h1.string = doc_name
            self.html.body.insert(0, inserted_h1)

    def parse_metadata(self):
        table = self.html.select_one("table")
        if table:
            table.decompose()

    def parse_links(self):
        external_path = "https://www.google.com/url?q="
        google_doc_paths = [
            "docs.google.com/document/d/",
            "docs.google.com/document/u/0/d/",
        ]
        trailing_garbage = "&sa=D&source=editors&ust="
        for a_tag in self.html.findAll("a", href=True):
            self.clean_external_links(a_tag, external_path)
            self.process_google_doc_links(a_tag, google_doc_paths)
            self.remove_trailing_garbage(a_tag, trailing_garbage)

    def clean_external_links(self, a_tag, external_path):
        if a_tag["href"].startswith(external_path):
            a_tag["href"] = a_tag["href"].replace(external_path, "")

    def process_google_doc_links(self, a_tag, google_doc_paths):
        for google_doc_path in google_doc_paths:
            if google_doc_path in a_tag["href"]:
                split_url = a_tag["href"].split(google_doc_path)[1]
                doc_id = split_url.split("/")[0]
                if self.nav_dict.get(doc_id):
                    full_path = self.nav_dict.get(doc_id)["full_path"]
                    a_tag["href"] = full_path

    def remove_trailing_garbage(self, a_tag, trailing_garbage):
        if trailing_garbage in a_tag["href"]:
            a_tag["href"] = a_tag["href"].split(trailing_garbage)[0]

    def tag_is_empty(self, tag):
        if isinstance(tag, NavigableString):
            return tag.strip() == ""
        elif tag is None or tag.get_text(strip=True) == "":
            if not tag.contents:
                return True
            else:
                return all(self.tag_is_empty(child) for child in tag.contents)
        return False
