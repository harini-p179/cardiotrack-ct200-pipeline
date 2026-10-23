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

def test_irregularity_duplicate_headings():
    """
    Irregularity Test 1:
    Duplicate headings across sections (or under same section) must produce
    distinct node IDs, stable distinct logical_node_ids, and retain correct parent IDs.
    """
    parser = DocumentParser("dummy.pdf", "1.0")
    parser.raw_elements = [
        {"type": "text", "content": "1 Section One", "page": 1, "top": 10},
        {"type": "text", "content": "1.1 General Information", "page": 1, "top": 20},
        {"type": "text", "content": "Content of section 1.1", "page": 1, "top": 30},
        {"type": "text", "content": "2 Section Two", "page": 1, "top": 50},
        {"type": "text", "content": "2.1 General Information", "page": 1, "top": 60},
        {"type": "text", "content": "Content of section 2.1", "page": 1, "top": 70},
    ]
    nodes = parser.build_tree()
    # root + 2 level-1 + 2 level-2 = 5 nodes
    assert len(nodes) == 5
    
    sec1 = next(n for n in nodes if n["heading"] == "1 Section One")
    sec2 = next(n for n in nodes if n["heading"] == "2 Section Two")
    sub1 = next(n for n in nodes if n["heading"] == "1.1 General Information")
    sub2 = next(n for n in nodes if n["heading"] == "2.1 General Information")
    
    # Assert distinct node IDs
    assert sub1["id"] != sub2["id"]
    # Assert correct distinct parent IDs
    assert sub1["parent_id"] == sec1["id"]
    assert sub2["parent_id"] == sec2["id"]
    # Assert distinct logical node IDs
    assert sub1["logical_node_id"] == "section_one/general_information"
    assert sub2["logical_node_id"] == "section_two/general_information"

def test_irregularity_broken_hierarchy_level_skip():
    """
    Irregularity Test 2:
    Broken hierarchy level skip (e.g. level 2 followed directly by level 4, skipping level 3).
    The parser must not fail, must attach the level 4 node to the closest ancestor (level 2),
    and validate_hierarchy must report 0 orphans.
    """
    parser = DocumentParser("dummy.pdf", "1.0")
    parser.raw_elements = [
        {"type": "text", "content": "2 Specifications", "page": 1, "top": 10},
        {"type": "text", "content": "2.1 Battery", "page": 1, "top": 20},
        {"type": "text", "content": "Battery specifications text.", "page": 1, "top": 30},
        {"type": "text", "content": "2.1.1.1 Battery Life Under Typical Use", "page": 1, "top": 40},
        {"type": "text", "content": "500 cycles or 1 year.", "page": 1, "top": 50},
    ]
    nodes = parser.build_tree()
    # root + level 1 (2) + level 2 (2.1) + level 4 (2.1.1.1) = 4 nodes
    assert len(nodes) == 4
    
    spec_node = next(n for n in nodes if n["heading"] == "2 Specifications")
    battery_node = next(n for n in nodes if n["heading"] == "2.1 Battery")
    skip_node = next(n for n in nodes if n["heading"] == "2.1.1.1 Battery Life Under Typical Use")
    
    assert battery_node["parent_id"] == spec_node["id"]
    # Level 4 node skipped level 3; it must be parented directly to level 2 battery node
    assert skip_node["parent_id"] == battery_node["id"]
    assert skip_node["level"] == 4
    assert parser.validate_hierarchy() is True

def test_irregularity_numbered_classification_not_misidentified():
    """
    Irregularity Test 3:
    Numbered classification items with colons (e.g. '1. Normal: Blood pressure is standard')
    must not be treated as headings, preventing corruption of section hierarchy.
    """
    parser = DocumentParser("dummy.pdf", "1.0")
    parser.raw_elements = [
        {"type": "text", "content": "3 Device Operation", "page": 1, "top": 10},
        {"type": "text", "content": "1. Normal: Blood pressure is within standard range.", "page": 1, "top": 20},
        {"type": "text", "content": "2. Elevated: Blood pressure is mildly elevated.", "page": 1, "top": 30},
    ]
    nodes = parser.build_tree()
    # root + 1 section = 2 nodes total (the classification items remain in body)
    assert len(nodes) == 2
    op_node = nodes[1]
    assert op_node["heading"] == "3 Device Operation"
    assert "1. Normal: Blood pressure is within standard range." in op_node["body"]
    assert "2. Elevated: Blood pressure is mildly elevated." in op_node["body"]

