import json
import unittest
from unittest.mock import patch


from webapp.parser import Parser
from tests.mocks.functions.get_html_mock import get_html_mock


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
        self.mock_drive = True
        self.mock_doc_id = "12345"
        self.mock_doc_dict = {
            "12345": {"full_path": "/full/mock/path", "name": "Mock document"}
        }
        self.mock_doc_name = "Mock document"
        # Monkey-patch the Parser class to use the custom 
        # function get_static_html instead of the original 
        # get_html method
        with patch.object(Parser, "get_html", get_html_mock):
            self.parser = Parser(
                self.mock_drive,
                self.mock_doc_id,
                self.mock_doc_dict,
                self.mock_doc_name,
            )
            self.soup = self.parser.html

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

if __name__ == "__main__":
    unittest.main()
