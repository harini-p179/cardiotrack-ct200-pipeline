from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.models import Version, SectionNode, Selection
from app.schemas.schemas import SelectionCreate, SelectionResponse, NodeBriefResponse
from app.core.logging import logger

router = APIRouter(prefix="/selections", tags=["selections"])

@router.post("", response_model=SelectionResponse)
def create_selection(payload: SelectionCreate, db: Session = Depends(get_db)):
    """
    Creates a version-pinned selection of section nodes.
    Ensures all nodes exist and belong to the specified version.
    """
    logger.info(f"Creating selection '{payload.name}' for version ID {payload.version_id}")
    
    # 1. Verify version exists
    version = db.query(Version).filter(Version.id == payload.version_id).first()
    if not version:
        raise HTTPException(
            status_code=404, 
            detail=f"Version with ID '{payload.version_id}' not found."
        )
        
    # 2. Verify all nodes exist and belong to the correct version
    nodes = db.query(SectionNode).filter(
        SectionNode.id.in_(payload.node_ids),
        SectionNode.version_id == version.id
    ).all()
    
    found_ids = {n.id for n in nodes}
    missing_ids = set(payload.node_ids) - found_ids
    
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"The following node IDs are missing or do not belong to version '{version.version_number}': {list(missing_ids)}"
        )
        
    # 3. Create the selection
    selection = Selection(
        name=payload.name,
        version_id=version.id
    )
    db.add(selection)
    db.commit() # Commit to get ID
    
    # Associate nodes (many-to-many)
    selection.nodes = nodes
    db.commit()
    db.refresh(selection)
    
    logger.info(f"Selection '{selection.name}' created with {len(nodes)} nodes (ID: {selection.id})")
    
    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        version_id=selection.version_id,
        created_at=selection.created_at,
        nodes=[NodeBriefResponse.model_validate(n) for n in selection.nodes]
    )

@router.get("", response_model=List[SelectionResponse])
def list_selections(db: Session = Depends(get_db)):
    """Lists all stored selections."""
    selections = db.query(Selection).order_by(Selection.created_at.desc()).all()
    return selections

@router.get("/{id}", response_model=SelectionResponse)
def get_selection_by_id(id: str, db: Session = Depends(get_db)):
    """Retrieves a specific selection by ID, including its associated nodes."""
    selection = db.query(Selection).filter(Selection.id == id).first()
    if not selection:
        raise HTTPException(
            status_code=404,
            detail=f"Selection with ID '{id}' not found."
        )
    return selection
