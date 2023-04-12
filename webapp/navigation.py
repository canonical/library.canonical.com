from webapp.googledrive import Drive


class Navigation:
    def __init__(self, google_drive: Drive):
        try:
            file_list = google_drive.get_document_list()
        except Exception as e:
            print(e)
        self.hierarchy = self.create_hierarchy(file_list)

    def create_hierarchy(self, objects):
        object_dict = {}
        root_objects = []

        # create a temp storage for each item and append children prop
        for obj in objects:
            obj["children"] = []
            obj["mimeType"] = obj["mimeType"].rpartition(".")[-1]
            object_dict[obj["id"]] = obj

        # iterate through temp storage to create parent-child relationships
        for obj in objects:
            parent_ids = obj["parents"]
            for parent_id in parent_ids:
                parent_obj = object_dict.get(parent_id)
                if parent_obj is not None:
                    parent_obj["children"].append(obj)
                else:
                    root_objects.append(obj)

        return root_objects
