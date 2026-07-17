import pytest
import os
from app.services.parser_service import DocumentParser

def test_parse_heading_valid():
    parser = DocumentParser("dummy.pdf", "1.0")
    
    # Test level 1
    h1 = parser.parse_heading("1 Device Overview")
    assert h1 is not None
    assert h1["numbering"] == "1"
    assert h1["title"] == "Device Overview"
    assert h1["level"] == 1
    assert h1["heading"] == "1 Device Overview"

    # Test level 2
    h2 = parser.parse_heading("1.1 Intended Use")
    assert h2 is not None
    assert h2["numbering"] == "1.1"
    assert h2["title"] == "Intended Use"
    assert h2["level"] == 2

    # Test level 4 (broken hierarchy edge case)
    h4 = parser.parse_heading("2.1.1.1 Battery Life Under Typical Use")
    assert h4 is not None
    assert h4["numbering"] == "2.1.1.1"
    assert h4["title"] == "Battery Life Under Typical Use"
    assert h4["level"] == 4

def test_parse_heading_invalid():
    parser = DocumentParser("dummy.pdf", "1.0")
    
    # Classification list item containing colon should be ignored
    assert parser.parse_heading("1. Normal: Blood pressure is standard.") is None
    
    # Random text should be ignored
    assert parser.parse_heading("This is just some paragraph text") is None
    assert parser.parse_heading("● Bullet point list item") is None

def test_table_to_markdown():
    parser = DocumentParser("dummy.pdf", "1.0")
    table_data = [
        ["Header A", "Header B"],
        ["Cell 1", "Cell 2"],
        [None, "Cell 4"]
    ]
    markdown = parser._table_to_markdown(table_data)
    assert "| Header A | Header B |" in markdown
    assert "| --- | --- |" in markdown
    assert "| Cell 1 | Cell 2 |" in markdown
    assert "|  | Cell 4 |" in markdown

def test_node_hash_calculation():
    parser = DocumentParser("dummy.pdf", "1.0")
    node = {
        "title": "Test Title",
        "body": "Test Body Content",
        "content_hash": ""
    }
    parser._update_node_hash(node)
    assert len(node["content_hash"]) == 64
    
    # Ensure hash changes if content changes
    old_hash = node["content_hash"]
    node["body"] = "Modified Body Content"
    parser._update_node_hash(node)
    assert node["content_hash"] != old_hash

def test_build_tree_with_mock_elements():
    parser = DocumentParser("dummy.pdf", "1.0")
    parser.raw_elements = [
        {"type": "text", "content": "1 Device Overview", "page": 1, "top": 50},
        {"type": "text", "content": "The device is a medical monitor.", "page": 1, "top": 60},
        {"type": "text", "content": "1.1 Intended Use", "page": 1, "top": 80},
        {"type": "text", "content": "Intended to measure systolic and diastolic pressure.", "page": 1, "top": 90},
        {"type": "table", "content": "| Parameter | Value |\n| --- | --- |\n| Systolic | 90-140 |", "page": 1, "top": 110}
    ]
    nodes = parser.build_tree()
    
    # Root + 2 sections = 3 nodes total
    assert len(nodes) == 3
    
    # Verify root
    root = nodes[0]
    assert root["logical_node_id"] == "document_root"
    assert root["level"] == 0
    assert len(root["children"]) == 1
    
    # Verify level 1 section
    l1 = nodes[1]
    assert l1["heading"] == "1 Device Overview"
    assert l1["logical_node_id"] == "device_overview"
    assert "medical monitor" in l1["body"]
    assert l1["parent_id"] == root["id"]
    
    # Verify level 2 section
    l2 = nodes[2]
    assert l2["heading"] == "1.1 Intended Use"
    assert l2["logical_node_id"] == "device_overview/intended_use"
    assert "systolic and diastolic" in l2["body"]
    assert "| Parameter | Value |" in l2["body"]
    assert l2["parent_id"] == l1["id"]
