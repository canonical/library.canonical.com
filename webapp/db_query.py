import os

USE_DB = "POSTGRES_DB_HOST" in os.environ


def get_or_parse_document(
    google_drive,
    doc_id,
    doc_dict,
    doc_name,
):
    if USE_DB:
        print("Using database to fetch or parse document", flush=True)
        from webapp.models import (
            Document,
        )  # Import here to avoid import errors if DB is not used
        from sqlalchemy.exc import OperationalError

        try:
            document = Document.query.filter_by(doc_id=doc_id).first()
            if document:
                print("Found document in DB", flush=True)
                from webapp.parser import Parser

                parser = Parser(
                    google_drive,
                    doc_id,
                    doc_dict,
                    doc_name,
                    html_string=document.parsed_html,
                    metadata=document.doc_metadata,
                    headings_map=document.headings_map,
                )
                return parser
        except OperationalError:
            print(
                "Database not available, falling back to Google Drive.",
                flush=True,
            )
            print("NO DB, fetching from Google Drive", flush=True)

    # Not in DB or DB unavailable: fetch, parse, and (if possible) store
    from webapp.parser import Parser

    parser = Parser(google_drive, doc_id, doc_dict, doc_name)
    print("Parsing document from Google Drive", flush=True)

    if USE_DB:
        try:
            from webapp.models import Document
            from webapp.db import db

            print("Saving document to DB", flush=True)
            new_doc = Document(
                doc_id=doc_id,
                doc_metadata=parser.metadata,
                parsed_html=str(parser.html),
                headings_map=parser.headings_map,
            )
            db.session.add(new_doc)
            db.session.commit()
            print("Document saved to DB successfully", flush=True)
        except Exception as e:
            print(f"Could not save to DB: {e}", flush=True)
    return parser
