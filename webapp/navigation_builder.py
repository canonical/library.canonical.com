import copy

from webapp.googledrive import GoogleDrive
from webapp.utils.process_leading_number import (
    extract_leading_number,
    remove_leading_number,
)


class NavigationBuilder:
    def __init__(
        self,
        google_drive: GoogleDrive,
        root_folder: str,
        cache=False,
        doc_reference_dict=None,
        temp_hierarchy=None,
        file_list=None,
        hierarchy=None,
    ):
        if not cache:
            self.root_folder = root_folder.lower()
            self.doc_reference_dict = {}
            self.temp_hierarchy = {}
            self.file_list = self.get_file_list_copy(google_drive)
            self.initialize_reference_dict()
            self.hierarchy = self.create_hierarchy(self.file_list)
        else:
            self.root_folder = root_folder.lower()
            self.doc_reference_dict = doc_reference_dict
            self.temp_hierarchy = temp_hierarchy
            self.file_list = file_list
            self.hierarchy = hierarchy

    def get_file_list_copy(self, google_drive: GoogleDrive):
        """
        Retrieves and deep copies the document list from Google Drive.
        """
        file_list = google_drive.get_document_list()
        return copy.deepcopy(file_list)

    def initialize_reference_dict(self):
        """
        Initializes the document reference dictionary.
        """
        self.doc_reference_dict = self.create_reference_dict(self.file_list)

    def add_path_context(self, hierarchy_obj, path="", breadcrumbs=None):
        """
        Recursively adds 'full_path' (document URL) and 'breadcrumbs' (list of
        hierarchical links) to each document in the hierarchy.
        """
        if breadcrumbs is None:
            breadcrumbs = []

        for key in hierarchy_obj.keys():
            if (
                hierarchy_obj[key]["slug"] == self.root_folder
                or hierarchy_obj[key]["slug"] == "index"
            ):
                full_path = path
                item_breadcrumbs = breadcrumbs
            else:
                full_path = path + "/" + hierarchy_obj[key]["slug"]
                item_breadcrumbs = breadcrumbs + [
                    {"name": hierarchy_obj[key]["name"], "path": full_path}
                ]

            hierarchy_obj[key]["full_path"] = full_path
            hierarchy_obj[key]["breadcrumbs"] = item_breadcrumbs

            if hierarchy_obj[key]["mimeType"] == "folder":
                self.add_path_context(
                    hierarchy_obj[key]["children"], full_path, item_breadcrumbs
                )

    def create_reference_dict(self, doc_objects):
        """
        A function that builds the reference dictionary for documents and
        initialises each document with the appropriate data.
        ex. {"document_id": {document_data_object}}
        """
        doc_reference_dict = {}
        for doc in doc_objects:
            # Attach orphan documents to the root folder.
            if "parents" not in doc:
                doc["parents"] = None

            doc["children"] = {}
            doc["mimeType"] = doc["mimeType"].rpartition(".")[-1]
            # Extract position information ('01-') and store it,
            # since 'name' is edited.
            doc["position"] = extract_leading_number(doc["name"])
            temp_name = remove_leading_number(doc["name"])
            if temp_name == "Index":
                temp_name = "index"
            doc["isSoftRoot"] = "!" in temp_name
            doc["name"] = temp_name.replace("!", "")
            doc["slug"] = "-".join(doc["name"].split(" ")).lower()
            doc["active"] = False
            doc["expanded"] = False

            # To keep only 'Library' from top level: If the parent folder's ID
            # is a drive ID (<20 chars) and not 'root', skip it in the
            # reference dict/navigation.
            if doc["parents"] and (
                len(doc["parents"][0]) > 20
                or doc["name"].lower() == self.root_folder
            ):
                doc_reference_dict[doc["id"]] = doc

        return doc_reference_dict

    def create_hierarchy(self, doc_objects):
        """
        A function that initialises each document with the appropriate data
        for building the navigation
        """
        # Build the 'temp_hierarchy' with the 'root_folder' as the root.
        # A tree structure reflecting the Google GoogleDrive folder structure.
        for doc in doc_objects:
            if doc["parents"]:
                parent_ids = doc["parents"]
                parent_obj = self.doc_reference_dict.get(parent_ids[0])
                if parent_obj is not None:
                    parent_obj["children"][doc["slug"]] = doc
                    self.insert_based_on_position(parent_obj, doc)
                elif doc["slug"] == self.root_folder:
                    self.temp_hierarchy[doc["slug"]] = doc
                elif doc["id"] in self.doc_reference_dict:
                    self.doc_reference_dict.pop(doc["id"])

        self.add_path_context(self.temp_hierarchy)

        return self.temp_hierarchy[self.root_folder]["children"]

    def insert_based_on_position(self, parent_obj, doc):
        """
        When appending a child to a parent, it checks for leading numbers and
        positions it accordingly. If no 'position' is given, it places the
        item alphabetically after the ones with 'position' values.
        """
        slug = doc["slug"]

        # Add doc to children
        children = parent_obj["children"]
        children[slug] = doc

        # Sort children first by 'position', then alphabetically by 'slug'
        ordered_slugs = sorted(
            children.keys(),
            key=lambda s: (
                (
                    children[s]["position"]
                    if children[s]["position"] is not None
                    else float("inf")
                ),
                s.lower(),  # Sort alphabetically
            ),
        )

        new_children = {k: children[k] for k in ordered_slugs}
        parent_obj["children"] = new_children
