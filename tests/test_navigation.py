import unittest
from unittest.mock import patch


from webapp.navigation import Navigation

from tests.mocks.functions.googledrivemock import GoogleDriveMock



class TestNavigation(unittest.TestCase):
    def setUp(self):
        """
        Run test HTML through the parser.
        """
        # Setup mock parameters
        self.mock_drive = GoogleDriveMock()
        self.mock_root_name = "library"
        self.MockNavigation = Navigation(self.mock_drive, self.mock_root_name)
        self.mock_hierarchy = self.MockNavigation.hierarchy
        self.mock_reference_dict = self.MockNavigation.doc_reference_dict

    def test_slug_represents_name(self):
        not_a_slug = False
        for doc_name in self.mock_reference_dict:
            doc = self.mock_reference_dict[doc_name]
            if doc["slug"] != "-".join(doc["name"].split(" ")).lower():
                not_a_slug = True
        
        self.assertFalse(
            not_a_slug, 
            "Document slugs should replaces spaces with dashes and be lowercase"
        )

    def test_non_root_items_arent_included(self):
        mock_non_root_items = [
            "_____unwanted_file_id", 
            "___unwanted_folder_id", 
            "nested_unwanted_folder_id", 
            "nested_unwanted_file_id",
        ]
        non_root_item_present = False
        for item in mock_non_root_items:
            if self.mock_reference_dict.get(item):
                non_root_item_present = True

        self.assertFalse(
            non_root_item_present, 
            "Items that aren't in the root folder should not be included."
        )
    
    def test_children_items_are_attached(self):
        
