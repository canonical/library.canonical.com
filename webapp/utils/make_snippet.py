import re
import html
from typing import List, Optional


def _strip_tags_except_strong(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    # Normalize any <mark> to <strong>
    s = s.replace("<mark>", "<strong>").replace("</mark>", "</strong>")
    # Protect <strong> tags so we can strip other tags safely
    s = s.replace("<strong>", "[[[STRONG_OPEN]]]").replace(
        "</strong>", "[[[STRONG_CLOSE]]]"
    )
    # Remove any remaining HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Restore strong tags
    s = s.replace("[[[STRONG_OPEN]]]", "<strong>").replace(
        "[[[STRONG_CLOSE]]]", "</strong>"
    )
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _terms_from_query(query: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query or "")]


def _highlight_terms(text: str, query: str, max_marks: int = 5) -> str:
    terms = list({t for t in _terms_from_query(query) if t})
    if not text or not terms:
        return text or ""
    pattern = re.compile(
        r"(" + "|".join(map(re.escape, terms)) + r")", re.IGNORECASE
    )
    count = 0

    def repl(m):
        nonlocal count
        if count >= max_marks:
            return m.group(0)
        count += 1
        return f"<strong>{m.group(0)}</strong>"

    return pattern.sub(repl, text)


def sanitize_highlight_fragment(fragment: str) -> str:
    """
    Clean an OpenSearch highlight fragment:
      - Remove <mark>/<strong> tags inside other HTML tags (attributes).
      - Normalize <mark> to <strong>.
      - Strip all tags, preserving <strong>.
      - Normalize whitespace and hyphens.
    Returns HTML with only <strong> tags.
    """
    if not fragment:
        return ""
    s = fragment

    # Remove highlight tags that occur inside tag attributes
    prev = None
    while prev != s:
        prev = s
        s = re.sub(
            r"(<[^>]*?)</?(?:mark|strong)>([^>]*>)",
            r"\1\2",
            s,
            flags=re.IGNORECASE,
        )

    # Normalize any remaining <mark> to <strong>, then strip tags except <strong>
    s = s.replace("<mark>", "<strong>").replace("</mark>", "</strong>")
    s = _strip_tags_except_strong(s)

    # Normalize spaced hyphens and whitespace
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def render_snippet(
    highlight_fragments: Optional[List[str]],
    html_or_text: str,
    query: str,
    radius: int = 120,
) -> str:
    """
    Prefer OpenSearch highlight (sanitized). Fallback: make_snippet() then wrap query terms in <strong>.
    Returns sanitized HTML containing only <strong> tags.
    """
    if highlight_fragments and highlight_fragments[0]:
        return sanitize_highlight_fragment(highlight_fragments[0])
    snippet_text = make_snippet(html_or_text, query, radius)
    return _highlight_terms(snippet_text, query)


def make_snippet(html_or_text: str, query: str, radius: int = 120) -> str:
    if not html_or_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_or_text)
    text = re.sub(r"\s+", " ", text).strip()

    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", query)]
    if not terms:
        return text[: 2 * radius] + ("..." if len(text) > 2 * radius else "")

    lower = text.lower()
    idxs = [lower.find(t) for t in terms if lower.find(t) != -1]
    if not idxs:
        return text[: 2 * radius] + ("..." if len(text) > 2 * radius else "")

    idx = min(idxs)
    start = max(0, idx - radius)
    end = min(len(text), idx + radius)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
