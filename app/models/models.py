import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from app.database.session import Base

def generate_uuid():
    return str(uuid.uuid4())

# Association table for Selections and SectionNodes (many-to-many relationship)
selection_node_association = Table(
    "selection_node_association",
    Base.metadata,
    Column("selection_id", String(36), ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True),
    Column("node_id", String(36), ForeignKey("section_nodes.id", ondelete="CASCADE"), primary_key=True)
)

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    versions = relationship("Version", back_populates="document", cascade="all, delete-orphan")

class Version(Base):
    __tablename__ = "versions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    content_hash = Column(String(64), nullable=True) # Overall version hash
    
    # Relationships
    document = relationship("Document", back_populates="versions")
    nodes = relationship("SectionNode", back_populates="version", cascade="all, delete-orphan")
    selections = relationship("Selection", back_populates="version", cascade="all, delete-orphan")

class SectionNode(Base):
    __tablename__ = "section_nodes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    version_id = Column(String(36), ForeignKey("versions.id", ondelete="CASCADE"), nullable=False)
    logical_node_id = Column(String(255), nullable=False) # Stable ID across versions
    heading = Column(String(255), nullable=True) # Full heading, e.g. "1.1 Intended Use"
    title = Column(String(255), nullable=False)  # Normalized title, e.g. "Intended Use"
    level = Column(Integer, nullable=False)      # Hierarchy level: 0 (root), 1, 2, 4 etc.
    body = Column(String, nullable=True)         # Node body (text + lists + tables)
    parent_id = Column(String(36), ForeignKey("section_nodes.id", ondelete="SET_NULL"), nullable=True)
    content_hash = Column(String(64), nullable=False) # SHA-256 of title + body
    status = Column(String(50), default="NEW")   # NEW, UNCHANGED, MODIFIED, DELETED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Self-referential hierarchy
    parent = relationship("SectionNode", remote_side=[id], back_populates="children")
    children = relationship("SectionNode", back_populates="parent", cascade="all, delete-orphan")
    
    # Relationships
    version = relationship("Version", back_populates="nodes")
    selections = relationship("Selection", secondary=selection_node_association, back_populates="nodes")

# Indexes for quick lookups
Index("ix_section_nodes_logical_id", SectionNode.logical_node_id)
Index("ix_section_nodes_version_id", SectionNode.version_id)
Index("ix_section_nodes_parent_id", SectionNode.parent_id)

class Selection(Base):
    __tablename__ = "selections"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    version_id = Column(String(36), ForeignKey("versions.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    version = relationship("Version", back_populates="selections")
    nodes = relationship("SectionNode", secondary=selection_node_association, back_populates="selections")
