import json
from datetime import datetime
from typing import Any

from app.engine import ChatGPTQueryRequest, query_chatgpt
from app.schemas.chatgpt import ReturnType
from app.schemas.get_questions import GetQuestionsResponse, ReconstructedProfile
from app.schemas.report import (
    BrandCrisisReportItem,
    ModelCoverageItem,
    PromptAuditItem,
    ShareOfVoiceItem,
    SnapshotSection,
    SprintSection,
    VisibilityReport,
)
from app.services.analyze_answer import AnswerAnalysis
from app.services.html_extract import extract_json_from_html


def label_for_score(score: float) -> str:
    """Edukemy label bands: Critical / Weak / Moderate / Strong."""
    if score >= 70:
        return "Strong"
    if score >= 40:
        return "Moderate"
    if score >= 20:
        return "Weak"
    return "Critical"


def _name_mentioned(name: str, analysis: AnswerAnalysis, brand_name: str) -> bool:
    name_l = name.strip().lower()
    if not name_l:
        return False
    if name_l == brand_name.strip().lower():
        return bool(analysis.brandCited or analysis.status in ("present", "nuanced"))
    return any(name_l == c.strip().lower() for c in analysis.citedInstead)


def compute_score_and_sov(
    brand_name: str,
    crisis_analyses: list[AnswerAnalysis],
    prompt_analyses: list[AnswerAnalysis],
) -> dict[str, Any]:
    """
    Discovery-only visibility score + discovery-only SOV in code.
    Crisis rows are exhibits only — they must not inflate the competitive chart.
    Rows with status=error are excluded from score and SOV denominators.
    """
    # crisis_analyses kept in signature for callers; intentionally unused for metrics.
    _ = crisis_analyses

    discovery = [a for a in prompt_analyses if a.status != "error"]
    cited_count = sum(
        1
        for a in discovery
        if a.brandCited or a.status in ("present", "nuanced")
    )
    discovery_total = len(discovery)
    visibility_score = (
        round(100 * cited_count / discovery_total) if discovery_total else 0
    )
    visibility_label = label_for_score(visibility_score)

    # SOV uses the same discovery-only pool as visibility score.
    names: set[str] = {brand_name}
    for a in discovery:
        for c in a.citedInstead:
            cleaned = (c or "").strip()
            if cleaned:
                names.add(cleaned)

    sov_rows: list[ShareOfVoiceItem] = []
    for name in names:
        mentions = sum(1 for a in discovery if _name_mentioned(name, a, brand_name))
        share = round(100 * mentions / discovery_total, 1) if discovery_total else 0.0
        sov_rows.append(
            ShareOfVoiceItem(
                name=name,
                share=share,
                isYou=name.strip().lower() == brand_name.strip().lower(),
            )
        )

    sov_rows.sort(key=lambda r: (-r.share, r.name.lower()))

    # Top 8 named entities + brand if missing from the cut.
    top = sov_rows[:8]
    if not any(r.isYou for r in top):
        brand_row = next((r for r in sov_rows if r.isYou), None)
        if brand_row:
            top = top[:7] + [brand_row]

    return {
        "citedCount": cited_count,
        "totalPrompts": discovery_total,
        "visibilityScore": float(visibility_score),
        "visibilityLabel": visibility_label,
        "competitiveShareOfVoice": top,
    }


