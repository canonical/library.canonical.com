import os
from datetime import datetime
from typing import Optional
from sqlalchemy.exc import OperationalError, ProgrammingError
from webapp.models import Document
from webapp.db import db

USE_DB_ENV = "POSTGRESQL_DB_CONNECT_STRING" in os.environ
_USE_DB_RUNTIME = True  # toggled off if table missing/RO


def use_db() -> bool:
    return USE_DB_ENV and _USE_DB_RUNTIME


def _disable_db(reason: str):
    global _USE_DB_RUNTIME
    _USE_DB_RUNTIME = False
    print(f"[db] Disabling DB usage at runtime: {reason}", flush=True)


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
    if use_db():
        print("Using database to fetch or parse document", flush=True)

        print("Checking for document in DB", flush=True)
        print(f"Doc ID: {doc_id}", flush=True)
        try:
            document = Document.query.filter_by(google_drive_id=doc_id).first()
            if document:
                print("Found document in DB", flush=True)
                from webapp.parser import Parser

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
        except (OperationalError, ProgrammingError) as e:
            # UndefinedTable or DB unavailable -> fallback to Drive and stop using DB
            _disable_db(str(e))

    # Not in DB or DB unavailable: fetch, parse, and (if possible) store
    from webapp.parser import Parser

    parser = Parser(google_drive, doc_id, doc_dict, doc_name)
    print("Parsing document from Google Drive", flush=True)

    if use_db():
        try:
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
        except (OperationalError, ProgrammingError) as e:
            _disable_db(str(e))
        except Exception as e:
            print(f"Could not save to DB: {e}", flush=True)

    return parser
