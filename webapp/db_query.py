from sqlalchemy.exc import OperationalError
from webapp.models import Document
from bs4 import BeautifulSoup

from webapp.parser import Parser


def is_db_available():
    try:
        # Try a simple query to check DB connectivity
        Document.query.first()
        return True
    except OperationalError:
        print("Database not available, falling back to Google Drive.")
        return False


def get_or_parse_document(doc_id, doc_dict, doc_name, google_drive):
    db_available = is_db_available()
    if db_available:
        document = Document.query.filter_by(doc_id=doc_id).first()
        if document:
            # Use cached HTML and metadata from the DB
            parser = Parser(
                google_drive,
                doc_id,
                doc_dict,
                doc_name,
                html_string=document.parsed_html,
                metadata=document.metadata,
                headings_map=document.headings_map,
            )
            return parser

    # Not in DB or DB unavailable: fetch, parse, and (if possible) store
    parser = Parser(google_drive, doc_id, doc_dict, doc_name)
    if db_available:
        new_doc = Document(
            doc_id=doc_id,
            metadata=parser.metadata,
            parsed_html=str(parser.html),
            headings_map=parser.headings_map,
        )
        from webapp.app import db  # Import here to avoid circular import

        db.session.add(new_doc)
        db.session.commit()
    return parser