def default_snapshot_date(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return dt.strftime("%B %Y")


def build_synthesize_prompt(
    brand_name: str,
    profile: ReconstructedProfile,
    analyses: list[dict],
    metrics: dict[str, Any],
) -> str:
    analyses_json = json.dumps(analyses, indent=2)
    sov_json = json.dumps(
        [r.model_dump() for r in metrics["competitiveShareOfVoice"]], indent=2
    )
    competitors = ", ".join(profile.primaryCompetitors) or "unknown"
    return f'''You write Anny AI visibility baseline briefs. Sell by proving diverted demand. Never pitch.

Brand: "{brand_name}"
Website: "{profile.inferredDomain}"
Industry (draft): "{profile.industry}"
Product line (draft): "{profile.productLine}"
ICP: "{profile.targetIcp}"
Competitors: {competitors}
HQ / hub: "{profile.headquartersOrHub}"

FIXED METRICS (do not change these numbers — they were computed in code):
- citedCount (discovery only): {metrics["citedCount"]}
- totalPrompts (discovery only): {metrics["totalPrompts"]}
- visibilityScore: {metrics["visibilityScore"]}
- visibilityLabel: "{metrics["visibilityLabel"]}"
- competitiveShareOfVoice (fixed):
{sov_json}

Per-prompt analyses (JSON):
{analyses_json}

Produce strict JSON only (no markdown fences) with this shape:
{{
  "executiveSummary": "{metrics["totalPrompts"]} buy-intent prompts tied to {profile.productLine or "the product shelf"}. Cited on {metrics["citedCount"]} of {metrics["totalPrompts"]}. Who appears instead: top competitors from analyses. One asymmetric win if any (as exception, not consolation). End with: This is the baseline.",
  "industry": "Short eyebrow-length polish of industry if draft is too long; else keep short",
  "productLine": "Short product/service shelf polish; else keep short",
  "sprint": {{
    "headline": "From this {metrics["citedCount"]}/{metrics["totalPrompts"]} baseline to cited on the enrolment prompts named below",
    "outcomes": [
      "Get named on [specific prompt cluster] that today lists [competitors]",
      "Get named on [specific prompt cluster] that today lists [competitors]",
      "Get named on [specific prompt cluster] that today lists [competitors]"
    ]
  }}
}}

Rules:
- Do NOT invent or alter visibilityScore, citedCount, totalPrompts, or SOV shares.
- executiveSummary: cold baseline brief only — prompt-set size, cited X of Y, who appears instead, optional asymmetric win as exception, "This is the baseline."
- Sprint headline: from baseline → cited on named enrolment prompts (not "close the gap" / "build visibility").
- Sprint outcomes: ONLY "get named on [prompt cluster] that today lists [competitors]" — three concrete lines from the analyses.
- Keep industry and productLine short (eyebrow length).
- BANNED words/phrases: authority, footprint, leverage, journey, unlock, empower, transform, book a call, ready to, let's, close the gap, build authority, expand citation.
'''


async def batch_synthesize(
    brand_name: str,
    profile: ReconstructedProfile,
    analyses_payload: list[dict],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    One browser call for narrative fields only.
    On parse failure: return empty narratives + synthesisError=True (no fake SOV).
    """
    question = build_synthesize_prompt(
        brand_name=brand_name,
        profile=profile,
        analyses=analyses_payload,
        metrics=metrics,
    )
    response = await query_chatgpt(
        ChatGPTQueryRequest(
            brandName=brand_name,
            question=question,
            returnType=ReturnType.html,
        )
    )
    data = extract_json_from_html(response.content)
    if not isinstance(data, dict):
        return {
            "executiveSummary": "",
            "industry": profile.industry,
            "productLine": profile.productLine,
            "sprint": SprintSection(),
            "synthesisError": True,
        }

    executive_summary = str(data.get("executiveSummary") or "").strip()
    industry = str(data.get("industry") or profile.industry).strip() or profile.industry
    product_line = (
        str(data.get("productLine") or profile.productLine).strip()
        or profile.productLine
    )

    sprint_raw = data.get("sprint") if isinstance(data.get("sprint"), dict) else {}
    try:
        sprint = SprintSection.model_validate(sprint_raw or {})
    except Exception:
        sprint = SprintSection()

    synthesis_error = not bool(executive_summary) and not bool(sprint.headline)
    return {
        "executiveSummary": executive_summary,
        "industry": industry,
        "productLine": product_line,
        "sprint": sprint,
        "synthesisError": synthesis_error,
    }


def build_model_coverage(visibility_score: float, cited_display: str) -> list[ModelCoverageItem]:
    return [
        ModelCoverageItem(
            model="ChatGPT",
            score=visibility_score,
            cited=cited_display,
            notInSnapshot=False,
        ),
        ModelCoverageItem(
            model="Perplexity", score=0, cited="—", notInSnapshot=True
        ),
        ModelCoverageItem(
            model="Google AI Overview", score=0, cited="—", notInSnapshot=True
        ),
        ModelCoverageItem(
            model="Gemini", score=0, cited="—", notInSnapshot=True
        ),
        ModelCoverageItem(model="Claude", score=0, cited="—", notInSnapshot=True),
        ModelCoverageItem(
            model="Google AI Mode", score=0, cited="—", notInSnapshot=True
        ),
    ]


async def synthesize_report(
    brand_name: str,
    questions: GetQuestionsResponse,
    crisis_rows: list[dict],
    prompt_rows: list[dict],
    crisis_analyses: list[AnswerAnalysis],
    prompt_analyses: list[AnswerAnalysis],
) -> VisibilityReport:
    profile = questions.reconstructedProfile
    metrics = compute_score_and_sov(brand_name, crisis_analyses, prompt_analyses)

    analysis_payload = [
        {
            "id": row.get("id", ""),
            "kind": "crisis",
            "query": row.get("prompt", ""),
            "brandCited": row.get("status") in ("present", "nuanced"),
            "status": row.get("status", ""),
            "statusLabel": row.get("statusLabel", ""),
            "citedInstead": row.get("citedInstead", []),
            "excerpt": row.get("excerpt", ""),
            "title": row.get("title", ""),
            "outcome": row.get("outcome", ""),
            "tag": row.get("tag", ""),
            "dealLoss": row.get("dealLoss", ""),
        }
        for row in crisis_rows
    ] + [
        {
            "id": row.get("id", ""),
            "kind": "discovery",
            "query": row.get("prompt", ""),
            "brandCited": row.get("status") in ("present", "nuanced"),
            "status": row.get("status", ""),
            "statusLabel": row.get("statusLabel", ""),
            "citedInstead": row.get("citedInstead", []),
            "excerpt": row.get("excerpt", ""),
            "title": row.get("title", ""),
            "outcome": row.get("outcome", ""),
            "tag": row.get("tag", ""),
            "dealLoss": row.get("dealLoss", ""),
        }
        for row in prompt_rows
    ]

    narratives = await batch_synthesize(
        brand_name=brand_name,
        profile=profile,
        analyses_payload=analysis_payload,
        metrics=metrics,
    )

    cited_display = f"{metrics['citedCount']}/{metrics['totalPrompts']}"
    return VisibilityReport(
        snapshot=SnapshotSection(
            brandName=brand_name,
            website=profile.inferredDomain,
            industry=narratives["industry"],
            productLine=narratives["productLine"],
            snapshotDate=default_snapshot_date(),
            visibilityScore=metrics["visibilityScore"],
            visibilityLabel=metrics["visibilityLabel"],
            citedCount=metrics["citedCount"],
            totalPrompts=metrics["totalPrompts"],
            executiveSummary=narratives["executiveSummary"],
            brandCrisisHeadline=questions.brandCrisisHeadline,
            brandCrisisDek=questions.brandCrisisDek,
            preparedFor="",
            role="",
        ),
        modelCoverage=build_model_coverage(
            metrics["visibilityScore"], cited_display
        ),
        competitiveShareOfVoice=metrics["competitiveShareOfVoice"],
        brandCrisis=[BrandCrisisReportItem.model_validate(r) for r in crisis_rows],
        prompts=[PromptAuditItem.model_validate(r) for r in prompt_rows],
        sprint=narratives["sprint"],
        synthesisError=bool(narratives["synthesisError"]),
    )
