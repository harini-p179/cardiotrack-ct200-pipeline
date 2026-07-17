from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Version, SectionNode
from app.schemas.schemas import NodeBriefResponse, NodeResponse, NodeDetailResponse, CompareResponse
from app.services.versioning_service import VersionMatcher
from app.core.logging import logger

router = APIRouter(prefix="/nodes", tags=["browse"])

def _get_latest_version(db: Session) -> str:
    """Helper to get the latest ingested version number."""
    v = db.query(Version).order_by(Version.created_at.desc()).first()
    if not v:
        raise HTTPException(status_code=404, detail="No document versions ingested yet.")
    return v.version_number

def reconstruct_full_text(node: SectionNode, db: Session) -> str:
    """Recursively reconstructs the full text of a node and all of its descendants."""
    parts = []
    if node.heading:
        parts.append(node.heading)
    elif node.title:
        parts.append(node.title)
        
    if node.body:
        parts.append(node.body)
        
    # Query children sorted by heading to preserve hierarchy order
    children = db.query(SectionNode).filter(
        SectionNode.parent_id == node.id
    ).order_by(SectionNode.heading).all()
    
    # Filter out DELETED placeholders from text reconstruction
    active_children = [c for c in children if c.status != "DELETED"]
    
    for child in active_children:
        child_text = reconstruct_full_text(child, db)
        parts.append(child_text)
        
    return "\n\n".join(parts)

@router.get("", response_model=List[NodeBriefResponse])
def list_top_level_sections(
    version_num: Optional[str] = Query(None, description="Filter by version number. Defaults to latest."),
    db: Session = Depends(get_db)
):
    """Lists the top-level sections (level 1) of the document."""
    if not version_num:
        version_num = _get_latest_version(db)
        
    version = db.query(Version).filter(Version.version_number == version_num).first()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version '{version_num}' not found.")
        
    # Get level 1 nodes for this version.
    # Note: level 0 is the root node itself. Level 1 are top-level headings.
    nodes = db.query(SectionNode).filter(
        SectionNode.version_id == version.id,
        SectionNode.level == 1,
        SectionNode.status != "DELETED"
    ).order_by(SectionNode.heading).all()
    
    return nodes

@router.get("/search", response_model=List[NodeBriefResponse])
def search_nodes(
    q: str = Query(..., description="Query string to search in heading or body"),
    version_num: Optional[str] = Query(None, description="Filter by version number. Defaults to latest."),
    db: Session = Depends(get_db)
):
    """Searches headings and text body across nodes in a specific version."""
    if not version_num:
        version_num = _get_latest_version(db)
        
    version = db.query(Version).filter(Version.version_number == version_num).first()
    if not version:
        raise HTTPException(status_code=404, detail=f"Version '{version_num}' not found.")
        
    nodes = db.query(SectionNode).filter(
        SectionNode.version_id == version.id,
        SectionNode.status != "DELETED",
        (SectionNode.heading.ilike(f"%{q}%") | SectionNode.body.ilike(f"%{q}%"))
    ).order_by(SectionNode.level, SectionNode.heading).all()
    
    return nodes

@router.get("/{id}", response_model=NodeDetailResponse)
def get_node_by_id(id: str, db: Session = Depends(get_db)):
    """Retrieves a specific node by its ID, including its children list and reconstructed text."""
    node = db.query(SectionNode).filter(SectionNode.id == id).first()
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{id}' not found.")
        
    children = db.query(SectionNode).filter(
        SectionNode.parent_id == node.id,
        SectionNode.status != "DELETED"
    ).order_by(SectionNode.heading).all()
    
    full_text = reconstruct_full_text(node, db)
    
    # We construct the response manually to handle children mapping and text reconstruction
    return NodeDetailResponse(
        id=node.id,
        logical_node_id=node.logical_node_id,
        heading=node.heading,
        title=node.title,
        level=node.level,
        body=node.body,
        parent_id=node.parent_id,
        content_hash=node.content_hash,
        status=node.status,
        full_text_reconstruction=full_text,
        children=[NodeBriefResponse.model_validate(c) for c in children]
    )

@router.get("/{id}/compare", response_model=CompareResponse)
def compare_node_across_versions(id: str, db: Session = Depends(get_db)):
    """
    Compares a node (by its ID) with its counterpart in the previous version
    or next version based on logical_node_id, generating a lightweight diff.
    """
    node = db.query(SectionNode).filter(SectionNode.id == id).first()
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{id}' not found.")
        
    # Get current version
    current_version = node.version
    
    # Find all versions of the document sorted by created_at
    versions = db.query(Version).filter(
        Version.document_id == current_version.document_id
    ).order_by(Version.created_at).all()
    
    version_ids = [v.id for v in versions]
    curr_idx = version_ids.index(current_version.id)
    
    if curr_idx == 0:
        # This is the first version, so no previous version exists
        return CompareResponse(
            logical_node_id=node.logical_node_id,
            title=node.title,
            heading=node.heading,
            status=node.status,
            diff_summary="This node was introduced in the first version.",
            v1_body=None,
            v2_body=node.body
        )
        
    # Fetch the node in the previous version
    prev_version_id = version_ids[curr_idx - 1]
    prev_node = db.query(SectionNode).filter(
        SectionNode.version_id == prev_version_id,
        SectionNode.logical_node_id == node.logical_node_id
    ).first()
    
    if not prev_node:
        # Node did not exist in previous version
        return CompareResponse(
            logical_node_id=node.logical_node_id,
            title=node.title,
            heading=node.heading,
            status="NEW",
            diff_summary="New section node introduced in this version.",
            v1_body=None,
            v2_body=node.body
        )
        
    # Node exists in both. Calculate diff.
    diff = VersionMatcher.generate_lightweight_diff(
        prev_node.body or "", 
        node.body or ""
    )
    
    status = "UNCHANGED" if node.content_hash == prev_node.content_hash else "MODIFIED"
    if status == "UNCHANGED":
        diff_summary = "No changes between versions."
    else:
        diff_summary = diff if diff else "Body content changed structure."
        
    return CompareResponse(
        logical_node_id=node.logical_node_id,
        title=node.title,
        heading=node.heading,
        status=status,
        diff_summary=diff_summary,
        v1_body=prev_node.body,
        v2_body=node.body
    )
