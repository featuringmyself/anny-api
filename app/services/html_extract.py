import json
import re
from typing import Any

from bs4 import BeautifulSoup

# ChatGPT chrome / empty-composer signals — not a real buyer answer.
_CHROME_MARKERS = (
    "where should we begin?",
    "what's on your mind?",
    "ask anything",
    "message chatgpt",
    "how can i help you today?",
)


class CaptureQualityError(ValueError):
    """Raised when captured HTML is empty chrome, not an assistant answer."""


def assistant_node(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return (
        soup.select_one('[data-message-author-role="assistant"]')
        or soup.select_one('[data-message-role="assistant"]')
        or soup.select_one(".agent-turn")
        or soup
    )


def strip_citations(assistant) -> None:
    """Strip citation pills / reference anchors only — do not remove .contents."""
    for tag in assistant.select(
        '[data-testid="webpage-citation-pill"], '
        "[data-content-reference-start], "
        "a[href*='citation'], "
        "span[data-state='closed'][data-testid*='citation']"
    ):
        tag.decompose()


def extract_assistant_text(html: str) -> str:
    """Extract clean plain text from a ChatGPT assistant turn HTML."""
    assistant = assistant_node(html)
    strip_citations(assistant)

    for br in assistant.find_all("br"):
        br.replace_with("\n")

    text = assistant.get_text()
    return re.sub(r"[ \t]+", " ", text).strip()


def is_capture_garbage(text: str) -> bool:
    """True when text looks like empty ChatGPT chrome, not a real answer."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if len(normalized) < 40:
        return True
    return any(marker in normalized for marker in _CHROME_MARKERS)


def validate_capture_text(text: str) -> str:
    """Return text or raise CaptureQualityError for empty/chrome captures."""
    if is_capture_garbage(text):
        raise CaptureQualityError(
            "Captured HTML looks like empty ChatGPT chrome, not an assistant answer"
        )
    return text


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _clean_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        return re.sub(r"\s+", " ", obj).strip()
    if isinstance(obj, dict):
        return {k: _clean_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_strings(item) for item in obj]
    return obj


def _is_json_value_start(s: str, k: int) -> bool:
    if k >= len(s):
        return False
    if s[k] in '"[{':
        return True
    if s[k] in "0123456789-":
        return True
    for lit in ("true", "false", "null"):
        if s.startswith(lit, k):
            end = k + len(lit)
            if end >= len(s) or s[end] in ',}] \t\r\n':
                return True
    return False


def _looks_like_string_end(s: str, i: int) -> bool:
    """True when quote at i is likely a JSON string terminator, not prose."""
    j = i + 1
    while j < len(s) and s[j] in " \t\r\n":
        j += 1
    if j >= len(s):
        return True
    nxt = s[j]
    if nxt in "}]":
        return True
    if nxt == ":":
        return True
    if nxt == ",":
        k = j + 1
        while k < len(s) and s[k] in " \t\r\n":
            k += 1
        return _is_json_value_start(s, k)
    return False


def _repair_json(raw: str) -> str:
    """
    Best-effort repair for ChatGPT JSON:
    - escape bare " inside string values (common in excerpts)
    - escape raw newlines/tabs inside strings
    - drop trailing commas before } or ]
    """
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if c != '"':
            out.append(c)
            i += 1
            continue

        out.append('"')
        i += 1
        while i < n:
            c = raw[i]
            if c == "\\":
                out.append(c)
                if i + 1 < n:
                    out.append(raw[i + 1])
                    i += 2
                else:
                    i += 1
                continue
            if c == '"':
                if _looks_like_string_end(raw, i):
                    out.append('"')
                    i += 1
                    break
                out.append('\\"')
                i += 1
                continue
            if c == "\n":
                out.append("\\n")
                i += 1
                continue
            if c == "\r":
                out.append("\\r")
                i += 1
                continue
            if c == "\t":
                out.append("\\t")
                i += 1
                continue
            out.append(c)
            i += 1

    repaired = "".join(out)
    return re.sub(r",\s*([}\]])", r"\1", repaired)


def _try_loads(raw: str) -> Any | None:
    for candidate in (raw, _strip_fences(raw), _repair_json(_strip_fences(raw))):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _extract_fenced_blocks(text: str) -> list[str]:
    return [
        m.group(1).strip()
        for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        if m.group(1).strip()
    ]


def _extract_balanced_slices(text: str, open_ch: str, close_ch: str) -> list[str]:
    """
    Extract top-level balanced [...] or {...} slices.
    Quote tracking is best-effort; callers still run repair+loads.
    """
    results: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != open_ch:
            i += 1
            continue
        start = i
        depth = 0
        in_str = False
        escape = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == open_ch:
                    depth += 1
                elif c == close_ch:
                    depth -= 1
                    if depth == 0:
                        results.append(text[start : j + 1])
                        i = j
                        break
            j += 1
        i += 1
    return results


def _candidate_json_blobs(text: str) -> list[str]:
    """Ordered candidate JSON substrings: fences, then arrays, then objects."""
    stripped = _strip_fences(text.strip())
    candidates: list[str] = []
    seen: set[str] = set()

    def add(blob: str) -> None:
        blob = blob.strip()
        if blob and blob not in seen:
            seen.add(blob)
            candidates.append(blob)

    add(stripped)
    for fence in _extract_fenced_blocks(text):
        add(fence)

    arrays = _extract_balanced_slices(text, "[", "]")
    objects = _extract_balanced_slices(text, "{", "}")

    # Prefer whichever structure appears first in the text.
    first_array = text.find("[")
    first_object = text.find("{")
    if first_array != -1 and (first_object == -1 or first_array <= first_object):
        for blob in arrays:
            add(blob)
        for blob in objects:
            add(blob)
    else:
        for blob in objects:
            add(blob)
        for blob in arrays:
            add(blob)

    # Greedy regex fallback for when quote-aware balancing fails on broken JSON.
    array_match = re.search(r"(\[[\s\S]*\])", text)
    object_match = re.search(r"(\{[\s\S]*\})", text)
    if array_match:
        add(array_match.group(1))
    if object_match:
        add(object_match.group(1))

    return candidates


def _parse_object_list_fallback(text: str) -> list[Any] | None:
    """
    When the outer array is unparsable, recover individual {...} objects
    that look like analysis rows (contain an "id" key).
    """
    objects = _extract_balanced_slices(text, "{", "}")
    parsed: list[Any] = []
    for blob in objects:
        data = _try_loads(blob)
        if isinstance(data, dict) and "id" in data:
            parsed.append(data)
    return parsed or None


def extract_json_from_text(text: str) -> dict[str, Any] | list[Any] | None:
    """Best-effort parse of a JSON object or array embedded in assistant text."""
    if not text or not text.strip():
        return None

    for raw in _candidate_json_blobs(text):
        data = _try_loads(raw)
        if isinstance(data, (dict, list)):
            return _clean_strings(data)

    fallback = _parse_object_list_fallback(text)
    if fallback is not None:
        return _clean_strings(fallback)
    return None


def extract_json_from_html(html: str) -> dict[str, Any] | list[Any] | None:
    """Extract assistant text from HTML, then parse embedded JSON."""
    return extract_json_from_text(extract_assistant_text(html))
