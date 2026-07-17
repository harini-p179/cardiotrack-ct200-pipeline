from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

# --- Node Schemas ---

class NodeBriefResponse(BaseModel):
    id: str
    logical_node_id: str
    heading: Optional[str] = None
    title: str
    level: int
    parent_id: Optional[str] = None
    status: str
    content_hash: str

    model_config = ConfigDict(from_attributes=True)

class NodeResponse(BaseModel):
    id: str
    logical_node_id: str
    heading: Optional[str] = None
    title: str
    level: int
    body: Optional[str] = None
    parent_id: Optional[str] = None
    content_hash: str
    status: str
    created_at: datetime
    updated_at: datetime
    children: List['NodeResponse'] = []

    model_config = ConfigDict(from_attributes=True)

class NodeDetailResponse(BaseModel):
    id: str
    logical_node_id: str
    heading: Optional[str] = None
    title: str
    level: int
    body: Optional[str] = None
    parent_id: Optional[str] = None
    content_hash: str
    status: str
    full_text_reconstruction: str
    children: List[NodeBriefResponse] = []

    model_config = ConfigDict(from_attributes=True)

# Support recursive schemas in Pydantic v2
NodeResponse.model_rebuild()


# --- Version Comparison Schemas ---

class CompareResponse(BaseModel):
    logical_node_id: str
    title: str
    heading: Optional[str] = None
    status: str  # UNCHANGED, MODIFIED, NEW, DELETED
    diff_summary: Optional[str] = None
    v1_body: Optional[str] = None
    v2_body: Optional[str] = None


# --- Selection Schemas ---

class SelectionCreate(BaseModel):
    name: str
    node_ids: List[str]
    version_id: str

class SelectionResponse(BaseModel):
    id: str
    name: str
    version_id: str
    created_at: datetime
    nodes: List[NodeBriefResponse]

    model_config = ConfigDict(from_attributes=True)


# --- LLM Test Case Schemas ---

class TestCaseCreate(BaseModel):
    title: str = Field(..., description="Short descriptive title of the test case")
    requirement: str = Field(..., description="The source requirement or text description")
    steps: List[str] = Field(..., description="Actionable step-by-step instructions")
    expected_result: str = Field(..., description="Expected output/behavior")
    priority: str = Field(..., description="Priority: High, Medium, or Low")
    risk: str = Field(..., description="Potential risks or failure modes")
    traceability: str = Field(..., description="The ID of the section node this test case maps to")

class LLMGenerationResponse(BaseModel):
    test_cases: List[TestCaseCreate]


# --- NoSQL / Stale Test Case Retrieval Schemas ---

class TestCaseResponse(BaseModel):
    id: str
    title: str
    requirement: str
    steps: List[str]
    expected_result: str
    priority: str
    risk: str
    traceability: str  # SectionNode ID at creation time
    selection_id: str
    version_number: str
    node_ids: List[str]  # All node IDs in the selection
    content_hash: str    # Node content hash at creation time
    timestamp: datetime
    stale_status: str    # STALE, NOT STALE, UNKNOWN
    staleness_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VersionResponse(BaseModel):
    id: str
    document_id: str
    version_number: str
    created_at: datetime
    content_hash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

