from bs4 import BeautifulSoup


from webapp.googledrive import Drive


class Parser:
    def __init__(self, google_drive: Drive, document_id: str):
        self.document_id = document_id

        try:
            raw_html = google_drive.get_html(document_id)
        except Exception as e:
            print(e)
        self.html = BeautifulSoup(raw_html, features="html.parser")
        self.html = self.remove_attrs(self.html)
        self.parse_metadata()

    def remove_attrs(self, soup):
        for tag in soup.findAll(True):
            del tag["style"]
        return soup

    def parse_metadata(self):
        table = self.html.select_one("table")
        if table:
            table.decompose()
