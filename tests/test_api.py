import pytest
from app.models.models import Document, Version, SectionNode, Selection
from app.services.mongo_service import nosql_store

@pytest.fixture(autouse=True)
def clean_nosql():
    """Ensure the NoSQL JSON/MongoDB store is cleared before each test."""
    nosql_store.delete_test_cases_by_selection("*")
    yield
    nosql_store.delete_test_cases_by_selection("*")

def seed_test_data(db):
    """Helper to seed mock data in SQLite."""
    doc = Document(id="doc-1", name="CT-200 Technical Manual")
    db.add(doc)
    
    # Version 1.0
    v1 = Version(id="v1-id", document_id="doc-1", version_number="1.0")
    db.add(v1)
    
    # Section Nodes for V1
    n1_v1 = SectionNode(
        id="n1-v1",
        version_id="v1-id",
        logical_node_id="device_overview",
        heading="1 Device Overview",
        title="Device Overview",
        level=1,
        body="Overview content.",
        parent_id=None,
        content_hash="hash-1",
        status="NEW"
    )
    n2_v1 = SectionNode(
        id="n2-v1",
        version_id="v1-id",
        logical_node_id="device_overview/intended_use",
        heading="1.1 Intended Use",
        title="Intended Use",
        level=2,
        body="Old requirement body.",
        parent_id="n1-v1",
        content_hash="hash-2",
        status="NEW"
    )
    db.add(n1_v1)
    db.add(n2_v1)
    
    # Version 2.0
    v2 = Version(id="v2-id", document_id="doc-1", version_number="2.0")
    db.add(v2)
    
    # Section Nodes for V2 (n2-v2 is modified, parent n1-v2 is unchanged)
    n1_v2 = SectionNode(
        id="n1-v2",
        version_id="v2-id",
        logical_node_id="device_overview",
        heading="1 Device Overview",
        title="Device Overview",
        level=1,
        body="Overview content.",
        parent_id=None,
        content_hash="hash-1",
        status="UNCHANGED"
    )
    n2_v2 = SectionNode(
        id="n2-v2",
        version_id="v2-id",
        logical_node_id="device_overview/intended_use",
        heading="1.1 Intended Use",
        title="Intended Use",
        level=2,
        body="New requirement body changed.",
        parent_id="n1-v2",
        content_hash="hash-2-modified",
        status="MODIFIED"
    )
    db.add(n1_v2)
    db.add(n2_v2)
    
    db.commit()
    return doc, v1, v2

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_list_top_level_sections(client, db_session):
    seed_test_data(db_session)
    
    # Defaults to latest (V2.0)
    response = client.get("/api/nodes")
    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) == 1
    assert nodes[0]["id"] == "n1-v2"
    assert nodes[0]["heading"] == "1 Device Overview"
    
    # Explicitly query V1.0
    response = client.get("/api/nodes?version_num=1.0")
    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) == 1
    assert nodes[0]["id"] == "n1-v1"

def test_search_nodes(client, db_session):
    seed_test_data(db_session)
    
    # Search for "requirement" in latest (V2.0)
    response = client.get("/api/nodes/search?q=requirement")
    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) == 1
    assert nodes[0]["id"] == "n2-v2"
    
    # Search for "Old" in V1.0
    response = client.get("/api/nodes/search?q=Old&version_num=1.0")
    assert response.status_code == 200
    nodes = response.json()
    assert len(nodes) == 1
    assert nodes[0]["id"] == "n2-v1"

def test_get_node_by_id(client, db_session):
    seed_test_data(db_session)
    
    response = client.get("/api/nodes/n1-v2")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "n1-v2"
    assert len(data["children"]) == 1
    assert data["children"][0]["id"] == "n2-v2"
    # Verify full text reconstruction contains parent heading + parent body + child heading + child body
    assert "1 Device Overview" in data["full_text_reconstruction"]
    assert "1.1 Intended Use" in data["full_text_reconstruction"]

