from webapp.googledrive import Drive
import os

ROOT = os.getenv("ROOT_FOLDER", "library")


class Navigation:
    def __init__(self, google_drive: Drive):
        file_list = google_drive.get_document_list()
        self.hierarchy = self.create_hierarchy(file_list)

    def add_path_context(self, hierarchy_obj, path="", breadcrumbs=None):
        if breadcrumbs is None:
            breadcrumbs = []

        for key in hierarchy_obj.keys():
            if (
                hierarchy_obj[key]["slug"] == ROOT
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
        self.doc_reference_dict = {}
        doc_hierarchy = {}

        for doc in doc_objects:
            doc["children"] = {}
            doc["mimeType"] = doc["mimeType"].rpartition(".")[-1]
            doc["slug"] = "-".join(doc["name"].split(" ")).lower()
            doc["active"] = False
            doc["expanded"] = False
            self.doc_reference_dict[doc["id"]] = doc

        for doc in doc_objects:
            parent_ids = doc["parents"]
            for parent_id in parent_ids:
                parent_obj = self.doc_reference_dict.get(parent_id)
                if parent_obj is not None:
                    parent_obj["children"][doc["slug"]] = doc
                else:
                    doc_hierarchy[doc["slug"]] = doc

        self.add_path_context(doc_hierarchy)

        ordered_hierarchy = self.order_hierarchy(
            doc_hierarchy[ROOT]["children"]
        )

        return ordered_hierarchy

    def order_hierarchy(self, hierarchy):
        if "index" in hierarchy:
            index_item = hierarchy.pop("index")
        ordered_items = dict(sorted(hierarchy.items(), key=lambda x: x[0]))
        ordered_hierarchy = {"index": index_item}
        ordered_hierarchy.update(ordered_items)

        return ordered_hierarchy
