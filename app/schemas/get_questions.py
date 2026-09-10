from pydantic import BaseModel, Field


class GetQuestionsRequest(BaseModel):
    brandName: str = Field(..., description="The name of the brand to get questions for")


class ReconstructedProfile(BaseModel):
    brandName: str = Field(..., description="The brand name")
    inferredDomain: str = Field(default="", description="The inferred primary domain")
    industry: str = Field(
        default="",
        description="Short eyebrow-length industry label (e.g. UPSC coaching)",
    )
    productLine: str = Field(
        default="",
        description="Short product/service shelf string for the cover eyebrow",
    )
    targetIcp: str = Field(default="", description="Target buyer persona / ICP")
    deducedUsps: list[str] = Field(default_factory=list, description="Deduced USPs")
    primaryCompetitors: list[str] = Field(
        default_factory=list, description="Primary competitors"
    )
    headquartersOrHub: str = Field(
        default="", description="Headquarters or densest customer cluster"
    )


class BrandCrisisItem(BaseModel):
    id: str = Field(..., description="Unique ID for the crisis exhibit")
    query: str = Field(
        ...,
        description=(
            "Crisis prompt: crisis-1 branded trust gate; "
            "crisis-2/3 unbranded shelf absences"
        ),
    )
    archetype: str = Field(..., description="Crisis archetype")
    severity: str = Field(default="critical", description="Severity level")
    tag: str = Field(default="", description="Category/topic tag")
    title: str = Field(default="", description="Short failure title")
    outcome: str = Field(default="", description="Summary of AI failure")
    theDistressAngle: str = Field(
        default="", description="Commercial pain point explaining the distress"
    )


class DiscoveryQueryItem(BaseModel):
    id: str = Field(..., description="Unique ID for the discovery query")
    query: str = Field(..., description="Conversational unbranded prompt")
    intent: str = Field(default="", description="The buyer job being executed")
    archetype: str = Field(..., description="Discovery archetype")
    severity: str = Field(default="critical", description="Severity level")
    tag: str = Field(default="", description="Category/topic tag")
    citedCompetitorsExpected: list[str] = Field(
        default_factory=list, description="Competitors expected to win the citation"
    )
    outcome: str = Field(default="", description="Projected outcome")
    theDistressAngle: str = Field(
        default="", description="Commercial pain point explaining the distress"
    )


class GetQuestionsResponse(BaseModel):
    reconstructedProfile: ReconstructedProfile
    brandCrisisHeadline: str = Field(
        default="", description="Headline for brand crisis exhibits"
    )
    brandCrisisDek: str = Field(
        default="", description="Subhead for brand crisis exhibits"
    )
    brandCrisis: list[BrandCrisisItem] = Field(
        default_factory=list, description="Brand crisis exhibits"
    )
    queriesHeadline: str = Field(
        default="", description="Headline for discovery queries"
    )
    queriesIntro: str = Field(
        default="", description="Introductory text for discovery queries"
    )
    queries: list[DiscoveryQueryItem] = Field(
        default_factory=list, description="Unbranded discovery queries"
    )
