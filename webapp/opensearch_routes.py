import os
import json
import requests
from flask import Blueprint, jsonify, request

from webapp.db import db
from webapp.models import Document
from webapp.services.opensearch_service import (
    requests_session_with_env_ca,
)


opensearch_bp = Blueprint("opensearch", __name__, url_prefix="/opensearch")


@opensearch_bp.route("/bulk/run", methods=["GET", "POST"])
def opensearch_bulk_run():
    """Stream all documents from DB to OpenSearch _bulk endpoint."""
    # Require DB
    if "POSTGRESQL_DB_CONNECT_STRING" not in os.environ:
        return ("DB not configured", 503)

    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")  # single line with \n is OK
    index_name = request.args.get("index") or os.getenv(
        "OPENSEARCH_INDEX", "library-docs"
    )

    if not base_url or not username or not password:
        return ("Missing OPENSEARCH_URL/USERNAME/PASSWORD", 400)

    def fmt_date(d):
        return d.strftime("%d-%m-%Y") if d else None

    def ndjson_iter():
        for doc in db.session.query(Document).yield_per(1000):
            action = {
                "index": {"_index": index_name, "_id": doc.google_drive_id}
            }
            yield json.dumps(action, ensure_ascii=False) + "\n"
            source = {
                "google_drive_ID": doc.google_drive_id,
                "date_planned_review": fmt_date(doc.date_planned_review),
                "type": doc.doc_type,
                "owner": doc.owner,
                "full_html": doc.full_html,
                "path": doc.path,
            }
            if hasattr(doc, "doc_metadata") and doc.doc_metadata is not None:
                source["doc_metadata"] = doc.doc_metadata
            if hasattr(doc, "headings_map") and doc.headings_map is not None:
                source["headings_map"] = doc.headings_map
            yield json.dumps(source, ensure_ascii=False) + "\n"

    try:
        http = requests_session_with_env_ca(tls_ca) if tls_ca else requests
    except Exception as e:
        return jsonify({"error": f"Invalid OPENSEARCH_TLS_CA: {e}"}), 400

    # Send to OpenSearch bulk endpoint
    try:
        resp = http.post(
            f"{base_url.rstrip('/')}/_bulk",
            data=ndjson_iter(),
            headers={"Content-Type": "application/x-ndjson"},
            auth=(username, password),
            timeout=300,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    # Parse response and return a compact summary
    summary = {"status": resp.status_code}
    try:
        body = resp.json()
        summary.update(
            {
                "errors": body.get("errors"),
                "took": body.get("took"),
                "items_count": (
                    len(body.get("items", []))
                    if isinstance(body.get("items"), list)
                    else None
                ),
            }
        )
        if body.get("errors") is True:
            # include first error item for quick debug
            for it in body.get("items", []):
                op = next(iter(it))
                if it[op].get("error"):
                    summary["first_error"] = it[op]["error"]
                    break
    except ValueError:
        summary["text"] = resp.text[:1000]

    return jsonify(summary), resp.status_code


@opensearch_bp.route("/indices", methods=["GET"])
def opensearch_list_indices():
    """List OpenSearch indices via _cat/indices."""
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    if not (base_url and username and password):
        return jsonify({"error": "OpenSearch not configured"}), 503

    try:
        try:
            http = requests_session_with_env_ca(tls_ca) if tls_ca else requests
        except NameError:
            http = requests

        resp = http.get(
            f"{base_url.rstrip('/')}/_cat/indices",
            auth=(username, password),
            params={"format": "json", "expand_wildcards": "all"},
            timeout=20,
        )
        # Pass through JSON body and status
        return (
            resp.text,
            resp.status_code,
            {
                "Content-Type": resp.headers.get(
                    "Content-Type", "application/json"
                )
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@opensearch_bp.route("/docs", methods=["GET"])
def opensearch_list_docs():
    """
    List documents from an OpenSearch index.
    Query params:
      - index: index name (default OPENSEARCH_INDEX or 'library-docs')
      - q: optional simple query (uses GET q=... form if provided)
      - size: page size (default 50)
      - from: offset for pagination (default 0)
      - raw=1: return raw OpenSearch response
    """
    base_url = os.getenv("OPENSEARCH_URL")
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")
    tls_ca = os.getenv("OPENSEARCH_TLS_CA")

    if not (base_url and username and password):
        return jsonify({"error": "OpenSearch not configured"}), 503

    index_name = request.args.get("index") or os.getenv(
        "OPENSEARCH_INDEX", "library-docs"
    )
    size = int(request.args.get("size", "50"))
    from_ = int(request.args.get("from", "0"))
    q = request.args.get("q")
    raw = request.args.get("raw") == "1"

    try:
        try:
            http = requests_session_with_env_ca(tls_ca) if tls_ca else requests
        except NameError:
            http = requests

        if q:
            # Simple URI search like docs: GET /{index}/_search?q=...
            includes = "path,owner,type,doc_metadata,full_html"
            resp = http.get(
                f"{base_url.rstrip('/')}/{index_name}/_search",
                auth=(username, password),
                params={
                    "q": q,
                    "size": size,
                    "from": from_,
                    "default_operator": "and",
                    "_source_includes": includes,
                },
                timeout=30,
            )
        else:
            # JSON body search with match_all
            resp = http.post(
                f"{base_url.rstrip('/')}/{index_name}/_search",
                auth=(username, password),
                headers={"Content-Type": "application/json"},
                json={
                    "query": {"match_all": {}},
                    "_source": {
                        "includes": [
                            "path",
                            "owner",
                            "type",
                            "doc_metadata",
                            "full_html",
                        ]
                    },
                    "size": size,
                    "from": from_,
                },
                timeout=30,
            )

        data = resp.json()
        if raw:
            return jsonify(data), resp.status_code

        hits = data.get("hits", {})
        total = (
            hits.get("total", {}).get("value")
            if isinstance(hits.get("total"), dict)
            else hits.get("total")
        )
        items = []
        for h in hits.get("hits", []):
            src = h.get("_source") or {}
            meta = src.get("doc_metadata") or {}
            items.append(
                {
                    "id": h.get("_id"),
                    "score": h.get("_score"),
                    "path": src.get("path"),
                    "owner": src.get("owner"),
                    "type": src.get("type"),
                    "title": meta.get("title"),
                    "full_html_snippet": (src.get("full_html") or "")[:200],
                }
            )

        return (
            jsonify(
                {
                    "index": index_name,
                    "from": from_,
                    "size": size,
                    "total": total,
                    "hits": items,
                }
            ),
            resp.status_code,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502
