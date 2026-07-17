import difflib
from typing import List, Dict, Any, Tuple
from app.core.logging import logger

class VersionMatcher:
    @staticmethod
    def generate_lightweight_diff(old_text: str, new_text: str) -> str:
        """Generates a standard unified diff between two text blocks."""
        old_lines = (old_text or "").splitlines()
        new_lines = (new_text or "").splitlines()
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="V1",
            tofile="V2",
            lineterm=""
        )
        return "\n".join(list(diff))

    @staticmethod
    def match_versions(
        old_nodes: List[Dict[str, Any]], 
        new_nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Matches nodes from the new version against the old version using
        normalized logical node paths.
        
        Returns:
            A tuple of (processed_new_nodes, deleted_nodes_to_insert)
        """
        logger.info(f"Matching {len(new_nodes)} new nodes against {len(old_nodes)} old nodes...")
        
        # Build mapping of logical_node_id -> node for old nodes
        old_map = {n["logical_node_id"]: n for n in old_nodes}
        new_map = {n["logical_node_id"]: n for n in new_nodes}
        
        processed_new_nodes = []
        deleted_nodes_to_insert = []
        
        # Process new nodes
        for n_new in new_nodes:
            logical_id = n_new["logical_node_id"]
            
            if logical_id in old_map:
                n_old = old_map[logical_id]
                
                # Check content hash
                if n_new["content_hash"] == n_old["content_hash"]:
                    n_new["status"] = "UNCHANGED"
                    logger.info(f"Node '{n_new['heading'] or n_new['title']}' matches V1 exactly (UNCHANGED).")
                else:
                    n_new["status"] = "MODIFIED"
                    logger.info(f"Node '{n_new['heading'] or n_new['title']}' changed content (MODIFIED).")
            else:
                # Node exists in new version but not old
                n_new["status"] = "NEW"
                logger.info(f"Node '{n_new['heading'] or n_new['title']}' is NEW in V2.")
                
            processed_new_nodes.append(n_new)
            
        # Detect deleted nodes
        for n_old in old_nodes:
            logical_id = n_old["logical_node_id"]
            if logical_id not in new_map:
                logger.info(f"Node '{n_old['heading'] or n_old['title']}' was DELETED in V2.")
                # Create a placeholder in the new version marking it as DELETED
                deleted_node = {
                    "logical_node_id": logical_id,
                    "heading": n_old["heading"],
                    "title": n_old["title"],
                    "level": n_old["level"],
                    "body": n_old["body"],
                    "parent_id": None, # Will be set during insertion if parent exists
                    "content_hash": n_old["content_hash"],
                    "status": "DELETED"
                }
                deleted_nodes_to_insert.append(deleted_node)
                
        return processed_new_nodes, deleted_nodes_to_insert
