import re

from app.engine import ChatGPTQueryRequest, query_chatgpt
from app.schemas.chatgpt import ReturnType
from app.schemas.get_questions import (
    DiscoveryQueryItem,
    GetQuestionsRequest,
    GetQuestionsResponse,
    ReconstructedProfile,
)
from app.services.html_extract import (
    assistant_node,
    extract_json_from_html,
    strip_citations,
)


def build_get_questions_prompt(brand_name: str) -> str:
    return f'''You are the Chief AI Search Strategist at Anny. Your job is to conduct AI Visibility Audits that prove lost buyer demand with cold exhibits — not marketing pitches.

You will be given ONLY the brand name: "{brand_name}".

You must first reverse-engineer the company's identity, ICP, competitors, signature claims, and vulnerabilities from your knowledge base, and then generate a battery of short "Visibility Distress Prompts" — the kind of queries real buyers type into ChatGPT.

---

### STEP 1: ENTITY REVERSE-ENGINEERING (Internal Deduction)
Before generating prompts, deduce and reconstruct:
1. Primary Domain & Industry: What domain do they operate on? What is their exact market vertical?
2. Core Target ICP: Who signs the check?
3. Primary Value Proposition & USPs / product shelf: What course, product, or service line do they sell? List concrete SKUs / enrolment drivers.
4. Likely Competitors: Top 3–5 incumbents and nimble rivals dominating this space.
5. Home Turf & Hub: Where are they headquartered or where is their densest customer cluster?
6. Vulnerability Surface:
   - What words phonetically or semantically collide with "{brand_name}"?
   - Where are they most prone to skepticism (refunds, KYC, track record)?

---

### STEP 2: BRAND-NAMING RULES

1. CRISIS slot crisis-1 ONLY: MUST include "{brand_name}" (branded trust gate).
2. CRISIS slots crisis-2 and crisis-3: MUST STRICTLY OMIT "{brand_name}" and their domain (unbranded shelf absences).
3. DISCOVERY (all queries): MUST STRICTLY OMIT "{brand_name}" and their domain.

BANNED as crisis fillers (never generate these shapes):
- "best X like {brand_name}"
- "alternatives to {brand_name}"
- multi-product diligence / switcher essays that soft-ask for the brand
- any soft branded shortlist that ChatGPT will trivially name

---

### STEP 3: SHORT BUYER PROMPTS (Edukemy length — CRITICAL)

Every query must be a **short conversational buyer prompt** — roughly Edukemy exhibit length.
Good examples: "{brand_name} review", "best online GS Foundation for UPSC 2027", "best IAS coaching in Old Rajinder Nagar".
BAD: long multi-clause diligence essays, RFP paragraphs, stacked constraints, or keyword-stuffed SEO strings.
Reject any query that reads like a consultant brief. Prefer 4–12 words when possible; never exceed ~20 words.

#### PART A: BRAND CRISIS EXHIBITS (exactly 3 — trust + category erasure)

| Slot | Type | Shape |
|------|------|-------|
| crisis-1 | Branded trust gate ONLY | "{{brand_name}} review" / "is {{brand_name}} legit" |
| crisis-2 | UNBRANDED flagship shelf | e.g. "best online GS Foundation for UPSC 2027" |
| crisis-3 | UNBRANDED home-turf or second flagship | e.g. "best IAS coaching in Old Rajinder Nagar" |

crisis-2 and crisis-3 prove category erasure when the brand is absent from the shortlist. Prefer shelves incumbents are known to own.

#### PART B: DISCOVERY & REVENUE SHELVES (8–10 Queries — STRICTLY Unbranded)
Map 1:1 to productLine SKUs / enrolment drivers (mentorship, essay, test series, etc.).
Short unbranded buy-intent only. Prefer prompts where incumbents own the shelf:
- Own-claim / USP theft
- Customer / proof erasure
- Competitor conquest & switchers
- Home-turf micro-market
- High-intent commercial shortlist (budget/seats OK only if still short)

---

### PHRASING CONSTRAINTS
- Conversational Human Phrasing: how humans naturally query chatbots.
- Real Commercial Pain: every prompt must represent diverted enrolment / demo / shortlist demand.
- NO long multi-clause diligence questions.
- NO salesy or pitch language in headlines, deks, or distress angles — state who gets the shortlist today and who does not.

---

### OUTPUT FORMAT
Output strict JSON matching the following structure:

```json
{{
  "reconstructedProfile": {{
    "brandName": "{brand_name}",
    "inferredDomain": "example.com",
    "industry": "Short eyebrow label (e.g. UPSC coaching)",
    "productLine": "Short shelf string (e.g. Integrated mentorship · GS · Optional)",
    "targetIcp": "Target buyer persona",
    "deducedUsps": ["USP 1", "USP 2"],
    "primaryCompetitors": ["Competitor A", "Competitor B", "Competitor C"],
    "headquartersOrHub": "City / Region"
  }},
  "brandCrisisHeadline": "Cold headline of trust failure or category erasure (no pitch)",
  "brandCrisisDek": "One factual line: who gets the shortlist / enrolment today; who does not",
  "brandCrisis": [
    {{
      "id": "crisis-1",
      "query": "{brand_name} review",
      "archetype": "Trust Gate Failure",
      "severity": "critical",
      "tag": "Trust failure",
      "title": "Short title describing the failure",
      "outcome": "One-line summary of how AI fails the brand",
      "theDistressAngle": "Factual commercial stake — who gets trust / shortlist today."
    }},
    {{
      "id": "crisis-2",
      "query": "Unbranded flagship shelf prompt (NO {brand_name})",
      "archetype": "Category Erasure",
      "severity": "critical",
      "tag": "Flagship shelf",
      "title": "Short title for the absence",
      "outcome": "Projected: {brand_name} missing · incumbents fill the shortlist",
      "theDistressAngle": "Flagship enrolment shortlist never sees {brand_name}."
    }},
    {{
      "id": "crisis-3",
      "query": "Unbranded home-turf or second flagship prompt (NO {brand_name})",
      "archetype": "Home Turf Erasure",
      "severity": "critical",
      "tag": "Home turf",
      "title": "Short title for the absence",
      "outcome": "Projected: {brand_name} missing · local/category rivals named",
      "theDistressAngle": "Home-turf buy intent routes to competitors."
    }}
  ],
  "queriesHeadline": "Prompt audit · [N] queries",
  "queriesIntro": "Buy-intent queries that route deal flow to competitors.",
  "queries": [
    {{
      "id": "q1",
      "query": "Short unbranded buyer prompt (NO BRAND NAME)",
      "intent": "The buyer job being executed",
      "archetype": "Own Claim Theft | Customer Proof Erasure | Competitor Conquest | Home Turf | Commercial RFP",
      "severity": "critical | high | standard",
      "tag": "Own claim | Home turf | Conquest | RFP | Category",
      "citedCompetitorsExpected": ["Competitor A", "Competitor B"],
      "outcome": "Projected outcome (e.g., '{brand_name} missing · Competitors fill the table')",
      "theDistressAngle": "Factual commercial stake — diverted enrolment/demo demand."
    }}
  ]
}}
```
'''


