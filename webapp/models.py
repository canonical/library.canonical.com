from webapp.db import db
from sqlalchemy.dialects.postgresql import JSON

DOC_TYPES = ("Introduction", "How to", "Reference", "Entity Page", "")


class Document(db.Model):
    __tablename__ = "Documents"

    id = db.Column(db.Integer, primary_key=True)
    google_drive_id = db.Column(db.String, unique=True, nullable=False)
    date_planned_review = db.Column(db.Date, nullable=True)
    doc_type = db.Column(
        "type", db.Enum(*DOC_TYPES, name="doc_type"), nullable=True
    )
    owner = db.Column(db.String, nullable=True)
    full_html = db.Column(db.Text, nullable=False)
    path = db.Column(db.String, unique=True, nullable=False, index=True)
    doc_metadata = db.Column(JSON, nullable=True)
    headings_map = db.Column(JSON, nullable=True)

    def __repr__(self):
        return f"<Document google_drive_id={self.google_drive_id}>"
