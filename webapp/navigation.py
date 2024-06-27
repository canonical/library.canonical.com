import copy
import re


from webapp.googledrive import Drive
from webapp.utils.process_leading_number import extract_leading_number, remove_leading_number


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
        Recursively adds 'full_path' (document URL) and 'breadcrumbs' (list of hierarchical links) to each document in the hierarchy.
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
        # Create a 'doc_reference_dict' of all documents without nesting,
        # so they can be referenced by their key.
        for doc in doc_objects:
            # If a document has no parent (shortcut) then we attach it
            # to the root folder
            if "parents" not in doc:
                doc["parents"] = None

            doc["children"] = {}
            doc["mimeType"] = doc["mimeType"].rpartition(".")[-1]
            # position must be extracted before slug is assigned, as 'name' is edited
            doc["position"] = extract_leading_number(doc["name"])
            doc["name"] = remove_leading_number(doc["name"])
            doc["slug"] = "-".join(doc["name"].split(" ")).lower()
            doc["active"] = False
            doc["expanded"] = False
            
            # If the parent folders id is a drive id (less than 20 chars)
            # and it is not the target folder (root_folder), don't add
            # it to the reference dict/navigation
            if doc["parents"] and (
                len(doc["parents"][0]) > 20
                or doc["name"].lower() == self.root_folder
            ):
                self.doc_reference_dict[doc["id"]] = doc

        # For each doc's parent, find the associated doc and attach it as
        # a child within the 'temp_hierarchy'. If the parent doesn't exist
        # and the slug is the 'root', attach it as the root of the dict.
        # If it meet niether criteria, remove it form  'doc_reference_dict'
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
        When appending a child to a parent, it checks for leadings numbers and positions it accordingly
        """
        slug = doc["slug"]
        position = doc["position"]
        
        # if no 'position' is given, append to the end
        if position is None:
            parent_obj["children"][slug] = doc
            return

        children = parent_obj["children"]
        children[slug] = doc
        ordered_slugs = sorted(children.keys(), key=lambda s: (children[s]["position"] if children[s]["position"] is not None else float('inf')))

        # so this is working but I don't know why
        new_children = {k: children[k] for k in ordered_slugs}
        parent_obj["children"] = new_children
