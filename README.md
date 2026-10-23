# CardioTrack CT-200 Document Pipeline

A production-quality backend API pipeline for technical document ingestion, structural parsing, versioning comparison, version-pinned requirement selection, LLM-based QA test-case generation, and real-time stale traceability mapping.

## Technology Stack
- **Backend Framework**: Python 3.12+ & FastAPI
- **Relational Store**: SQLAlchemy 2.0+ & SQLite (for document hierarchy trees, versions, and selections)
- **NoSQL / Document Store**: Portable local JSON Store (with auto-switching to MongoDB if running instance URL is provided in `.env`)
- **PDF Extraction**: `pdfplumber` (layout-sorted flow extraction, text and table alignment)
- **AI Integration**: Gemini API (`google-generativeai`) with structured response validation and automatic fallback
- **Test Suite**: `pytest`

---

## Getting Started

### 1. Prerequisites
Ensure you have **Python 3.12 or newer** installed. Check your version with:
```bash
python --version
```

### 2. Installation & Setup
Clone or navigate to the project directory, then create and activate a Python virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install all project dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample environment file to create your active configuration:
```bash
cp .env.example .env
```

Open `.env` in a text editor to view or edit the settings:
- `NOSQL_STORE`: Defaults to `"json"` (local file storage). To use MongoDB, set to `"mongodb"` and update `MONGODB_URL`.
- `GEMINI_API_KEY`: Provide a valid Gemini API Key to enable live AI generations. If left empty, the pipeline uses a robust mock generator to ensure it runs out-of-the-box with zero keys.

---

## Running the Pipeline

### Step 1: Ingest Document Versions
Run the ingestion script to parse the PDF manuals (`ct200_manual.pdf` and `ct200_manual_v2.pdf`), build the parent-child node tree, resolve level skips, run the node matching/diffing comparator, and populate the SQLite database:
```bash
python scripts/ingest.py
```
This builds `ct200_pipeline.db` in your workspace and populates it with document versions `1.0` and `2.0`.

### Step 2: Start the Web API Server
Run the FastAPI development server using Uvicorn on port 8001:
```bash
uvicorn main:app --port 8001 --reload
```
The server will start at `http://localhost:8001`. You can access the interactive Swagger API documentation at:
👉 **[http://localhost:8001/docs](http://localhost:8001/docs)**

### Step 3: Run the End-to-End Demonstration Script
We provide an automated demonstration script that runs through the complete end-to-end lifecycle (browsing, comparing, version-pinned selection creation, LLM QA test case generation, and real-time stale traceability mapping):
```bash
python scripts/demo_run.py
```

### Step 4: Run the Test Suite
Execute the entire unit and integration test suite to verify the parser, structural irregularity handling, versioning comparator, API routes, LLM services, and stale traceability checks:
```bash
pytest -v
```

---

## API Endpoint Overview

### 1. Document Browsing & Comparison
- `GET /api/nodes` - List top-level sections (defaults to latest version, supports `?version_num=1.0`).
- `GET /api/nodes/search` - Search requirement headings or body text (supports `?q=search_term&version_num=2.0`).
- `GET /api/nodes/{id}` - Retrieve a specific section node by ID, including its child outline and recursively reconstructed full text body.
- `GET /api/nodes/{id}/compare` - Compare a section across versions to get its change status (`UNCHANGED`, `MODIFIED`, `NEW`, `DELETED`) and line-by-line unified diff.

### 2. Selections
- `POST /api/selections` - Save a named group of version-pinned section node IDs.
  - Body: `{"name": "Cuff Alarms", "version_id": "uuid-here", "node_ids": ["uuid-1", "uuid-2"]}`
- `GET /api/selections` - List all saved selections.
- `GET /api/selections/{id}` - Retrieve a specific selection and its pinned nodes.

### 3. LLM QA Test Case Generation
- `POST /api/generations/{selection_id}` - Generate QA test cases from selected requirements.
  - *Duplicate Submission Policy*: If test cases already exist for this selection, the pipeline checks node content hashes. If unchanged, it returns the cached cases. If requirements have changed, it automatically overwrites and regenerates them to maintain cost-efficiency.

### 4. Retrieval & Stale Traceability
- `GET /api/retrieval` - Retrieve generated test cases (supports filtering by `selection_id`, `node_id`, `version`, or status: `?status=stale` or `?status=active`).
  - *Real-time Staleness Check*: Compares the requirement hash at generation time against the counterpart section in the latest document version. Flags test cases as `STALE` (with reasons: Modified content or Deleted section) or `NOT STALE` dynamically.
