from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Version, SectionNode
from app.schemas.schemas import TestCaseResponse
from app.services.mongo_service import nosql_store
from app.core.logging import logger

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

def _determine_staleness(
    db: Session,
    stored_hash: str,
    source_node_id: str,
    latest_version: Version
) -> tuple[str, str]:
    """
    Compares the test case content hash at generation time against the 
    corresponding node in the latest document version to determine staleness.
    
    Returns:
        A tuple of (stale_status, reason_string)
    """
    # 1. Fetch the source node from SQLite
    orig_node = db.query(SectionNode).filter(SectionNode.id == source_node_id).first()
    if not orig_node:
        return "UNKNOWN", "The original source node ID could not be found in the database."
        
    logical_id = orig_node.logical_node_id
    
    # 2. Find the counterpart of this node in the latest version
    latest_node = db.query(SectionNode).filter(
        SectionNode.version_id == latest_version.id,
        SectionNode.logical_node_id == logical_id
    ).first()
    
    # 3. Assess status
    if not latest_node or latest_node.status == "DELETED":
        return "STALE", f"The source requirement section '{orig_node.heading or orig_node.title}' was DELETED in version {latest_version.version_number}."
        
    if latest_node.content_hash == stored_hash:
        return "NOT STALE", f"The requirement content matches the latest version ({latest_version.version_number}) content hash."
        
    # Content hash changed
    return "STALE", f"The requirement content was MODIFIED in version {latest_version.version_number}. Hash changed from {stored_hash[:8]} to {latest_node.content_hash[:8]}."

@router.get("", response_model=List[TestCaseResponse])
def query_test_cases(
    selection_id: Optional[str] = Query(None, description="Filter by selection ID"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    version: Optional[str] = Query(None, description="Filter by document version number at generation time"),
    status: Optional[str] = Query(None, description="Filter by status: 'active' (NOT STALE) or 'stale' (STALE)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves previously generated test cases from the NoSQL database.
    Performs real-time stale traceability detection against the latest version.
    Supports filtering by selection, node, version, and stale/active status.
    """
    logger.info(f"Querying test cases: selection_id={selection_id}, node_id={node_id}, version={version}, status={status}")
    
    # 1. Build NoSQL query filters
    filters = {}
    if selection_id:
        filters["selection_id"] = selection_id
    if node_id:
        # Match test case where node_id is in the selection node_ids list
        filters["node_id"] = node_id
    if version:
        filters["version_number"] = version
        
    # Query NoSQL
    raw_tcs = nosql_store.get_test_cases(filters)
    
    # Fetch latest version to compute staleness
    latest_version = db.query(Version).order_by(Version.created_at.desc()).first()
    
    responses = []
    for tc in raw_tcs:
        source_hash = tc["content_hash"]
        source_node_id = tc["traceability"]
        
        # Determine staleness
        if latest_version:
            stale_status, reason = _determine_staleness(db, source_hash, source_node_id, latest_version)
        else:
            stale_status, reason = "UNKNOWN", "No document versions ingested yet to compare against."
            
        # Filter by status if requested
        # 'active' matches 'NOT STALE', 'stale' matches 'STALE'
        if status == "active" and stale_status != "NOT STALE":
            continue
        if status == "stale" and stale_status != "STALE":
            continue
            
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
            stale_status=stale_status,
            staleness_reason=reason
        ))
        
    return responses
