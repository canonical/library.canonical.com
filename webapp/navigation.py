import copy

from webapp.googledrive import Drive


class Navigation:
    def __init__(self, google_drive: Drive, root_folder: str):
        self.root_folder = root_folder.lower()
        self.doc_reference_dict = {}
        self.doc_hierarchy = {}
        file_list = google_drive.get_document_list()
        doc_objects_copy = copy.deepcopy(file_list)
        self.hierarchy = self.create_hierarchy(doc_objects_copy)

    def add_path_context(self, hierarchy_obj, path="", breadcrumbs=None):
        """
        A recursive function that adds a 'full_path' value, which indicates
        the url to the document and a 'breadcrumbs' value, which is an array
        of links that represent the nesting of the given document in the
        hierarchy.
        """
        # Check if there is a breadcrumb list, if there is not initialise one
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
        # a child within the 'doc_hierarchy'. If the parent doesn't exist
        # and the slug is the 'root', attach it as the root of the dict.
        # If it meet niether criteria, remove it form  'doc_reference_dict'
        for doc in doc_objects:
            if doc["parents"]:
                parent_ids = doc["parents"]
                parent_obj = self.doc_reference_dict.get(parent_ids[0])
                if parent_obj is not None:
                    parent_obj["children"][doc["slug"]] = doc
                elif doc["slug"] == self.root_folder:
                    self.doc_hierarchy[doc["slug"]] = doc
                elif doc["id"] in self.doc_reference_dict:
                    self.doc_reference_dict.pop(doc["id"])

        ordered_hierarchy = self.order_hierarchy(
            self.doc_hierarchy[self.root_folder]["children"]
        )

        self.add_path_context(self.doc_hierarchy)

        return ordered_hierarchy

    def order_hierarchy(self, hierarchy):
        """
        Orders top level items based on leading numbers separated by
        a dash(-) and then removes the number and dash.
        """

        def remove_pre(text):
            """
            Removes the number and dash(-) from a string
            """
            if "-" in text:
                idx = text.index("-")
                if text[:idx].isdigit():
                    index = idx + 1
                    return text[index:]
            return text

        if "index" in hierarchy:
            index_item = hierarchy.pop("index")
            ordered_items = dict(sorted(hierarchy.items(), key=lambda x: x[0]))
            ordered_hierarchy = {"index": index_item}

            updated_dict = {}
            for key, item in ordered_items.items():
                new_key = remove_pre(key)
                if isinstance(item, dict):
                    if "slug" in item:
                        item["slug"] = remove_pre(item["slug"])
                    if "name" in item:
                        item["name"] = remove_pre(item["name"])
                    if item["id"] in self.doc_reference_dict:
                        ref_item = self.doc_reference_dict.get(item["id"])
                        ref_item["name"] = remove_pre(ref_item["name"])
                updated_dict[new_key] = item

            ordered_hierarchy.update(updated_dict)

            return ordered_hierarchy
