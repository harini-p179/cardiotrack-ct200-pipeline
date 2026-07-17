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

@app.get("/")
def read_root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "healthy",
        "api_documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main.py:app", host="0.0.0.0", port=8000, reload=True)
