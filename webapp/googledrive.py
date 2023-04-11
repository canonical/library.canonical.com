import io

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO


class Drive:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )

    def get_hierarchy(self):

        try:
            results = (
                self.service.files()
                .list(
                    spaces='drive',
                    fields='nextPageToken, '
                    'files(id, name, parents)',)
                .execute()
            )
            items = results.get("files", [])
        except HttpError as error:
            print(f"An error occurred: {error}")

        hierarchy = self.create_hierarchy(items)

        return hierarchy

    def get_html(self, document_id):
        """GETs a specific document based off its ID"""
        request = self.service.files().export(
            fileId=document_id, mimeType="text/html"
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        html = fh.getvalue().decode("utf-8")

        return html


    def create_hierarchy(self, document_list):
        object_map = {obj['id']: {'name': obj['name'], 'id': obj['id'], 'children': []} for obj in document_list}
        root_objects = []

        for obj in document_list:
            if 'parents' in obj:
                for parent_id in obj['parents']:
                    if parent_id in object_map:
                        object_map[parent_id]['children'].append(object_map[obj['id']])
                        break
            else:
                root_objects.append(object_map[obj['id']])

        return root_objects

