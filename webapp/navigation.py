from webapp.googledrive import Drive
import os

ROOT = os.getenv("ROOT_FOLDER", "library")


class Navigation:
    def __init__(self, google_drive: Drive):
        file_list = google_drive.get_document_list()
        self.hierarchy = self.create_hierarchy(file_list)
        self.object_dict

    def add_path_context(self, obj, path="", breadcrumbs=None):
        if breadcrumbs is None:
            breadcrumbs = []

        for key in obj.keys():
            if obj[key]["slug"] == ROOT or obj[key]["slug"] == "index":
                full_path = path
                item_breadcrumbs = breadcrumbs
            else:
                full_path = path + "/" + obj[key]["slug"]
                item_breadcrumbs = breadcrumbs + [
                    {"name": obj[key]["name"], "path": full_path}
                ]

            obj[key]["full_path"] = full_path
            obj[key]["breadcrumbs"] = item_breadcrumbs

            if obj[key]["mimeType"] == "folder":
                self.add_path_context(
                    obj[key]["children"], full_path, item_breadcrumbs
                )

    def create_hierarchy(self, objects):
        self.object_dict = {}
        root_objects = {}

        for obj in objects:
            obj["children"] = {}
            obj["mimeType"] = obj["mimeType"].rpartition(".")[-1]
            obj["slug"] = "-".join(obj["name"].split(" ")).lower()
            obj["active"] = False
            obj["expanded"] = False
            self.object_dict[obj["id"]] = obj

        for obj in objects:
            parent_ids = obj["parents"]
            for parent_id in parent_ids:
                parent_obj = self.object_dict.get(parent_id)
                if parent_obj is not None:
                    parent_obj["children"][obj["slug"]] = obj
                else:
                    root_objects[obj["slug"]] = obj

        self.add_path_context(root_objects)

        ordered_hierarchy = self.order_hierarchy(
            root_objects[ROOT]["children"]
        )

        return ordered_hierarchy

    def order_hierarchy(self, hierarchy):
        if "index" in hierarchy:
            index_item = hierarchy.pop("index")
        sorted_items = dict(sorted(hierarchy.items(), key=lambda x: x[0]))
        sorted_hierarchy = {"index": index_item}
        sorted_hierarchy.update(sorted_items)

        return sorted_hierarchy
