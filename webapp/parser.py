import os
import json
from urllib.parse import unquote
from bs4 import BeautifulSoup, NavigableString

from webapp.googledrive import GoogleDrive

from webapp.utils.entity_to_char import entity_to_char

ROOT = os.getenv("ROOT_FOLDER", "library")


class Parser:
    def __init__(
        self, google_drive: GoogleDrive, doc_id: str, doc_dict, doc_name: str
    ):
        self.doc_id = doc_id
        self.doc_dict = doc_dict
        self.html = self.get_html(google_drive)
        self.process_html(doc_name)

    def get_html(self, google_drive: GoogleDrive):
        raw_html = google_drive.fetch_document(self.doc_id)
        return BeautifulSoup(raw_html, features="lxml")

    def process_html(self, doc_name):
        with open("webapp/config/bs4_ignores.json") as f:
            bs4_ignores = json.load(f)

        self.parse_metadata()
        self.parse_nested_lists()
        self.parse_nested_bullet_lists()
        self.parse_links()
        self.parse_tags(bs4_ignores)
        self.wrap_code_blocks(bs4_ignores["code_block"])
        self.remove_head()
        self.insert_h1_if_missing(doc_name)
        self.insert_chip_under_title()
        self.generate_headings_map()
        self.parse_create_doc_button()

    def parse_nested_lists(self):
        ol_elements = self.html.find_all(
            "ol", class_=lambda x: x and x.startswith("lst-kix")
        )
        previous_ols = {}

        for ol in ol_elements:
            # get the level of nesting from the class name
            numeric_suffix = ol["class"][0][len("lst-kix") :][-1]  # noqa: E203
            # check if it is the start of a new list
            if "start" in ol["class"]:
                # if its top level add the counter class
                if numeric_suffix == "0":
                    ol["class"] = ol.get("class", []) + [
                        "p-list--nested-counter"
                    ]
                # check if there's already a list with a lower level of nesting
                if (
                    numeric_suffix
                    and str(int(numeric_suffix) - 1) in previous_ols
                ):
                    target_location = previous_ols[
                        str(int(numeric_suffix) - 1)
                    ]
                    if target_location.name == "li":
                        target_location.append(ol)
                    elif target_location.name == "ol":
                        target_location.find_all("li")[-1].append(ol)
                # add the current list to the previous_ols dict
                previous_ols[numeric_suffix] = ol
            # if it's not the start of a new list extract the indervidual li's
            else:
                target_location = previous_ols[str(int(numeric_suffix))]
                li_eles = ol.find_all("li")
                for li in li_eles:
                    if target_location.name == "li":
                        target_location.append(li)
                    elif target_location.name == "ol":
                        target_location.append(li)
                previous_ols[numeric_suffix] = li_eles[-1]

    def parse_nested_bullet_lists(self):
        ul_elements = self.html.find_all(
            "ul", class_=lambda x: x and x.startswith("lst-kix")
        )
        previous_uls = {}

        for ul in ul_elements:
            # Check if the item is the start of a new list and add the start  to class
            alphabetic_suffix = ul["class"][0]
            if alphabetic_suffix in previous_uls:
                # Find the previous mention of that list
                previous_list = previous_uls[alphabetic_suffix]
                if previous_list is not None:
                    # Check the previous list to see if it has a sibling
                    next_siblings = previous_list.findNextSiblings()
                    if len(next_siblings) != 0:
                        next = previous_list.next_sibling()
                        if len(next) != 0 and next[0].name != "li":
                            # if the previous list has a sibling that is not a list add start to mark it as a new list
                            ul["class"].append("start")

            # get the level of nesting from the class name
            numeric_suffix = ul["class"][0][len("lst-kix") :][-1]  # noqa: E203
            # check if it is the start of a new list
            if "start" in ul["class"]:
                if (
                    numeric_suffix
                    and str(int(numeric_suffix) - 1) in previous_uls
                ):
                    target_location = previous_uls[
                        str(int(numeric_suffix) - 1)
                    ]
                    if target_location.name == "li":
                        target_location.append(ul)
                    elif target_location.name == "ul":
                        target_location.find_all("li")[-1].append(ul)
                # add the current list to the previous_ols dict
                previous_uls[numeric_suffix] = ul
                previous_uls[alphabetic_suffix] = ul
            # if it's not the start of a new list extract the indervidual li's
            else:
                target_location = previous_uls[str(int(numeric_suffix))]
                li_eles = ul.find_all("li")
                for li in li_eles:
                    if target_location.name == "li":
                        target_location.append(li)
                    elif target_location.name == "ul":
                        target_location.append(li)
                previous_uls[numeric_suffix] = li_eles[-1]

    def remove_head(self):
        head = self.html.select_one("head")
        if head:
            head.decompose()

    def parse_tags(self, bs4_ignores):
        for tag in self.html.findAll(True):
            self.convert_styles_to_tags(tag, bs4_ignores["styles"])
            self.remove_ids_from_tags(tag)
            self.unwrap_spans(tag)
            self.remove_empty_tags(tag, bs4_ignores["tags"])

    def convert_styles_to_tags(self, tag, ignored_styles):
        if tag.has_attr("style"):
            tag_style = tag["style"].replace(" ", "")
            for style, tag_name in ignored_styles.items():
                if style in tag_style and not tag.find("a"):
                    tag.wrap(self.html.new_tag(tag_name))
            del tag["style"]

    def wrap_inline_text(self, tag):
        while "```code" in tag.contents[-1]:
            text = tag.contents[-1].text
            pos_start = text.find("```code")
            pos_end = text.find("```endcode")
            pre_code = text[0:pos_start]
            code = text[pos_start + 7 : pos_end]
            new_tag = self.html.new_tag("code")
            new_tag.string = code
            post_code = text[pos_end + 10 :]
            tag.contents[-1].replace_with(pre_code)
            tag.append(new_tag)
            tag.append(post_code)

    def wrap_code_blocks(self, code_block_config):
        start_symbol = entity_to_char(code_block_config["start"])
        end_symbol = entity_to_char(code_block_config["end"])

        current_code_block = None
        # Identify code blocks by the start and end symbols
        code_tags = self.html.findAll("code")
        for tag in code_tags:
            if tag.text == "```code":
                tag.string = tag.text.replace("```code", start_symbol)
            if tag.text == "```endcode":
                tag.string = tag.text.replace("```endcode", end_symbol)

        for tag in code_tags:
            # Sometimes there will be a line break in the middle of a code
            # block, so we need to unwrap it
            if tag.find("br"):
                tag.unwrap()
            elif start_symbol in tag.text:
                current_code_block = self.html.new_tag(
                    "div", **{"class": "p-code-snippet"}
                )
                tag.string = tag.text.replace(start_symbol, "")
                parent_tag = tag.parent
                if parent_tag.name != "pre":
                    parent_tag.name = "pre"
                    # Append the pre tag to the code block and put the code
                    # block where the original tag was
                    parent_tag.insert_before(current_code_block)
                    current_code_block.append(parent_tag)
            elif end_symbol in tag.text and current_code_block:
                tag.decompose()
                # Unwrap the nested code tags
                for tag in current_code_block.findAll("code"):
                    tag.unwrap()
                # Re-wrap in a code tag within the pre tag
                pre_tag = current_code_block.find("pre")
                pre_tag.name = "code"
                pre_tag.wrap(self.html.new_tag("pre"))
                # End the current code block and reset
                current_code_block = None
            elif current_code_block:
                # If there is no start or end symbol, we are in the middle of
                # a code block
                parent_tag = tag.parent
                if parent_tag.name != "pre":
                    pre_tag = current_code_block.find("pre")
                    pre_tag.append(self.html.new_tag("br"))
                    # Get all the tags in the new group and append them to the
                    # pre tag on a new line
                    for tag in parent_tag.find_all("code"):
                        pre_tag.append(tag)
        # Clean up any unicode items that are left in the code blocks
        for tag in self.html.select("code:contains(\uec03)"):
            tag.contents[0].replace_with(tag.contents[0].replace("\uec03", ""))
            tag.contents[2].replace_with("")
        # Clean up empty p tags and clean unicode items in p tags
        for tag in self.html.findAll("p"):
            if not tag.contents:
                tag.decompose()
            elif "```code" in tag.text:
                self.wrap_inline_text(tag)
            elif "\uec02" in tag.text:
                tag.string = tag.text.replace("\uec02", "")

    def remove_ids_from_tags(self, tag):
        if tag.has_attr("id"):
            del tag["id"]

    def remove_empty_tags(self, tag, ignored_tags):
        if tag.name not in ignored_tags and self.tag_is_empty(tag):
            tag.extract()

    def unwrap_spans(self, tag):
        if tag.name == "span" and not tag.has_attr("style"):
            tag.unwrap()

    def insert_h1_if_missing(self, doc_name):
        h1 = self.html.select_one("h1")
        if not h1 and doc_name.lower() != "index" and self.html.body:
            inserted_h1 = self.html.new_tag("h1")
            inserted_h1.string = doc_name
            self.html.body.insert(0, inserted_h1)

    def parse_metadata(self):
        table = self.html.select_one("table")
        self.metadata = dict()
        first_row = []
        third_row = []
        if table:
            rows = table.find_all("tr")
            for ind in range(len(rows)):
                row = rows[ind]
                columns = row.find_all("td")
                if len(columns) > 2:
                    if ind == 0:
                        for col in columns:
                            key = (
                                col.get_text(strip=True)
                                .replace(" ", "_")
                                .lower()
                            )
                            first_row.append(key)
                    elif ind == 1:
                        for icol in range(len(columns)):
                            col = columns[icol]
                            value = col.get_text(strip=True)
                            if first_row[icol] == "author(s)":
                                if "," in value:
                                    value = value.split(",")
                                else:
                                    value = [value]
                            self.metadata[first_row[icol]] = value
                    elif ind == 2:
                        for col in columns:
                            key = (
                                col.get_text(strip=True)
                                .replace(" ", "_")
                                .lower()
                            )
                            third_row.append(key)
                            if key == "reviewer(s)":
                                self.metadata[key] = []
                    elif ind >= 3:
                        current_row = []
                        for icol in range(len(columns)):
                            col = columns[icol]
                            value = col.get_text(strip=True)
                            current_row.append(value)
                        reviewer_dict = {}
                        for i in range(len(third_row)):
                            if third_row[i] == "reviewer(s)":
                                reviewer_dict["name"] = current_row[i]
                            else:
                                reviewer_dict[third_row[i]] = current_row[i]
                        self.metadata["reviewer(s)"].append(reviewer_dict)
                else:
                    key = (
                        columns[0]
                        .get_text(strip=True)
                        .replace(" ", "_")
                        .lower()
                    )
                    value = columns[1].get_text(strip=True)
                    self.metadata[key] = value

            table.decompose()

            return self.metadata

    def parse_create_doc_button(self):
        button_sets = self.html.findAll(
            lambda tag: tag
            and tag.string
            and "create-doc-button" in tag.string
        )
        if len(button_sets) > 0:
            for create_doc_button in button_sets:
                link_tag = self.html.new_tag("a", href="/create-copy-template")
                new_tag = self.html.new_tag(
                    "button", **{"class": "p-button--positive"}
                )
                new_tag.string = "Create Document"
                link_tag.append(new_tag)
                create_doc_button.replace_with(link_tag)

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
            a_tag["href"] = unquote(a_tag["href"])

    def clean_external_links(self, a_tag, external_path):
        if a_tag["href"].startswith(external_path):
            a_tag["href"] = a_tag["href"].replace(external_path, "")

    def process_google_doc_links(self, a_tag, google_doc_paths):
        for google_doc_path in google_doc_paths:
            if google_doc_path in a_tag["href"]:
                split_url = a_tag["href"].split(google_doc_path)[1]
                doc_id = split_url.split("/")[0]
                if self.doc_dict.get(doc_id):
                    full_path = self.doc_dict.get(doc_id)["full_path"]
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

    def insert_chip_under_title(self):
        title = self.html.select_one("h1")
        if self.html.body:
            if title is None and self.html.bady:
                self.insert_h1_if_missing("")
                title = self.html.select_one("h1")
            if not self.metadata.get("type") is None:
                type = self.metadata["type"]
                if not type == "":
                    if type == "how-to":
                        tag = self.html.new_tag(
                            "div",
                            attrs={"class": "p-chip--information u-no-margin"},
                        )
                        tag.string = type
                    elif type == "Explanation":
                        tag = self.html.new_tag(
                            "a", href="https://diataxis.fr/explanation/"
                        )
                        tag["style"] = "color:inherit"
                        inner_tag = self.html.new_tag(
                            "div",
                            attrs={"class": "p-chip--caution u-no-margin"},
                        )
                        inner_tag.string = type
                        tag.append(inner_tag)
                    else:
                        tag = self.html.new_tag(
                            "div", attrs={"class": "p-chip u-no-margin"}
                        )
                        tag.string = type
                    title.insert_after(tag)

    def generate_headings_map(self):
        self.headings_map = []
        id_suffix = 1

        headings = self.html.find_all(["h2", "h3"])

        for tag in headings:
            id_val = (
                tag.text.lower()
                .replace(" ", "-")
                .replace("(", "")
                .replace(")", "")
                + "-"
                + str(id_suffix)
            )
            tag["id"] = id_val
            self.headings_map.append(
                {
                    "id": id_val,
                    "name": tag.text,
                    "level": int(tag.name[1]),
                }
            )
            id_suffix = id_suffix + 1

        return self.headings_map
