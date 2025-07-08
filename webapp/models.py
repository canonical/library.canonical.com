from webapp.db import db
from sqlalchemy.dialects.postgresql import JSON


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    doc_id = db.Column(db.String, unique=True, nullable=False)
    doc_metadata = db.Column(JSON, nullable=False)
    parsed_html = db.Column(db.Text, nullable=False)
    headings_map = db.Column(JSON, nullable=True)  # <-- Add this line

    def __repr__(self):
        return f"<Document doc_id={self.doc_id}>"
