import copy


from webapp.googledrive import Drive
from webapp.utils.process_leading_number import (
    extract_leading_number,
    remove_leading_number,
)


class Navigation:
    def __init__(self, google_drive: Drive, root_folder: str):
        self.root_folder = root_folder.lower()
        self.doc_reference_dict = {}
        self.temp_hierarchy = {}
        file_list = google_drive.get_document_list()
        doc_objects_copy = copy.deepcopy(file_list)
        self.hierarchy = self.create_hierarchy(doc_objects_copy)

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

    def create_hierarchy(self, doc_objects):
        """
        A function that initialises each document with the appropriate data
        for building the navigation
        """
        # Builds 'doc_reference_dict'.
        # ex. 'docuement_id': {document_object}
        for doc in doc_objects:
            # Attach orphan documents to the root folder.
            if "parents" not in doc:
                doc["parents"] = None

            doc["children"] = {}
            doc["mimeType"] = doc["mimeType"].rpartition(".")[-1]
            # Extract position before assigning slug, since 'name' is edited.
            doc["position"] = extract_leading_number(doc["name"])
            doc["name"] = remove_leading_number(doc["name"])
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
                self.doc_reference_dict[doc["id"]] = doc

        # Build the 'temp_hierarchy' with the 'root_folder' as the root.
        # A tree structure reflecting the Google Drive folder structure.
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
        When appending a child to a parent, it checks for leadings numbers and
        positions it accordingly
        """
        slug = doc["slug"]
        position = doc["position"]

        # Add doc to children
        children = parent_obj["children"]
        children[slug] = doc

        # If no 'position' is given, leave it at the end
        if position is None:
            return

        # Reorder based on 'position' value
        ordered_slugs = sorted(
            children.keys(),
            key=lambda s: (
                children[s]["position"]
                if children[s]["position"] is not None
                else float("inf")
            ),
        )

        new_children = {k: children[k] for k in ordered_slugs}
        parent_obj["children"] = new_children
