from webapp.googledrive import Drive
import os

class Navigation:
    def __init__(self, google_drive: Drive, root_folder: str):
        self.root_folder = root_folder.lower()
        self.doc_reference_dict = {}
        file_list = google_drive.get_document_list()
        self.hierarchy = self.create_hierarchy(file_list)

    def add_path_context(self, hierarchy_obj, path="", breadcrumbs=None):
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
        doc_hierarchy = {}

        for doc in doc_objects:
            doc["children"] = {}
            doc["mimeType"] = doc["mimeType"].rpartition(".")[-1]
            doc["slug"] = "-".join(doc["name"].split(" ")).lower()
            doc["active"] = False
            doc["expanded"] = False
            if (
                len(doc["parents"][0]) > 20
                or doc["name"].lower() == self.root_folder
            ):
                self.doc_reference_dict[doc["id"]] = doc

        for doc in doc_objects:
            parent_ids = doc["parents"]
            parent_obj = self.doc_reference_dict.get(parent_ids[0])
            if parent_obj is not None:
                parent_obj["children"][doc["slug"]] = doc
            else:
                doc_hierarchy[doc["slug"]] = doc

        self.add_path_context(doc_hierarchy)

        ordered_hierarchy = self.order_hierarchy(
            doc_hierarchy[self.root_folder]["children"]
        )
        return ordered_hierarchy

    def order_hierarchy(self, hierarchy):
        if "index" in hierarchy:
            index_item = hierarchy.pop("index")
            ordered_items = dict(sorted(hierarchy.items(), key=lambda x: x[0]))
            ordered_hierarchy = {"index": index_item}
            ordered_hierarchy.update(ordered_items)

            return ordered_hierarchy
