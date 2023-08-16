from bs4 import BeautifulSoup


with open("tests/mocks/data/mock_google_doc.html", "r") as f:
    mock_google_doc = f.read()


def get_html_mock(self, drive):
    mock_html = mock_google_doc
    return BeautifulSoup(mock_html, features="lxml")
