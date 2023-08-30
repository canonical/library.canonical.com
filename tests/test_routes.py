import unittest

from webapp.app import app


class TestRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        """
        Setup Flask app for testing once for all tests
        """
        app.testing = True
        self.app = app.test_client()
        with self.app.session_transaction() as sess:
            sess["openid"] = {
                "identity_url": "localhost",
                "email": "testing@ubuntu.com",
                "fullname": "Test user",
            }

    def setUp(self):
        """
        Create a new client instance before each test
        """
        self.client = app.test_client()

    @classmethod
    def tearDownClass(self):
        """
        Teardown Flask app after all tests have run
        """
        self.app = None

    def test_home_page(self):
        """
        When given the index URL,
        we should return a 200 status code
        """
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        """
        When given a non-existent URL,
        we should return a 404 status code
        """
        response = self.app.get("/not-found-url")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
