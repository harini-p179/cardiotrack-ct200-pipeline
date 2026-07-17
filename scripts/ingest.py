import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal, Base, engine
from app.services.db_service import DBService
from app.core.config import settings
from app.core.logging import logger

def run_ingestion():
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Ingest Version 1
        pdf_v1 = str(settings.V1_PDF_PATH)
        logger.info(f"Ingesting Version 1 from {pdf_v1}...")
        v1 = DBService.ingest_document_version(
            db=db,
            doc_name="CT-200 Technical Manual",
            file_path=pdf_v1,
            version_num="1.0"
        )
        logger.info(f"Version 1 Ingestion Complete. Version ID: {v1.id}")
        
        # Ingest Version 2
        pdf_v2 = str(settings.V2_PDF_PATH)
        logger.info(f"Ingesting Version 2 from {pdf_v2}...")
        v2 = DBService.ingest_document_version(
            db=db,
            doc_name="CT-200 Technical Manual",
            file_path=pdf_v2,
            version_num="2.0"
        )
        logger.info(f"Version 2 Ingestion Complete. Version ID: {v2.id}")
        
        logger.info("Ingestion process completed successfully.")
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_ingestion()
