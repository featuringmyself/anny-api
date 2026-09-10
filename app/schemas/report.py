from pydantic import BaseModel, Field

from app.schemas.get_questions import GetQuestionsRequest


class ReportRequest(GetQuestionsRequest):
    """Brand-only input for the visibility report orchestrator."""


class SnapshotSection(BaseModel):
    brandName: str = Field(..., description="Brand under audit")
    website: str = Field(default="", description="Inferred or known website")
    industry: str = Field(
        default="", description="Short eyebrow-length industry label"
    )
    productLine: str = Field(
        default="", description="Short product/service shelf for the cover eyebrow"
    )
    snapshotDate: str = Field(
        default="", description="Human snapshot date, e.g. September 2026"
    )
    visibilityScore: float = Field(
        default=0,
        description=(
            "0–100 discovery-only visibility score: share of discovery prompts "
            "where the brand appears (present or nuanced). Brand-crisis rows "
            "are exhibits and are excluded from numerator/denominator."
        ),
    )
    visibilityLabel: str = Field(
        default="Critical",
        description="0–19 Critical, 20–39 Weak, 40–69 Moderate, 70–100 Strong",
    )
    citedCount: int = Field(
        default=0, description="Discovery prompts where the brand was cited"
    )
    totalPrompts: int = Field(
        default=0, description="Total discovery prompts (crisis excluded)"
    )
    executiveSummary: str = Field(default="", description="Report executive summary")
    brandCrisisHeadline: str = Field(
        default="",
        description="Cold headline of trust failure or category erasure",
    )
    brandCrisisDek: str = Field(
        default="",
        description="One factual line: who gets the shortlist today; who does not",
    )
    preparedFor: str = Field(default="", description="Recipient name (empty in v1)")
    role: str = Field(default="", description="Recipient role (empty in v1)")


class ModelCoverageItem(BaseModel):
    model: str = Field(..., description="AI engine name")
    score: float = Field(default=0, description="Visibility score for this model")
    cited: str = Field(default="0/0", description="Cited count display, e.g. 0/10")
    notInSnapshot: bool = Field(
        default=False,
        description="True when this model was not included in the snapshot",
    )


class ShareOfVoiceItem(BaseModel):
    name: str = Field(..., description="Brand or competitor name")
    share: float = Field(..., description="Share of voice percentage 0–100")
    isYou: bool = Field(
        default=False, description="True when this row is the audited brand"
    )


class BrandCrisisReportItem(BaseModel):
    id: str = Field(default="", description="Crisis exhibit id")
    prompt: str = Field(
        ...,
        description="Crisis prompt (crisis-1 branded; crisis-2/3 unbranded shelves)",
    )
    status: str = Field(
        ..., description="present | absent | nuanced | error"
    )
    statusLabel: str = Field(
        default="",
        description="Exhibit status line, e.g. Absent · Vision Lakshya named",
    )
    screenshotPath: str = Field(default="", description="PNG evidence path")
    excerpt: str = Field(
        default="",
        description="Compressed answer facts (names, scores, shortlists) — not opinion",
    )
    title: str = Field(default="", description="Short title")
    outcome: str = Field(default="", description="One-line outcome")
    tag: str = Field(default="", description="Topic tag")
    citedInstead: list[str] = Field(default_factory=list)
    dealLoss: str = Field(
        default="",
        description="Factual commercial stake: who gets the shortlist today",
    )


class PromptAuditItem(BaseModel):
    id: str = Field(default="", description="Discovery prompt id")
    prompt: str = Field(..., description="Unbranded discovery prompt")
    status: str = Field(
        ..., description="present | absent | nuanced | error"
    )
    statusLabel: str = Field(
        default="",
        description="Exhibit status line, e.g. Absent · Vision Lakshya named",
    )
    citedInstead: list[str] = Field(default_factory=list)
    screenshotPath: str = Field(default="", description="PNG evidence path")
    excerpt: str = Field(
        default="",
        description="Compressed answer facts (names, scores, shortlists) — not opinion",
    )
    title: str = Field(default="", description="Short title")
    outcome: str = Field(default="", description="One-line outcome")
    tag: str = Field(default="", description="Topic tag")
    archetype: str = Field(default="", description="Distress archetype")
    severity: str = Field(default="", description="Severity level")
    dealLoss: str = Field(
        default="",
        description="Factual commercial stake: who gets the shortlist today",
    )


class SprintSection(BaseModel):
    headline: str = Field(default="", description="90-day sprint headline")
    outcomes: list[str] = Field(
        default_factory=list, description="Sprint outcome bullets"
    )


class VisibilityReport(BaseModel):
    snapshot: SnapshotSection
    modelCoverage: list[ModelCoverageItem] = Field(default_factory=list)
    competitiveShareOfVoice: list[ShareOfVoiceItem] = Field(default_factory=list)
    brandCrisis: list[BrandCrisisReportItem] = Field(default_factory=list)
    prompts: list[PromptAuditItem] = Field(default_factory=list)
    sprint: SprintSection = Field(default_factory=SprintSection)
    synthesisError: bool = Field(
        default=False,
        description="True when narrative synthesis failed; metrics/rows still grounded",
    )
