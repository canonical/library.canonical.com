import unittest


from webapp.navigation import Navigation

from tests.mocks.functions.googledrivemock import GoogleDriveMock


class TestNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        """
        Run test HTML through the parser.
        """
        # Setup mock parameters
        self.mock_drive = GoogleDriveMock()
        self.mock_file_list = self.mock_drive.mock_file_list
        self.mock_root_name = "library"
        self.MockNavigation = Navigation(self.mock_drive, self.mock_root_name)
        self.mock_hierarchy = self.MockNavigation.hierarchy
        self.mock_reference_dict = self.MockNavigation.doc_reference_dict

    def test_slug_represents_name(self):
        """
        Check that space separated names are made into dash separated names
        to be used as slugs
        """
        not_a_slug = False
        for doc_name in self.mock_reference_dict:
            doc = self.mock_reference_dict[doc_name]
            if doc["slug"] != "-".join(doc["name"].split(" ")).lower():
                not_a_slug = True

        self.assertFalse(
            not_a_slug,
            "Document slugs should replaces spaces with dashes and be lowercase",
        )

    def test_non_root_items_arent_included(self):
        """
        Test that items that are not under the root folder are not in the
        reference dict and therefor the hierarchy
        """
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
            "Items that aren't in the root folder should not be included.",
        )

    def test_the_top_level_items_are_children_of_root(self):
        """
        Look at the top level items in the hierarchy and check they are all children
        of the root folder
        """
        mock_root_folder_id = "the_library_folder_id"
        valid_parents = True
        for key in self.mock_hierarchy:
            if self.mock_hierarchy[key]["parents"][0] != mock_root_folder_id:
                valid_parents = False

        self.assertTrue(
            valid_parents,
            "Top level items should all have the root folder as a parent",
        )

    def test_children_items_have_correspondin_parents(self):
        """
        Test that the 'children' of a given folder, have the coresponding 'parents'
        for the folder they are in
        """
        def check_parents(hierarchy):
            for key, value in hierarchy.items():
                if "children" in value and value["children"]:
                    for child_key, child_value in value["children"].items():
                        if (
                            "parents" in child_value
                            and child_value["parents"][0]
                            != hierarchy[key]["id"]
                        ):
                            return False
                    if not check_parents(value["children"]):
                        return False
            return True

        children_match_parents = check_parents(self.mock_hierarchy)

        self.assertTrue(
            children_match_parents,
            "The children of a given item in the hierarchy should have a value"
            "of 'parent', that corresponds to the given item.",
        )

    def test_top_level_items_are_ordered(self):
        """
        Check top level items are ordered based on the leading number and dash
        ("-1") and that it is removed.
        """
        # Create an ordered array of the top level items based on leading
        # numeric values use the mock_file_list data
        filtered_items = [
            item
            for item in self.mock_file_list
            if item["name"].split("-")[0].isdigit()
        ]
        filtered_items.sort(key=lambda item: int(item["name"].split("-")[0]))
        sorted_ids = [item["id"] for item in filtered_items]

        # Make an array of the top level items that have been processed by
        # the Navigation class, removing the first item (which is always
        # 'index')
        hierarchy_ids = [item["id"] for item in list(self.mock_hierarchy.values())[1:]]

        self.assertListEqual(sorted_ids, hierarchy_ids)