def test_compare_node_across_versions(client, db_session):
    seed_test_data(db_session)
    
    # Compare modified node in V2
    response = client.get("/api/nodes/n2-v2/compare")
    assert response.status_code == 200
    compare_data = response.json()
    assert compare_data["logical_node_id"] == "device_overview/intended_use"
    assert compare_data["status"] == "MODIFIED"
    assert "-Old requirement body." in compare_data["diff_summary"]
    assert "+New requirement body changed." in compare_data["diff_summary"]

def test_create_and_get_selection(client, db_session):
    seed_test_data(db_session)
    
    # Create selection in V1
    payload = {
        "name": "Safety Selection",
        "version_id": "v1-id",
        "node_ids": ["n2-v1"]
    }
    response = client.post("/api/selections", json=payload)
    assert response.status_code == 200
    selection = response.json()
    assert selection["name"] == "Safety Selection"
    assert selection["version_id"] == "v1-id"
    assert len(selection["nodes"]) == 1
    assert selection["nodes"][0]["id"] == "n2-v1"
    
    # Retrieve it back
    selection_id = selection["id"]
    response = client.get(f"/api/selections/{selection_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Safety Selection"

def test_generate_test_cases_caching(client, db_session):
    seed_test_data(db_session)
    
    # Create selection in V2
    payload = {
        "name": "Operation Selection",
        "version_id": "v2-id",
        "node_ids": ["n2-v2"]
    }
    sel_res = client.post("/api/selections", json=payload)
    selection_id = sel_res.json()["id"]
    
    # Generate test cases (1st time: triggers generation)
    gen_res = client.post(f"/api/generations/{selection_id}")
    assert gen_res.status_code == 200
    tcs = gen_res.json()
    assert len(tcs) > 0
    assert tcs[0]["staleness_reason"] == "Newly generated test case."
    assert tcs[0]["stale_status"] == "NOT STALE"
    
    # Generate test cases (2nd time: should hit cache since content unchanged)
    cache_res = client.post(f"/api/generations/{selection_id}")
    assert cache_res.status_code == 200
    cached_tcs = cache_res.json()
    assert len(cached_tcs) == len(tcs)
    assert cached_tcs[0]["staleness_reason"] == "Requirement content matches generation time hash."

def test_retrieval_and_staleness_detection(client, db_session):
    seed_test_data(db_session)
    
    # 1. Create selection for node n2-v1 in Version 1.0
    payload = {
        "name": "V1 Selection",
        "version_id": "v1-id",
        "node_ids": ["n2-v1"]
    }
    sel_res = client.post("/api/selections", json=payload)
    selection_id = sel_res.json()["id"]
    
    # 2. Generate test cases when Version 1.0 is the latest version.
    # Note: To simulate this, we generated it referencing n2-v1 which had content_hash "hash-2".
    gen_res = client.post(f"/api/generations/{selection_id}")
    assert gen_res.status_code == 200
    
    # 3. Retrieve test cases. Because Version 2.0 is now the latest version in the DB (since it has
    # been added in seed_test_data), and the counterpart n2-v2 has content_hash "hash-2-modified",
    # the stale traceability check should flag this as STALE!
    ret_res = client.get(f"/api/retrieval?selection_id={selection_id}")
    assert ret_res.status_code == 200
    ret_tcs = ret_res.json()
    assert len(ret_tcs) > 0
    assert ret_tcs[0]["stale_status"] == "STALE"
    assert "MODIFIED in version 2.0" in ret_tcs[0]["staleness_reason"]

def test_selection_not_found(client, db_session):
    # Retrieve non-existent selection
    response = client.get("/api/selections/non-existent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Selection with ID 'non-existent-uuid' not found."

def test_generate_non_existent_selection(client, db_session):
    # Trigger generation on non-existent selection
    response = client.post("/api/generations/non-existent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Selection with ID 'non-existent-uuid' not found."

