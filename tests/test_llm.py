import pytest
from app.services.llm_service import LLMService
from app.models.models import SectionNode
from app.schemas.schemas import TestCaseCreate, LLMGenerationResponse

def test_mock_test_case_generation_cuff():
    node = SectionNode(
        id="node-uuid-1",
        version_id="version-uuid",
        logical_node_id="device_operation/cuff_inflation",
        heading="3.2 Cuff Inflation Sequence",
        title="Cuff Inflation Sequence",
        level=2,
        body="Initial inflation target is 180 mmHg. Incremental steps of 30 mmHg. Maximum target is 299 mmHg.",
        content_hash="mock_hash_1"
    )
    
    test_cases = LLMService._generate_mock_test_cases([node])
    assert len(test_cases) > 0
    for tc in test_cases:
        assert isinstance(tc, TestCaseCreate)
        assert tc.traceability == "node-uuid-1"
        assert tc.priority in ["High", "Medium", "Low"]
        assert len(tc.steps) > 0
        assert tc.expected_result != ""

def test_mock_test_case_generation_overpressure():
    node = SectionNode(
        id="node-uuid-2",
        version_id="version-uuid",
        logical_node_id="alarms_safety/overpressure_protection",
        heading="4.1 Overpressure Protection",
        title="Overpressure Protection",
        level=2,
        body="Emergency relief system activates if pressure exceeds 300 mmHg.",
        content_hash="mock_hash_2"
    )
    
    test_cases = LLMService._generate_mock_test_cases([node])
    assert len(test_cases) > 0
    assert any("Overpressure" in tc.title or "Emergency" in tc.title for tc in test_cases)

def test_generate_test_cases_fallback(db_session):
    # Setup test nodes in database
    v_id = "v-1-id"
    node1 = SectionNode(
        id="node-1",
        version_id=v_id,
        logical_node_id="device_overview/intended_use",
        heading="1.1 Intended Use",
        title="Intended Use",
        level=2,
        body="Monitor is for home use.",
        content_hash="hash1"
    )
    db_session.add(node1)
    db_session.commit()
    
    # Run service (without GEMINI_API_KEY, should fall back to mock)
    test_cases = LLMService.generate_test_cases(
        db=db_session,
        selection_id="selection-id-xyz",
        node_ids=["node-1"]
    )
    
    assert len(test_cases) > 0
    assert test_cases[0].traceability == "node-1"

def test_validation_response_schema():
    valid_payload = {
        "test_cases": [
            {
                "title": "Test overpressure limit",
                "requirement": "Device must deflated if pressure exceeds 299 mmHg.",
                "steps": ["Apply pressure of 300 mmHg", "Wait 2s"],
                "expected_result": "Cuff deflates completely",
                "priority": "High",
                "risk": "Ischemia risk",
                "traceability": "node-uuid-abc"
            }
        ]
    }
    
    validated = LLMGenerationResponse.model_validate(valid_payload)
    assert len(validated.test_cases) == 1
    assert validated.test_cases[0].title == "Test overpressure limit"
    assert validated.test_cases[0].priority == "High"
