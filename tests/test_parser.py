import json
import unittest

from webapp.parser import Parser
from tests.mocks.functions.googledrivemock import GoogleDriveMock

from webapp.helper.entity_to_char import entity_to_char


class TestParser(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        with open("webapp/config/bs4_ignores.json") as f:
            self.bs4_ignores = json.load(f)

    def setUp(self):
        """
        Run test HTML through the parser.
        """
        # Setup mock parameters
        self.mock_drive = GoogleDriveMock()
        self.mock_doc_id = "12345"
        self.mock_doc_dict = {
            "12345": {"full_path": "/full/mock/path", "name": "Mock document"}
        }
        self.mock_doc_name = "Mock document"

        self.parser = Parser(
            self.mock_drive,
            self.mock_doc_id,
            self.mock_doc_dict,
            self.mock_doc_name,
        )
        self.soup = self.parser.html

        self.entity_to_char = entity_to_char

    def test_insert_h1_if_missing_with_h1_present(self):
        """
        Create an 'h1' tag and check that it is not replaced
        """
        h1_tag = self.soup.new_tag("h1")
        h1_tag.string = "Existing heading"
        self.soup.body.insert(0, h1_tag)

        self.parser.insert_h1_if_missing("New heading")

        self.assertEqual(
            h1_tag.string,
            "Existing heading",
            "Existing 'h1' tag should not be modified.",
        )

    def test_insert_h1_if_missing_without_h1(self):
        """
        Check if an 'h1' tag is inserted when it's missing
        based on the mock_doc_dict parsed into the Parser
        """
        h1_tag = self.soup.select_one("h1")
        self.assertIsNotNone(h1_tag, "'h1' tag should be inserted.")
        self.assertEqual(
            h1_tag.string,
            "Mock document",
            "Inserted 'h1' tag has incorrect content.",
        )

    def test_images_are_parsed(self):
        """
        Check if image is present in soup and src is
        not empty
        """
        is_valid = False
        img_tag = self.soup.find("img")
        if img_tag and img_tag.get("src"):
            is_valid = True

        self.assertTrue(is_valid, "Images should exist and have and src value")

    def test_head_tag_removed(self):
        """
        Check if the 'head' tag is removed from the soup
        """
        head_tag = self.soup.find("head")
        self.assertIsNone(head_tag, "The 'head' tag should be removed.")

    def test_parse_links_clean_external_links(self):
        """
        Check that external links are cleaned correctly
        """
        a_tag = self.soup.new_tag(
            "a", href="https://www.google.com/url?q=http://example.com"
        )
        self.soup.body.append(a_tag)
        self.parser.parse_links()

        self.assertEqual(
            a_tag["href"],
            "http://example.com",
            "External link should be cleaned.",
        )

    def test_docs_links_link_internally(self):
        """
        Check that docs links link internally
        """
        a_tag = self.soup.new_tag(
            "a", href="docs.google.com/document/u/0/d/example12345/edit"
        )
        self.soup.body.append(a_tag)

        # Monkey patch doc_dict
        self.parser.doc_dict = {
            "example12345": {"full_path": "/example/full/path"}
        }

        google_doc_paths = [
            "docs.google.com/document/d/",
            "docs.google.com/document/u/0/d/",
        ]
        self.parser.process_google_doc_links(a_tag, google_doc_paths)

        self.assertEqual(
            a_tag["href"],
            "/example/full/path",
            "Docs links should be converted to internal links.",
        )

    def test_trailing_garbage_is_removed(self):
        """
        Check that trailing garbage is removed
        """
        a_tag = self.soup.new_tag(
            "a", href="http://example.com/&sa=D&source=editors&ust=GARBAGE"
        )
        self.soup.body.append(a_tag)
        self.parser.parse_links()

        self.assertEqual(
            a_tag["href"],
            "http://example.com/",
            "Trailing garbage should be removed.",
        )

    def test_generate_headings_map(self):
        """
        Check that a heading map is created with all h2
        and h3 headings
        """
        h2_tag = self.soup.new_tag("h2")
        h2_tag.string = "Heading"
        self.soup.body.append(h2_tag)

        h3_tag = self.soup.new_tag("h3")
        h3_tag.string = "Subheading"
        self.soup.body.append(h3_tag)

        self.parser.generate_headings_map()

        expected_map = [
            {"id": "heading-1", "name": "Heading", "level": 2},
            {"id": "subheading-2", "name": "Subheading", "level": 3},
        ]

        self.assertEqual(
            self.parser.headings_map,
            expected_map,
            "Headings map is not generated correctly.",
        )

    def test_parse_metadata_without_table(self):
        """
        Check if metadata parsing works correctly when there
        is no 'table' tag
        """
        metadata = self.parser.metadata

        self.assertEqual(
            metadata,
            {},
            "Metadata should be an empty dictionary when there is no 'table'.",
        )

    def test_parse_metadata_with_table(self):
        """
        Create a 'table' tag with some metadata and check if
        the metadata is parsed correctly
        """
        table_tag = self.soup.new_tag("table")
        row1 = self.soup.new_tag("tr")
        row1_key = self.soup.new_tag("td")
        row1_key.string = "Author"
        row1_value = self.soup.new_tag("td")
        row1_value.string = "John Doe"
        row1.append(row1_key)
        row1.append(row1_value)
        table_tag.append(row1)

        self.soup.body.append(table_tag)

        metadata = self.parser.parse_metadata()

        expected_metadata = {"author": "John Doe"}
        self.assertEqual(
            metadata, expected_metadata, "Metadata is not parsed correctly."
        )

    def test_non_empty_tag(self):
        """
        Check if tag_is_empty returns False for a non-empty tag
        """
        tag = self.soup.new_tag("p")
        tag.string = "Some text"

        self.assertFalse(
            self.parser.tag_is_empty(tag),
            "tag_is_empty should return False for non-empty tag.",
        )

    def test_empty_tags(self):
        """
        Check if tag_is_empty returns True for an empty tag
        """
        tag = self.soup.new_tag("p")

        self.assertTrue(
            self.parser.tag_is_empty(tag),
            "tag_is_empty should return True for an empty tag.",
        )

    def test_nested_empty_tags(self):
        """
        Check if tag_is_empty returns True for a tag with empty
        child tags
        """
        parent_tag = self.soup.new_tag("ul")
        child_tag1 = self.soup.new_tag("li")
        child_tag2 = self.soup.new_tag("li")
        parent_tag.append(child_tag1)
        parent_tag.append(child_tag2)

        self.assertTrue(
            self.parser.tag_is_empty(parent_tag),
            "tag_is_empty should return True for a tag with empty child tags.",
        )

    def test_mixed_empty_and_non_empty_tags(self):
        """
        Check if tag_is_empty correctly handles a tag with mixed
        content (text and child tags)
        """
        tag = self.soup.new_tag("div")
        tag.string = "Some text"
        child_tag = self.soup.new_tag("p")
        tag.append(child_tag)

        self.assertFalse(
            self.parser.tag_is_empty(tag),
            "tag_is_empty should return False for a tag with mixed content.",
        )

    def test_remove_empty_tags(self):
        """
        Check if empty tags are removed correctly
        """
        empty_tags = ["div", "span"]
        for empty_tag in empty_tags:
            tag = self.soup.new_tag(empty_tag)
            self.soup.body.insert(1, tag)

        self.parser.parse_tags(self.bs4_ignores)

        for empty_tag in empty_tags:
            removed_tag = self.soup.select_one(empty_tag)
            self.assertEqual(
                removed_tag, None, f"{empty_tag} tag should be removed."
            )

    def test_remove_empty_tags_with_non_empty_tags(self):
        """
        Check if non-empty tags are not removed
        """
        tag = self.soup.new_tag("p")
        tag.string = "Non-empty paragraph"
        self.soup.body.append(tag)

        self.parser.parse_tags(self.bs4_ignores)

        p_tag = self.soup.select_one("p")

        self.assertNotEqual(
            p_tag, None, "Non-empty tag should not be removed."
        )

    def test_underline_style_is_converted_to_tag(self):
        """
        Check underline style is converted to a wrapper tag
        """
        tag = self.soup.new_tag("p", style="text-decoration: underline;")
        self.soup.body.insert(1, tag)
        self.parser.convert_styles_to_tags(tag, self.bs4_ignores["styles"])

        converted_tag = self.soup.select_one("p")
        has_style = hasattr(converted_tag, "style")
        parent_tag = converted_tag.parent

        self.assertTrue(has_style, "Style should be removed")
        self.assertEqual(
            parent_tag.name,
            "u",
            "Style should be converted to a wrapping tag.",
        )

    def test_bold_style_is_converted_to_tag(self):
        """
        Check bold style is converted to a wrapper tag
        """
        tag = self.soup.new_tag("p", style="font-weight: 700;")
        self.soup.body.insert(1, tag)

        self.parser.convert_styles_to_tags(tag, self.bs4_ignores["styles"])

        converted_tag = self.soup.select_one("p")
        has_style = hasattr(converted_tag, "style")
        parent_tag = converted_tag.parent

        self.assertTrue(has_style, "Style should be removed")
        self.assertEqual(
            parent_tag.name,
            "strong",
            "Style should be converted to a wrapping tag.",
        )

    def test_italic_style_is_converted_to_tag(self):
        """
        Check italic style is converted to a wrapper tag
        """
        tag = self.soup.new_tag("p", style="font-style: italic;")
        self.soup.body.insert(1, tag)
        self.parser.convert_styles_to_tags(tag, self.bs4_ignores["styles"])

        converted_tag = self.soup.select_one("p")
        has_style = hasattr(converted_tag, "style")
        parent_tag = converted_tag.parent
        self.assertTrue(has_style, "Style should be removed")
        self.assertEqual(
            parent_tag.name,
            "em",
            "Style should be converted to a wrapping tag.",
        )

    def test_spans_are_unwrapped(self):
        """
        Check that an element will have wrapping spans removed
        """
        parent_tag = self.soup.new_tag("span")
        child_tag = self.soup.new_tag("p")
        parent_tag.insert(1, child_tag)

        self.parser.parse_tags(self.bs4_ignores)

        parent_tag = child_tag.parent

        self.assertEqual(
            parent_tag.name,
            "span",
            "Element should not be wrapped in a span element",
        )

    def test_entity_to_char_conversion(self):
        """
        Check that HTML entities are converted to characters
        """
        start_char = self.entity_to_char(
            self.bs4_ignores["code_block"]["start"]
        )
        end_char = self.entity_to_char(self.bs4_ignores["code_block"]["end"])

        self.assertEqual(
            start_char,
            "",
            "Start entity code should be converted to character",
        )
        self.assertEqual(
            end_char, "", "End entity code should be converted to character"
        )

    def test_code_block_handling(self):
        """
        Check that code blocks are handled correctly
        """
        # First paragraph
        p1 = self.soup.new_tag("p")
        code1 = self.soup.new_tag("code")
        code1.string = ""
        code2 = self.soup.new_tag("code")
        code2.string = "test"
        code3 = self.soup.new_tag("code")
        code3.string = "&nbsp;"
        code4 = self.soup.new_tag("code")
        code4.string = "line1"
        p1.extend([code1, code2, code3, code4])

        # Second paragraph
        p2 = self.soup.new_tag("p")
        code5 = self.soup.new_tag("code")
        code5.string = "test"
        code6 = self.soup.new_tag("code")
        code6.string = "&nbsp;"
        code7 = self.soup.new_tag("code")
        code7.string = "line2"
        p2.extend([code5, code6, code7])

        # Third paragraph
        p3 = self.soup.new_tag("p")
        code8 = self.soup.new_tag("code")
        code8.string = ""
        p3.append(code8)

        # Append all paragraphs
        self.soup.extend([p1, p2, p3])

        self.parser.wrap_code_blocks(self.bs4_ignores["code_block"])

        code_block = self.soup.find("div", {"class": "p-code-snippet"})
        code_block_child = code_block.find(recursive=False)
        code_block_child_child = code_block_child.find(recursive=False)

        self.assertIsNotNone(
            code_block,
            "Code block should be wrapped in a div with"
            " the class name 'p-code-snippet'",
        )
        self.assertEqual(
            code_block_child.name,
            "pre",
            "Code block should be wrapped in a pre tag,"
            " as a direct child of the div with class name 'p-code-snippet'",
        )
        self.assertEqual(
            code_block_child_child.name,
            "code",
            "Code block should be wrapped in a code tag,"
            " as a direct child of the pre tag",
        )


if __name__ == "__main__":
    unittest.main()
