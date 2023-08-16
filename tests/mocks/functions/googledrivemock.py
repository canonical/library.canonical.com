import json

with open("tests/mocks/data/mock_file_list.json", "r") as f:
    mock_file_list = json.load(f)
with open("tests/mocks/data/mock_google_doc.html", "r") as f:
    mock_google_doc = f.read()

class GoogleDriveMock:
    def __init__(self):
        self.mock_google_doc = mock_google_doc
        self.mock_file_list = mock_file_list["file_list"]

    def fetch_document(self, document_id):
        """
        Mocks fetching a Google Doc.

        :param document_id: Does nothing and only allows it to
        work within the Parser
        """
        return self.mock_google_doc
    
    def get_document_list(self):
        """
        Mocks retrieving a list of documents from a chosen google drive

        :return: Mocked list of document information.
        """
        return self.mock_file_list
