from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import logger
from app.database.session import engine, Base
from app.api import browse, selection, llm, retrieval

# Initialize SQLite database tables on startup
logger.info("Creating SQLite database schema tables...")
Base.metadata.create_all(bind=engine)
logger.info("SQLite schema tables created successfully.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API pipeline for ingestion, versioning, selection, and LLM test-case generation.",
    version="1.0.0"
)

# Global Exception Handler (Task 12)
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error_type": type(exc).__name__,
            "message": str(exc)
        }
    )

@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"Validation error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Validation error or bad request parameters.",
            "message": str(exc)
        }
    )

# Register Router endpoints
app.include_router(browse.router, prefix=settings.API_V1_STR)
app.include_router(selection.router, prefix=settings.API_V1_STR)
app.include_router(llm.router, prefix=settings.API_V1_STR)
app.include_router(retrieval.router, prefix=settings.API_V1_STR)

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "app" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def read_root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return {
        "project": settings.PROJECT_NAME,
        "status": "healthy",
        "api_documentation": "/docs",
        "web_dashboard": "/dashboard"
    }

@app.get("/dashboard")
@app.get("/ui")
def read_dashboard():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)

@app.get("/download/approach-document-pdf")
def download_approach_doc():
    pdf_file = BASE_DIR / "approach_document.pdf"
    if pdf_file.exists():
        return FileResponse(
            pdf_file, 
            media_type="application/pdf", 
            filename="CardioTrack_CT200_Approach_Document_Harini_P.pdf"
        )
    return JSONResponse(status_code=404, content={"detail": "PDF not found."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
