import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

class NoSQLStore:
    def __init__(self):
        self.store_type = settings.NOSQL_STORE
        self.json_path = settings.JSON_STORE_PATH
        self.db = None
        self.collection = None
        
        # Ensure parent directory for JSON store exists
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        
        if self.store_type == "mongodb":
            try:
                import pymongo
                logger.info(f"Connecting to MongoDB at: {settings.MONGODB_URL}")
                self.client = pymongo.MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
                # Try to ping server
                self.client.server_info()
                self.db = self.client[settings.MONGODB_DB]
                self.collection = self.db["test_cases"]
                logger.info("Successfully connected to MongoDB.")
            except Exception as e:
                logger.warning(f"Failed to connect to MongoDB ({str(e)}). Falling back to JSON file storage.")
                self.store_type = "json"

    def _read_json_file(self) -> List[Dict[str, Any]]:
        """Helper to read from the JSON file."""
        if not os.path.exists(self.json_path):
            return []
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except Exception as e:
            logger.error(f"Error reading JSON store: {e}")
            return []

    def _write_json_file(self, data: List[Dict[str, Any]]):
        """Helper to write to the JSON file."""
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error writing to JSON store: {e}")

    def save_test_cases(self, test_cases: List[Dict[str, Any]]):
        """Stores a list of test cases in the active database store (MongoDB or JSON file)."""
        logger.info(f"Saving {len(test_cases)} test cases in NoSQL store ({self.store_type})...")
        
        records = []
        for tc in test_cases:
            record = {
                "id": tc.get("id") or str(uuid.uuid4()),
                "title": tc["title"],
                "requirement": tc["requirement"],
                "steps": tc["steps"],
                "expected_result": tc["expected_result"],
                "priority": tc["priority"],
                "risk": tc["risk"],
                "traceability": tc["traceability"],
                "selection_id": tc["selection_id"],
                "version_number": tc["version_number"],
                "node_ids": tc["node_ids"],
                "content_hash": tc["content_hash"],
                "timestamp": tc.get("timestamp") or datetime.utcnow().isoformat()
            }
            records.append(record)

        if self.store_type == "mongodb" and self.collection is not None:
            try:
                self.collection.insert_many(records)
                logger.info("Saved records in MongoDB collection.")
                return
            except Exception as e:
                logger.error(f"MongoDB write failed: {e}. Falling back to file save.")
                # Fallback to JSON saving on failure
                
        # JSON file save
        data = self._read_json_file()
        data.extend(records)
        self._write_json_file(data)
        logger.info(f"Saved records in local JSON file: {self.json_path}")

    def get_test_cases(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieves test cases from the database matching the provided filters."""
        filters = filters or {}
        
        if self.store_type == "mongodb" and self.collection is not None:
            try:
                query = {}
                if "selection_id" in filters:
                    query["selection_id"] = filters["selection_id"]
                if "traceability" in filters:
                    query["traceability"] = filters["traceability"]
                if "version_number" in filters:
                    query["version_number"] = filters["version_number"]
                    
                cursor = self.collection.find(query)
                results = []
                for doc in cursor:
                    # convert MongoDB _id to string or remove it
                    doc["id"] = doc.get("id") or str(doc["_id"])
                    if "_id" in doc:
                        del doc["_id"]
                    results.append(doc)
                return results
            except Exception as e:
                logger.error(f"MongoDB read failed: {e}. Reading from local file.")
                
        # JSON file retrieval
        data = self._read_json_file()
        results = []
        for doc in data:
            match = True
            for k, v in filters.items():
                # Allow matching element inside list, e.g. node_id in node_ids
                if k == "node_id":
                    if v not in doc.get("node_ids", []):
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc)
        return results

    def delete_test_cases_by_selection(self, selection_id: str):
        """Deletes test cases for a specific selection. Used to overwrite/regenerate."""
        if self.store_type == "mongodb" and self.collection is not None:
            try:
                self.collection.delete_many({"selection_id": selection_id})
                return
            except Exception as e:
                logger.error(f"MongoDB delete failed: {e}.")
                
        # JSON file delete
        data = self._read_json_file()
        filtered_data = [doc for doc in data if doc.get("selection_id") != selection_id]
        self._write_json_file(filtered_data)

nosql_store = NoSQLStore()
