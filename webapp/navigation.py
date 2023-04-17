from webapp.googledrive import Drive


class Navigation:
    def __init__(self, google_drive: Drive):
        file_list = google_drive.get_document_list()
        self.hierarchy = self.create_hierarchy(file_list)
        self.object_dict

    def create_hierarchy(self, objects):
        self.object_dict = {}
        root_objects = {}

        def add_full_path(obj, path=""):
            for key in obj.keys():
                obj[key]["full_path"] = path + "/" + obj[key]["slug"]
                if obj[key]["mimeType"] == "folder":
                    add_full_path(obj[key]["children"], obj[key]["full_path"])

        for obj in objects:
            obj["children"] = {}
            obj["mimeType"] = obj["mimeType"].rpartition(".")[-1]
            obj["slug"] = "-".join(obj["name"].split(" ")).lower()
            obj["active"] = False
            obj["expanded"] = False
            obj["path"] = ""
            self.object_dict[obj["id"]] = obj

        for obj in objects:
            parent_ids = obj["parents"]
            for parent_id in parent_ids:
                parent_obj = self.object_dict.get(parent_id)
                if parent_obj is not None:
                    parent_obj["children"][obj["slug"]] = obj
                else:
                    root_objects[obj["slug"]] = obj

        add_full_path(root_objects)

        return root_objects["library"]["children"]
