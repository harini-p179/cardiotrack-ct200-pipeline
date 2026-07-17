import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Document, Version, SectionNode, Selection
from app.services.parser_service import DocumentParser
from app.services.versioning_service import VersionMatcher
from app.core.logging import logger

class DBService:
    @staticmethod
    def get_or_create_document(db: Session, name: str) -> Document:
        """Retrieves an existing document by name or creates a new one."""
        doc = db.query(Document).filter(Document.name == name).first()
        if not doc:
            doc = Document(name=name)
            db.add(doc)
            db.commit()
            db.refresh(doc)
            logger.info(f"Created new document in DB: {name} (ID: {doc.id})")
        return doc

    @staticmethod
    def ingest_document_version(db: Session, doc_name: str, file_path: str, version_num: str) -> Version:
        """
        Parses a PDF manual and ingests it as a new version.
        Runs the matching algorithm to flag changes against the latest existing version.
        """
        logger.info(f"Starting ingestion: doc_name={doc_name}, file={file_path}, version={version_num}")
        
        # 1. Get or create the Document
        doc = DBService.get_or_create_document(db, doc_name)
        
        # Check if version already exists
        existing_version = db.query(Version).filter(
            Version.document_id == doc.id,
            Version.version_number == version_num
        ).first()
        if existing_version:
            logger.info(f"Version {version_num} already exists in DB (ID: {existing_version.id}). Skipping ingestion.")
            return existing_version

        # 2. Parse PDF to extract nodes
        parser = DocumentParser(file_path, version_num)
        parsed_nodes = parser.build_tree()
        
        # 3. Fetch previous version for matching
        prev_version = db.query(Version).filter(
            Version.document_id == doc.id
        ).order_by(Version.created_at.desc()).first()
        
        nodes_to_insert = []
        
        if prev_version:
            # Load previous nodes
            prev_nodes_db = db.query(SectionNode).filter(
                SectionNode.version_id == prev_version.id
            ).all()
            
            # Convert DB model objects to simple dicts for matcher
            prev_nodes = []
            for pn in prev_nodes_db:
                # Skip DELETED placeholder nodes from comparison
                if pn.status == "DELETED":
                    continue
                prev_nodes.append({
                    "logical_node_id": pn.logical_node_id,
                    "heading": pn.heading,
                    "title": pn.title,
                    "level": pn.level,
                    "body": pn.body,
                    "content_hash": pn.content_hash
                })
                
            # Perform matching
            processed_new_nodes, deleted_nodes = VersionMatcher.match_versions(prev_nodes, parsed_nodes)
            
            # Map of logical_node_id to new DB node ID for child linking
            new_db_nodes = []
            
            # Create a new version object
            new_version = Version(
                document_id=doc.id,
                version_number=version_num,
                content_hash="" # Will compute below
            )
            db.add(new_version)
            db.commit() # Commit to get version ID
            
            # Insert new and modified nodes
            for node_dict in processed_new_nodes:
                db_node = SectionNode(
                    id=node_dict["id"],
                    version_id=new_version.id,
                    logical_node_id=node_dict["logical_node_id"],
                    heading=node_dict["heading"],
                    title=node_dict["title"],
                    level=node_dict["level"],
                    body=node_dict["body"],
                    parent_id=node_dict["parent_id"],
                    content_hash=node_dict["content_hash"],
                    status=node_dict["status"]
                )
                db.add(db_node)
                new_db_nodes.append(db_node)
                
            # Insert deleted node placeholders
            for del_node_dict in deleted_nodes:
                db_node = SectionNode(
                    version_id=new_version.id,
                    logical_node_id=del_node_dict["logical_node_id"],
                    heading=del_node_dict["heading"],
                    title=del_node_dict["title"],
                    level=del_node_dict["level"],
                    body=del_node_dict["body"],
                    parent_id=None, # Deleted nodes are detached
                    content_hash=del_node_dict["content_hash"],
                    status="DELETED"
                )
                db.add(db_node)
                
            db.commit()
            
        else:
            # No previous version exists. All nodes are NEW.
            new_version = Version(
                document_id=doc.id,
                version_number=version_num,
                content_hash=""
            )
            db.add(new_version)
            db.commit()
            
            for node_dict in parsed_nodes:
                db_node = SectionNode(
                    id=node_dict["id"],
                    version_id=new_version.id,
                    logical_node_id=node_dict["logical_node_id"],
                    heading=node_dict["heading"],
                    title=node_dict["title"],
                    level=node_dict["level"],
                    body=node_dict["body"],
                    parent_id=node_dict["parent_id"],
                    content_hash=node_dict["content_hash"],
                    status="NEW"
                )
                db.add(db_node)
            db.commit()
            
        # 4. Compute overall version hash (SHA-256 of all child content hashes combined)
        version_nodes = db.query(SectionNode).filter(SectionNode.version_id == new_version.id).order_by(SectionNode.heading).all()
        combined_hash = hashlib.sha256(
            "".join([n.content_hash for n in version_nodes]).encode("utf-8")
        ).hexdigest()
        
        new_version.content_hash = combined_hash
        db.commit()
        
        logger.info(f"Version {version_num} ingested successfully with {len(version_nodes)} nodes (Hash: {combined_hash})")
        return new_version
