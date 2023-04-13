from webapp.googledrive import Drive


class Navigation:
    def __init__(self, google_drive: Drive):
        file_list = google_drive.get_document_list()
        self.hierarchy = self.create_hierarchy(file_list)

    def create_hierarchy(self, objects):
        object_dict = {}
        root_objects = {}

        for obj in objects:
            obj["children"] = {}
            obj["mimeType"] = obj["mimeType"].rpartition(".")[-1]
            obj["slug"] = "-".join(obj["name"].split(" ")).lower()
            object_dict[obj["id"]] = obj

        for obj in objects:
            parent_ids = obj["parents"]
            for parent_id in parent_ids:
                parent_obj = object_dict.get(parent_id)
                if parent_obj is not None:
                    parent_obj["children"][obj["slug"]] = obj
                else:
                    root_objects[obj["slug"]] = obj

        return root_objects
