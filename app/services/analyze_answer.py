import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.engine import ChatGPTQueryRequest, query_chatgpt
from app.schemas.chatgpt import ReturnType
from app.schemas.get_questions import ReconstructedProfile
from app.services.html_extract import extract_assistant_text, extract_json_from_html

# Fallback chunk size when a full-batch ChatGPT JSON response cannot be parsed.
_ANALYZE_CHUNK_SIZE = 6
_PREVIEW_CHARS = 240


class BatchAnalyzeError(RuntimeError):
    """Raised when the batch analyze browser call cannot be parsed."""


class AnswerAnalysis(BaseModel):
    id: str = Field(default="", description="Prompt id this analysis belongs to")
    brandCited: bool = Field(default=False, description="Whether the brand was cited")
    status: Literal["present", "absent", "nuanced", "error"] = Field(
        default="absent", description="Citation status for the brand"
    )
    statusLabel: str = Field(
        default="",
        description="Exhibit status line, e.g. Absent · Vision Lakshya named",
    )
    citedInstead: list[str] = Field(
        default_factory=list,
        description="Competitors or institutes named instead of (or alongside) the brand",
    )
    excerpt: str = Field(
        default="",
        description="Compressed answer facts — names, scores, shortlists (not opinion)",
    )
    title: str = Field(default="", description="Short title for the crisis/prompt row")
    outcome: str = Field(default="", description="One-line outcome summary")
    tag: str = Field(default="", description="Category/topic tag")
    dealLoss: str = Field(
        default="",
        description=(
            "One factual commercial-stake line: who gets the shortlist/"
            "enrolment/demo today and who does not"
        ),
    )


def build_batch_analyze_prompt(
    brand_name: str,
    profile: ReconstructedProfile,
    items: list[dict],
) -> str:
    competitors = ", ".join(profile.primaryCompetitors) or "unknown"
    items_json = json.dumps(items, indent=2)
    return f'''You are an AI visibility auditor at Anny. Analyze EVERY ChatGPT answer below for brand citation outcomes in ONE response.

Prove diverted demand with cold facts. Do not pitch. Do not praise. Do not console.

Brand under audit: "{brand_name}"
Inferred domain: "{profile.inferredDomain}"
Industry: "{profile.industry}"
Product line: "{profile.productLine}"
Known competitors: {competitors}

Items to analyze (JSON array of {{id, kind, query, answer_text}}):
{items_json}

For EACH item, decide whether "{brand_name}" (or its domain) is cited as a recommended/relevant option.
Status meanings:
- "present": brand is clearly recommended or named as a viable option
- "absent": brand is missing; competitors or others fill the answer
- "nuanced": brand appears but with caveats, confusion, or weak positioning

statusLabel style (Edukemy exhibit): "Absent · Vision Lakshya named", "Present · named in shortlist", "Nuanced · mentioned with caveats".

EXCERPT RULE (critical): Quote/compress what ChatGPT said — names, scores, shortlists, rankings.
FORBIDDEN in excerpt/title/outcome: meta opinion ("clearly named and evaluated", "strong option", "the brand is missing from recommendations").
Write the excerpt as compressed answer facts only.
Inside JSON string values, do NOT use raw double quotes; use single quotes for any quoted phrases.

dealLoss RULE: one factual commercial-stake line naming who gets the shortlist / enrolment / demo today and that "{brand_name}" does not (or the caveat if nuanced). No "this terrifies the founder." No persuasion.

Output a strict JSON ARRAY only (no markdown fences, no prose before/after), one object per input id, same order:
[
  {{
    "id": "q1",
    "brandCited": false,
    "status": "absent",
    "statusLabel": "Absent · Vision Lakshya named",
    "citedInstead": ["VisionIAS", "InsightsIAS"],
    "excerpt": "VisionIAS Lakshya, InsightsIAS MARG... No {brand_name}.",
    "title": "Integrated mentorship",
    "tag": "Absent · Vision Lakshya named",
    "outcome": "Absent · Vision Lakshya named",
    "dealLoss": "Integrated prep shortlist goes to VisionIAS / InsightsIAS; enrolment intent never sees {brand_name}."
  }}
]

You MUST return one object for every input id. Do not invent answers that contradict answer_text.
'''


