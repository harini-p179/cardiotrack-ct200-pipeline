import pytest
from app.services.versioning_service import VersionMatcher

def test_generate_lightweight_diff():
    old_text = "Line 1\nLine 2\nLine 3"
    new_text = "Line 1\nLine 2 changed\nLine 3\nLine 4"
    
    diff = VersionMatcher.generate_lightweight_diff(old_text, new_text)
    
    # Verify standard unified diff elements are present
    assert "--- V1" in diff
    assert "+++ V2" in diff
    assert "-Line 2" in diff
    assert "+Line 2 changed" in diff
    assert "+Line 4" in diff

def test_match_versions_all_cases():
    old_nodes = [
        {"logical_node_id": "root/unchanged", "heading": "1.1 Unchanged", "title": "Unchanged", "level": 2, "body": "Same body", "content_hash": "hash_1"},
        {"logical_node_id": "root/modified", "heading": "1.2 Modified", "title": "Modified", "level": 2, "body": "Old body", "content_hash": "hash_2"},
        {"logical_node_id": "root/deleted", "heading": "1.3 Deleted", "title": "Deleted", "level": 2, "body": "Deleted body", "content_hash": "hash_3"}
    ]
    
    new_nodes = [
        {"logical_node_id": "root/unchanged", "heading": "1.1 Unchanged", "title": "Unchanged", "level": 2, "body": "Same body", "content_hash": "hash_1"},
        {"logical_node_id": "root/modified", "heading": "1.2 Modified", "title": "Modified", "level": 2, "body": "New body", "content_hash": "hash_2_new"},
        {"logical_node_id": "root/new", "heading": "1.4 New", "title": "New", "level": 2, "body": "New body content", "content_hash": "hash_4"}
    ]
    
    processed_new, deleted_nodes = VersionMatcher.match_versions(old_nodes, new_nodes)
    
    # 1. Processed new nodes checks
    assert len(processed_new) == 3
    
    # Check Unchanged
    unchanged_node = next(n for n in processed_new if n["logical_node_id"] == "root/unchanged")
    assert unchanged_node["status"] == "UNCHANGED"
    
    # Check Modified
    modified_node = next(n for n in processed_new if n["logical_node_id"] == "root/modified")
    assert modified_node["status"] == "MODIFIED"
    
    # Check New
    new_node = next(n for n in processed_new if n["logical_node_id"] == "root/new")
    assert new_node["status"] == "NEW"
    
    # 2. Deleted nodes checks
    assert len(deleted_nodes) == 1
    deleted = deleted_nodes[0]
    assert deleted["logical_node_id"] == "root/deleted"
    assert deleted["status"] == "DELETED"
    assert deleted["body"] == "Deleted body"