def parse_get_questions_html(html: str, brand_name: str = "") -> GetQuestionsResponse:
    data = extract_json_from_html(html)
    if isinstance(data, dict):
        try:
            return GetQuestionsResponse.model_validate(data)
        except Exception:
            pass

    assistant = assistant_node(html)
    strip_citations(assistant)
    lis = assistant.select("[data-assistant-markdown] li") or assistant.select("ol li")
    fallback_queries: list[DiscoveryQueryItem] = []
    for i, li in enumerate(lis, 1):
        clean_text = re.sub(r"\s+", " ", li.get_text(separator=" ", strip=True)).strip()
        clean_text = re.sub(r"^\d+[\.\)]\s*", "", clean_text)
        if clean_text:
            fallback_queries.append(
                DiscoveryQueryItem(
                    id=f"q{i}",
                    query=clean_text,
                    archetype="General",
                    severity="standard",
                )
            )

    return GetQuestionsResponse(
        reconstructedProfile=ReconstructedProfile(brandName=brand_name),
        queries=fallback_queries,
    )


async def fetch_questions(request: GetQuestionsRequest) -> GetQuestionsResponse:
    question = build_get_questions_prompt(request.brandName)
    response = await query_chatgpt(
        ChatGPTQueryRequest(
            brandName=request.brandName,
            question=question,
            returnType=ReturnType.html,
        )
    )
    return parse_get_questions_html(response.content, request.brandName)
