from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Selection, SectionNode
from app.schemas.schemas import TestCaseResponse
from app.services.llm_service import LLMService
from app.services.mongo_service import nosql_store
from app.core.logging import logger

router = APIRouter(prefix="/generations", tags=["llm-generation"])

@router.post("/{selection_id}", response_model=List[TestCaseResponse])
def generate_test_cases_for_selection(selection_id: str, db: Session = Depends(get_db)):
    """
    Triggers LLM QA test case generation for a version-pinned selection of nodes.
    
    Duplicates Submission Policy:
    1. If test cases have already been generated for this selection_id, we check
       if the content of the selected nodes has changed.
    2. If the content hashes match the cached test cases, we return the cached test cases
       to save cost and maintain consistency.
    3. If content hashes differ, we overwrite and regenerate the test cases.
    """
    logger.info(f"Received generation request for selection ID '{selection_id}'")
    
    # 1. Fetch selection from SQLite
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise HTTPException(
            status_code=404,
            detail=f"Selection with ID '{selection_id}' not found."
        )
        
    # Get nodes belonging to this selection
    nodes = selection.nodes
    if not nodes:
        raise HTTPException(
            status_code=400,
            detail=f"Selection '{selection.name}' does not contain any section nodes."
        )
        
    node_ids = [n.id for n in nodes]
    version_number = selection.version.version_number
    
    # 2. Check if we already have test cases in NoSQL
    existing_tcs = nosql_store.get_test_cases({"selection_id": selection_id})
    
    if existing_tcs:
        logger.info(f"Found {len(existing_tcs)} existing test cases for selection ID '{selection_id}'. Verifying content freshness...")
        # Check if the content hashes match.
        # We check each node's current hash in the database vs the hash stored in the test case.
        # In a selection, each test case has a 'traceability' pointing to the source node,
        # and has the 'content_hash' of that node at generation time.
        node_hash_map = {n.id: n.content_hash for n in nodes}
        
        hashes_match = True
        for tc in existing_tcs:
            tc_node_id = tc["traceability"]
            stored_hash = tc["content_hash"]
            
            # If the source node's current hash does not match what was stored, it's stale!
            current_hash = node_hash_map.get(tc_node_id)
            if current_hash != stored_hash:
                hashes_match = False
                logger.info(f"Hash mismatch detected for node ID '{tc_node_id}'. Stored={stored_hash}, Current={current_hash}.")
                break
                
        if hashes_match:
            logger.info("Requirement content is unchanged. Returning cached test cases.")
            
            # Map dict to schema response. Status is NOT STALE because content is unchanged.
            responses = []
            for tc in existing_tcs:
                responses.append(TestCaseResponse(
                    id=tc["id"],
                    title=tc["title"],
                    requirement=tc["requirement"],
                    steps=tc["steps"],
                    expected_result=tc["expected_result"],
                    priority=tc["priority"],
                    risk=tc["risk"],
                    traceability=tc["traceability"],
                    selection_id=tc["selection_id"],
                    version_number=tc["version_number"],
                    node_ids=tc["node_ids"],
                    content_hash=tc["content_hash"],
                    timestamp=tc["timestamp"],
                    stale_status="NOT STALE",
                    staleness_reason="Requirement content matches generation time hash."
                ))
            return responses
            
        logger.info("Requirement content has changed. Deleting cached test cases and regenerating...")
        nosql_store.delete_test_cases_by_selection(selection_id)

    # 3. Trigger LLM to generate fresh test cases
    try:
        generated_tcs = LLMService.generate_test_cases(db, selection_id, node_ids)
    except Exception as e:
        logger.error(f"Failed to generate test cases: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Test case generation failed: {str(e)}"
        )
        
    # Map nodes to quickly fetch content hash
    node_hash_map = {n.id: n.content_hash for n in nodes}
    
    # 4. Save generated test cases in NoSQL
    save_records = []
    responses = []
    for tc in generated_tcs:
        source_node_id = tc.traceability
        source_hash = node_hash_map.get(source_node_id, "")
        
        record = {
            "title": tc.title,
            "requirement": tc.requirement,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "priority": tc.priority,
            "risk": tc.risk,
            "traceability": source_node_id,
            "selection_id": selection_id,
            "version_number": version_number,
            "node_ids": node_ids,
            "content_hash": source_hash
        }
        save_records.append(record)
        
    # Save bulk
    nosql_store.save_test_cases(save_records)
    
    # Fetch them back (to populate IDs and timestamp correctly)
    stored_tcs = nosql_store.get_test_cases({"selection_id": selection_id})
    for tc in stored_tcs:
        responses.append(TestCaseResponse(
            id=tc["id"],
            title=tc["title"],
            requirement=tc["requirement"],
            steps=tc["steps"],
            expected_result=tc["expected_result"],
            priority=tc["priority"],
            risk=tc["risk"],
            traceability=tc["traceability"],
            selection_id=tc["selection_id"],
            version_number=tc["version_number"],
            node_ids=tc["node_ids"],
            content_hash=tc["content_hash"],
            timestamp=tc["timestamp"],
            stale_status="NOT STALE",
            staleness_reason="Newly generated test case."
        ))
        
    return responses
