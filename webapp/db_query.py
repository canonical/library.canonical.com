import os
from datetime import datetime
from typing import Optional

USE_DB = "POSTGRESQL_DB_CONNECT_STRING" in os.environ


def _normalize_doc_type(t: Optional[str]) -> Optional[str]:
    if not t:
        return None
    t = t.strip().lower()
    if t in ("how to", "how-to"):
        return "How to"
    if t == "introduction":
        return "Introduction"
    if t == "reference":
        return "Reference"
    if t in ("entity page", "entity"):
        return "Entity Page"
    return None


def get_or_parse_document(
    google_drive,
    doc_id,
    doc_dict,
    doc_name,
):
    if USE_DB:
        print("Using database to fetch or parse document", flush=True)
        from webapp.models import Document  # Import only when DB is used
        from sqlalchemy.exc import OperationalError

        print("Checking for document in DB", flush=True)
        print(f"Doc ID: {doc_id}", flush=True)
        # print(f"Doc Metadata: {doc_dict}", flush=True)
        try:
            # use correct column name
            document = Document.query.filter_by(google_drive_id=doc_id).first()
            if document:
                print("Found document in DB", flush=True)
                from webapp.parser import Parser

                print(document, flush=True)
                parser = Parser(
                    google_drive,
                    doc_id,
                    doc_dict,
                    doc_name,
                    html_string=document.full_html,
                    metadata=document.doc_metadata,
                    headings_map=document.headings_map,
                )
                return parser
        except OperationalError:
            print(
                "Database not available, falling back to Google Drive.",
                flush=True,
            )

    # Not in DB or DB unavailable: fetch, parse, and (if possible) store
    from webapp.parser import Parser

    parser = Parser(google_drive, doc_id, doc_dict, doc_name)
    print("Parsing document from Google Drive", flush=True)

    if USE_DB:
        try:
            from webapp.models import Document
            from webapp.db import db

            # derive fields from parser metadata and nav dict
            md = parser.metadata or {}
            owners = (
                md.get("owner") or md.get("owner(s)") or md.get("author(s)")
            )
            if isinstance(owners, list):
                owner = ", ".join([o for o in owners if o]) if owners else None
            else:
                owner = owners or None

            doc_type = _normalize_doc_type(md.get("type"))
            dpr = None
            if md.get("date_planned_review"):
                try:
                    dpr = datetime.strptime(
                        md["date_planned_review"], "%d-%m-%Y"
                    ).date()
                except ValueError:
                    dpr = None

            # path from navigation reference dict
            path = None
            ref = doc_dict.get(doc_id) or {}
            path = ref.get("full_path") or ref.get("path") or "/"

            new_doc = Document(
                google_drive_id=doc_id,
                date_planned_review=dpr,
                doc_type=doc_type,
                owner=owner,
                full_html=str(parser.html),
                path=path,
                doc_metadata=md,
                headings_map=parser.headings_map,
            )
            db.session.add(new_doc)
            db.session.commit()
            print("Document saved to DB successfully", flush=True)
        except Exception as e:
            print(f"Could not save to DB: {e}", flush=True)

    return parser
