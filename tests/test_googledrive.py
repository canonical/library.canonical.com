import unittest
from webapp.googledrive import Drive

class GoogleDriveTestCase(unittest.TestCase):
    def setUp(self):
        """
        Establish google drive connection for testing
        """
        self.drive = Drive()

    def test_get_list(self):
        """
        Fetch list of all documents from google drive and
        check list length is greater than 1
        """
        document_list = self.drive.get_document_list()
        self.assertGreater(len(document_list), 1)

if __name__ == '__main__':
    unittest.main()
