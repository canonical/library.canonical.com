import unittest

from webapp.app import app

class TestRoutes(unittest.TestCase):
    def setUp(self):
        """
        Setup Flask app for testing
        """
        app.testing = True
        self.app = app.test_client()
        with self.app.session_transaction() as sess:
            sess["openid"] = {
                "identity_url": "localhost",
                "email": "testing@ubuntu.com",
                "fullname": "Test user",
            }

    def test_home_page(self):
        """
        When given the index URL,
        we should return a 200 status code
        """
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        """
        When given a non-existent URL,
        we should return a 404 status code
        """
        response = self.app.get("/not-found-url")
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
