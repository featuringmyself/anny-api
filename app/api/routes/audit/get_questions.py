import json
import re
from bs4 import BeautifulSoup
from fastapi import APIRouter, status
from app.engine import ChatGPTQueryRequest, query_chatgpt
from app.schemas.chatgpt import ReturnType
from app.schemas.get_questions import (
    DiscoveryQueryItem,
    GetQuestionsRequest,
    GetQuestionsResponse,
    ReconstructedProfile,
)

router = APIRouter(prefix="/get_questions", tags=["get_questions"])


def extract_audit_data_from_html(html: str, brand_name: str = "") -> GetQuestionsResponse:
    soup = BeautifulSoup(html, "html.parser")
    assistant = (
        soup.select_one('[data-message-author-role="assistant"]')
        or soup.select_one('[data-message-role="assistant"]')
        or soup.select_one(".agent-turn")
        or soup
    )

    # Decompose citations and reference anchors
    for tag in assistant.select(
        '[data-testid="webpage-citation-pill"], .contents, [data-content-reference-start], span[data-state]'
    ):
        tag.decompose()

    # Convert <br> tags into newlines
    for br in assistant.find_all("br"):
        br.replace_with("\n")

    text = assistant.get_text()

    # Attempt to extract JSON from assistant response
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        raw_json = match.group(1).strip()
        raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json, flags=re.MULTILINE)
        raw_json = re.sub(r"\s*```$", "", raw_json, flags=re.MULTILINE)
        try:
            data = json.loads(raw_json)

            def clean_strings(obj):
                if isinstance(obj, str):
                    return re.sub(r"\s+", " ", obj).strip()
                elif isinstance(obj, dict):
                    return {k: clean_strings(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_strings(item) for item in obj]
                return obj

            cleaned = clean_strings(data)
            return GetQuestionsResponse.model_validate(cleaned)
        except Exception:
            pass

    # Fallback if response is structured as list items
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


@router.post(
    "/", 
    response_model=GetQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get visibility distress audit questions and reconstructed profile",
    description="Reverse-engineers the brand profile and generates visibility distress prompts across brand crisis and discovery archetypes.",
)
async def get_questions(request: GetQuestionsRequest) -> GetQuestionsResponse:
    question = f'''You are the Chief AI Search Strategist at Anny. Your job is to conduct AI Visibility Audits that sell high-ticket 90-day AI citation sprints to founders, CEOs, and CMOs.

You will be given ONLY the brand name: "{request.brandName}".

You must first reverse-engineer the company's identity, ICP, competitors, signature claims, and vulnerabilities from your knowledge base, and then generate a battery of "Visibility Distress Prompts" designed to expose commercial deal loss in frontier AI engines (ChatGPT, Perplexity, Google AI Overviews, Claude).

---

### STEP 1: ENTITY REVERSE-ENGINEERING (Internal Deduction)
Before generating prompts, deduce and reconstruct:
1. Primary Domain & Industry: What domain do they operate on? What is their exact market vertical?
2. Core Target ICP: Who signs the check (e.g., enterprise CTOs, PG landlords, salaried retail investors)?
3. Primary Value Proposition & USPs: What is their sharpest homepage claim, pricing wedge, or operational guarantee (e.g., "7-day refunds", "free tier", "autopay on WhatsApp")?
4. Likely Competitors: Top 3–5 incumbents and nimble rivals dominating this space.
5. Home Turf & Hub: Where are they headquartered or where is their densest customer cluster?
6. Vulnerability Surface: 
   - What words phonetically or semantically collide with "{request.brandName}" (e.g., RentOk -> Rentokil; Linkrunner -> NetAlly hardware; Sprentzo -> skincare; Praata -> coliving)?
   - Where are they most prone to skepticism (e.g., refunds, KYC, data security, small track record)?

---

### STEP 2: THE SACRED BRAND-NAMING RULE (The 20 / 80 Split)

You must strictly obey this placement rule:

1. BRANDED PROMPTS (~20% of total — ONLY in Brand Crisis & Direct Diligence):
   - You MUST explicitly include "{request.brandName}" or their inferred domain.
   - Purpose: Prove that even when a warm lead types their EXACT name, AI fails the trust gate, confuses their category, or defends their competitor.

2. UNBRANDED PROMPTS (~80% of total — in Discovery & Revenue Shelves):
   - You MUST STRICTLY FORBID and OMIT "{request.brandName}" and their domain.
   - Purpose: Prove that when a qualified buyer asks AI for the exact solution, USP, or workflow they provide, AI gives 100% of the recommendations to competitors.

---

### STEP 3: THE 8 DISTRESS ARCHETYPES

Generate queries mapped to these 8 commercial distress triggers:

#### PART A: BRAND CRISIS EXHIBITS (2–3 Queries — ALWAYS Branded with "{request.brandName}")
1. Identity Collision & Category Confusion:
   - Form: "is {request.brandName} reliable", "are {request.brandName} products reliable", "alternatives to [inferred-domain]"
   - Angle: AI confuses them with an unrelated commodity, hardware, pest control, or warns of scams.
2. Bottom-of-Funnel Trust Gate Failure:
   - Form: "is [inferred-domain] legit", "should I buy/order from [inferred-domain]", "does {request.brandName} refund [key claim] timely?", "{request.brandName} review"
   - Angle: AI advises caution, says there's no independent proof, or tells the prospect to use Cash on Delivery.
3. Switcher Defense (Defending the Incumbent):
   - Form: "should I switch from [Top Incumbent] to {request.brandName}"
   - Angle: When a warm lead asks AI for permission to switch, AI tells them: "I wouldn't switch blindly" and defends the incumbent.

#### PART B: DISCOVERY & REVENUE SHELVES (8–10 Queries — STRICTLY Unbranded)
4. Homepage USP & "Own Claim" Theft (Critical Severity):
   - Form: Take their signature capability or tagline and turn it into a buyer query without naming them (e.g., "MMP with transparent per-install pricing", "app that invests in gold every time I spend on UPI").
   - Angle: The exact differentiator the founder built their company on is awarded to their direct rival.
5. Flagship Customer / Proof Erasure (Critical Severity):
   - Form: "what [software/agency] does [known client in industry] use", "who provides [service] for [notable company]"
   - Angle: AI checks 4–5 competitors and claims no provider exists, erasing their social proof.
6. Competitor Conquest & Switchers (High Severity):
   - Form: "[Incumbent] alternatives for [ICP]", "I want a tool like [Incumbent] but not [Incumbent]"
   - Angle: Buyers actively abandoning the incumbent are funneled to secondary rivals, completely skipping this brand.
7. Home-Turf & Micro-Market Humiliation (High Severity):
   - Form: "best [service] near [inferred neighborhood/tech park]", "[service] in [inferred HQ city]"
   - Angle: Competitors down the street win the shortlist while this brand is invisible in their own backyard.
8. High-Intent Commercial RFP & Deal Size (High Severity):
   - Form: Prompts with hard constraints: seat count, team size, budget, or timeline (e.g., "[category] for 200 seats in [city]", "[category] under 25k budget").
   - Angle: High-ARR deals with budget in hand are being divvied up between competitors in AI answers right now.

---

### PHRASING CONSTRAINTS
- Conversational Human Phrasing: Write how humans naturally query chatbots (e.g., "where should I stay for work in...", "which company gets...", "I want an app like X but..."). Never output robotic keyword search syntax.
- Real Commercial Pain: Every single prompt must represent a lost demo, an aborted checkout, a lost deposit, or customer churn.

---

### OUTPUT FORMAT
Output strict JSON matching the following structure:

```json
{{
  "reconstructedProfile": {{
    "brandName": "{request.brandName}",
    "inferredDomain": "example.com",
    "industry": "Specific industry description",
    "targetIcp": "Target buyer persona",
    "deducedUsps": ["USP 1", "USP 2"],
    "primaryCompetitors": ["Competitor A", "Competitor B", "Competitor C"],
    "headquartersOrHub": "City / Region"
  }},
  "brandCrisisHeadline": "Punchy headline summarizing the trust or identity crisis",
  "brandCrisisDek": "One-line subhead explaining the commercial stakes",
  "brandCrisis": [
    {{
      "id": "crisis-1",
      "query": "Exact prompt with {request.brandName} or inferred domain",
      "archetype": "Identity Collision | Trust Gate Failure | Switcher Defense",
      "severity": "critical",
      "tag": "Brand collision | Trust failure | Switch verdict",
      "title": "Short title describing the failure",
      "outcome": "One-line summary of how AI fails the brand",
      "theDistressAngle": "Why this specific response terrifies the founder and kills deals in flight."
    }}
  ],
  "queriesHeadline": "Prompt audit · [N] queries",
  "queriesIntro": "Intro explaining that while brand-trust prompts fail above, these buying queries route deal flow to competitors.",
  "queries": [
    {{
      "id": "q1",
      "query": "Natural conversational prompt (STRICTLY NO BRAND NAME)",
      "intent": "The buyer job being executed",
      "archetype": "Own Claim Theft | Customer Proof Erasure | Competitor Conquest | Home Turf | Commercial RFP",
      "severity": "critical | high | standard",
      "tag": "Own claim | Home turf | Conquest | RFP | Category",
      "citedCompetitorsExpected": ["Competitor A", "Competitor B"],
      "outcome": "Projected outcome (e.g., '{request.brandName} missing · Competitors fill the table')",
      "theDistressAngle": "The commercial pain point: why the founder will lean forward in distress upon seeing this."
    }}
  ]
}}
'''
    response = await query_chatgpt(ChatGPTQueryRequest(brandName=request.brandName, question=question, returnType=ReturnType.html))
    return extract_audit_data_from_html(response.content, request.brandName)