def _preview_text(text: str, limit: int = _PREVIEW_CHARS) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _unwrap_analyses_payload(data: Any) -> list[Any] | None:
    """Normalize ChatGPT shapes into a list of analysis objects."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return None

    for key in ("analyses", "results", "items", "data", "answers"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    # Single analysis object with an id — treat as a 1-item batch.
    if "id" in data and ("status" in data or "brandCited" in data):
        return [data]

    return None


def _analyses_from_payload(
    data: Any,
    items: list[dict],
) -> list[AnswerAnalysis]:
    unwrapped = _unwrap_analyses_payload(data)
    if not unwrapped:
        raise BatchAnalyzeError(
            "Batch analyze response could not be parsed as a JSON array"
        )

    by_id: dict[str, AnswerAnalysis] = {}
    for raw in unwrapped:
        if not isinstance(raw, dict):
            continue
        try:
            analysis = AnswerAnalysis.model_validate(raw)
        except Exception:
            continue
        if analysis.id:
            by_id[analysis.id] = analysis

    results: list[AnswerAnalysis] = []
    for item in items:
        item_id = str(item.get("id") or "")
        if item_id in by_id:
            results.append(by_id[item_id])
            continue
        results.append(
            AnswerAnalysis(
                id=item_id,
                brandCited=False,
                status="error",
                statusLabel="Analysis missing",
                excerpt="",
                title="Analysis missing",
                outcome="Per-id analysis missing from batch response",
                tag="Error",
            )
        )

    # If NOTHING was successfully parsed from the batch, fail the report.
    if not by_id:
        raise BatchAnalyzeError(
            "Batch analyze returned no valid per-id analyses"
        )

    return results


async def _query_analyze_html(
    brand_name: str,
    profile: ReconstructedProfile,
    items: list[dict],
) -> str:
    question = build_batch_analyze_prompt(brand_name, profile, items)
    response = await query_chatgpt(
        ChatGPTQueryRequest(
            brandName=brand_name,
            question=question,
            returnType=ReturnType.html,
        )
    )
    return response.content


async def _batch_analyze_once(
    brand_name: str,
    profile: ReconstructedProfile,
    items: list[dict],
) -> list[AnswerAnalysis]:
    html = await _query_analyze_html(brand_name, profile, items)
    data = extract_json_from_html(html)

    try:
        return _analyses_from_payload(data, items)
    except BatchAnalyzeError as exc:
        preview = _preview_text(extract_assistant_text(html))
        raise BatchAnalyzeError(f"{exc} | preview: {preview}") from exc


async def batch_analyze_all(
    brand_name: str,
    profile: ReconstructedProfile,
    items: list[dict],
) -> list[AnswerAnalysis]:
    """
    Analyze captured answers via chatgpt.com (browser).
    Tries one full-batch call first; on parse failure, retries in chunks of ~6.
    Raises BatchAnalyzeError if JSON cannot be parsed (no fake absent rows).
    Per-id misses become status=error and must be excluded from score/SOV by callers.
    """
    if not items:
        return []

    try:
        return await _batch_analyze_once(brand_name, profile, items)
    except BatchAnalyzeError:
        if len(items) <= _ANALYZE_CHUNK_SIZE:
            raise

    # Full-batch response was truncated/malformed — analyze in smaller chunks.
    by_id: dict[str, AnswerAnalysis] = {}
    chunk_errors: list[str] = []

    for start in range(0, len(items), _ANALYZE_CHUNK_SIZE):
        chunk = items[start : start + _ANALYZE_CHUNK_SIZE]
        try:
            chunk_results = await _batch_analyze_once(brand_name, profile, chunk)
        except BatchAnalyzeError as exc:
            chunk_errors.append(str(exc))
            continue
        for analysis in chunk_results:
            if analysis.id and analysis.status != "error":
                by_id[analysis.id] = analysis
            elif analysis.id and analysis.id not in by_id:
                by_id[analysis.id] = analysis

    if not by_id:
        detail = "Batch analyze response could not be parsed as a JSON array"
        if chunk_errors:
            detail = f"{detail} (chunked fallback also failed: {chunk_errors[0]})"
        raise BatchAnalyzeError(detail)

    results: list[AnswerAnalysis] = []
    for item in items:
        item_id = str(item.get("id") or "")
        if item_id in by_id:
            results.append(by_id[item_id])
            continue
        results.append(
            AnswerAnalysis(
                id=item_id,
                brandCited=False,
                status="error",
                statusLabel="Analysis missing",
                excerpt="",
                title="Analysis missing",
                outcome="Per-id analysis missing from batch response",
                tag="Error",
            )
        )
    return results
