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

if __name__ == "__main__":
    unittest.main()
