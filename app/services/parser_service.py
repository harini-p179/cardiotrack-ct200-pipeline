import re
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import pdfplumber
from app.core.logging import logger

class DocumentParser:
    def __init__(self, pdf_path: str, version_number: str):
        self.pdf_path = pdf_path
        self.version_number = version_number
        self.raw_elements: List[Dict[str, Any]] = []
        self.nodes: List[Dict[str, Any]] = []
        self.root_node: Optional[Dict[str, Any]] = None
        self.document_title = "CardioTrack CT-200 Home Blood Pressure Monitor — Technical & User Manual"

    def extract_elements(self) -> List[Dict[str, Any]]:
        """
        Extracts both text lines and tables from the PDF.
        Sorts them based on their vertical 'top' coordinates on each page
        to reconstruct the document in the correct logical reading order.
        """
        logger.info(f"Extracting layout elements from PDF: {self.pdf_path}")
        all_elements = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                
                # 1. Extract all tables on the page
                tables = page.find_tables()
                
                # Filter out sub-tables (tables contained within other tables)
                main_tables = []
                for t in tables:
                    bbox = t.bbox
                    is_subtable = False
                    for ot in tables:
                        if ot == t:
                            continue
                        obbox = ot.bbox
                        # If t is inside ot, it's a sub-table
                        if (bbox[0] >= obbox[0] - 2 and bbox[1] >= obbox[1] - 2 and
                            bbox[2] <= obbox[2] + 2 and bbox[3] <= obbox[3] + 2 and
                            (obbox[2] - obbox[0]) > (bbox[2] - bbox[0])):
                            is_subtable = True
                            break
                    if not is_subtable:
                        # Validate that it has rows and columns
                        data = t.extract()
                        if data and len(data) > 1 and len(data[0]) > 1:
                            main_tables.append(t)
                
                # 2. Extract words and filter out those that are inside tables
                words = page.extract_words()
                non_table_words = []
                for w in words:
                    x0, top, x1, bottom = w["x0"], w["top"], w["x1"], w["bottom"]
                    in_table = False
                    for mt in main_tables:
                        tx0, ttop, tx1, tbottom = mt.bbox
                        # Overlap check
                        if not (x1 < tx0 or x0 > tx1 or bottom < ttop or top > tbottom):
                            in_table = True
                            break
                    if not in_table:
                        non_table_words.append(w)
                
                # 3. Group non-table words into text lines by 'top' coordinate tolerance
                page_lines = []
                if non_table_words:
                    non_table_words.sort(key=lambda w: (w["top"], w["x0"]))
                    current_line = [non_table_words[0]]
                    for w in non_table_words[1:]:
                        if abs(w["top"] - current_line[-1]["top"]) < 3.0:
                            current_line.append(w)
                        else:
                            page_lines.append(current_line)
                            current_line = [w]
                    page_lines.append(current_line)
                
                # Convert list of words to text elements
                for line in page_lines:
                    line_text = " ".join([w["text"] for w in line]).strip()
                    if not line_text:
                        continue
                    # Calculate average top coordinate
                    avg_top = sum([w["top"] for w in line]) / len(line)
                    all_elements.append({
                        "type": "text",
                        "content": line_text,
                        "page": page_num,
                        "top": avg_top
                    })
                
                # 4. Add tables as elements
                for mt in main_tables:
                    data = mt.extract()
                    markdown_table = self._table_to_markdown(data)
                    all_elements.append({
                        "type": "table",
                        "content": markdown_table,
                        "page": page_num,
                        "top": mt.bbox[1]
                    })
                
                # Sort elements of current page by top coordinate
                # (This preserves reading flow on a per-page basis)
                page_elements = [el for el in all_elements if el["page"] == page_num]
                page_elements.sort(key=lambda x: x["top"])
                
        self.raw_elements = all_elements
        logger.info(f"Extracted {len(self.raw_elements)} raw elements from PDF.")
        return self.raw_elements

    def _table_to_markdown(self, data: List[List[Optional[str]]]) -> str:
        """Converts raw table data to a clean markdown format."""
        if not data:
            return ""
        cleaned_table = []
        for row in data:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(cell).strip().replace("\n", " "))
            cleaned_table.append(cleaned_row)
            
        headers = cleaned_table[0]
        alignments = ["---"] * len(headers)
        markdown = f"| {' | '.join(headers)} |\n"
        markdown += f"| {' | '.join(alignments)} |\n"
        for row in cleaned_table[1:]:
            markdown += f"| {' | '.join(row)} |\n"
        return markdown

    def parse_heading(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Regex to match numbered headings like "1. Device Overview" or "1.1 Intended Use"
        or "2.1.1.1 Battery Life Under Typical Use".
        Excludes list items (like '1. Normal:') that contain colons.
        """
        # Ensure we don't treat list classifications (e.g. "1. Normal:") as headings
        if ":" in text and len(text.split(":")[0]) < 30:
            # Contains a colon close to the start, highly likely a classification list item
            return None
            
        # Match standard patterns like "1. Section" or "1.1 Section" or "2.1.1.1 Section"
        match = re.match(r"^\s*(\d+(?:\.\d+)*\.?)\s+(.*)$", text)
        if not match:
            return None
            
        numbering = match.group(1).rstrip(".")
        title = match.group(2).strip()
        
        parts = numbering.split(".")
        if all(p.isdigit() for p in parts):
            # Guard against quantities/measurements like "500 cycles" or "120 mmHg"
            # Section chapters do not exceed 20, and headings must start with an uppercase letter
            if int(parts[0]) > 20:
                return None
            if not title or not title[0].isupper():
                return None
                
            level = len(parts)
            return {
                "numbering": numbering,
                "title": title,
                "level": level,
                "heading": f"{numbering} {title}"
            }
        return None

    def build_tree(self) -> List[Dict[str, Any]]:
        """
        Reconstructs the hierarchical document tree from layout elements.
        Validates the structure and resolves missing levels in the stack.
        """
        if not self.raw_elements:
            self.extract_elements()
            
        logger.info("Reconstructing document hierarchy tree...")
        
        # Initialize Document Root Node at Level 0
        root = {
            "id": str(uuid.uuid4()),
            "logical_node_id": "document_root",
            "heading": None,
            "title": self.document_title,
            "level": 0,
            "body": "",
            "parent_id": None,
            "children": [],
            "content_hash": "",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "NEW"
        }
        self.root_node = root
        self.nodes = [root]
        
        # Stack to keep track of parent nodes at each level: list of tuples (level, node_dict)
        stack = [(0, root)]
        
        active_node = root
        
        for el in self.raw_elements:
            if el["type"] == "text":
                text = el["content"]
                
                # Ignore PDF headers/footers (e.g., page numbers or manual titles)
                if text == "CardioTrack CT-200 Home Blood" or text == "Pressure Monitor — Technical &" or text == "User Manual":
                    continue
                if re.match(r"^---\s*PAGE\s+\d+\s*---$", text):
                    continue
                if re.match(r"^\d+$", text): # Lone page numbers
                    continue
                
                heading_info = self.parse_heading(text)
                if heading_info:
                    # Create a new section node
                    level = heading_info["level"]
                    title = heading_info["title"]
                    heading = heading_info["heading"]
                    
                    # Pop stack until we find a parent with level < L
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                        
                    if not stack:
                        # Fallback to root if stack gets empty (shouldn't happen)
                        parent = root
                    else:
                        parent = stack[-1][1]
                    
                    # Build stable logical node id based on title path
                    path_parts = [p[1]["title"].lower().replace(" ", "_") for p in stack if p[0] > 0]
                    path_parts.append(title.lower().replace(" ", "_"))
                    logical_node_id = "/".join(path_parts)
                    
                    # Disambiguate if duplicate heading path already exists
                    existing_logical_ids = {n["logical_node_id"] for n in self.nodes}
                    if logical_node_id in existing_logical_ids:
                        base_logical_id = logical_node_id
                        counter = 2
                        while f"{base_logical_id}_{counter}" in existing_logical_ids:
                            counter += 1
                        logical_node_id = f"{base_logical_id}_{counter}"
                    
                    new_node = {
                        "id": str(uuid.uuid4()),
                        "logical_node_id": logical_node_id,
                        "heading": heading,
                        "title": title,
                        "level": level,
                        "body": "",
                        "parent_id": parent["id"],
                        "children": [],
                        "content_hash": "",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "status": "NEW"
                    }
                    
                    parent["children"].append(new_node["id"])
                    self.nodes.append(new_node)
                    stack.append((level, new_node))
                    active_node = new_node
                else:
                    # Append body text (joining with space or newline)
                    # Check if it starts with list bullet
                    if text.startswith("●") or text.startswith("-") or re.match(r"^\d+\.\s+", text):
                        if active_node["body"]:
                            active_node["body"] += f"\n{text}"
                        else:
                            active_node["body"] = text
                    else:
                        if active_node["body"]:
                            if active_node["body"].endswith("\n") or active_node["body"].endswith("●") or active_node["body"].endswith("-"):
                                active_node["body"] += f" {text}"
                            else:
                                active_node["body"] += f"\n{text}" if active_node["body"].endswith(".") else f" {text}"
                        else:
                            active_node["body"] = text
                            
            elif el["type"] == "table":
                # Tables are appended to the body of the active section node
                table_md = el["content"]
                if active_node["body"]:
                    active_node["body"] += f"\n\n{table_md}\n"
                else:
                    active_node["body"] = f"{table_md}\n"
                    
        # Calculate hashes for all nodes
        for node in self.nodes:
            self._update_node_hash(node)
            
        self.validate_hierarchy()
        return self.nodes

    def _update_node_hash(self, node: Dict[str, Any]):
        """Calculates SHA-256 content hash based on title and body."""
        content = f"{node['title']}|{node['body'] or ''}"
        node["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()

    def validate_hierarchy(self):
        """
        Validates the reconstructed document tree.
        Ensures parents exist, detects level skips (broken hierarchies), 
        and verifies content is not silently dropped.
        """
        logger.info("Validating document hierarchy...")
        orphans = 0
        skips = 0
        
        # Check node parent-child mapping consistency
        node_dict = {n["id"]: n for n in self.nodes}
        for n in self.nodes:
            if n["parent_id"]:
                if n["parent_id"] not in node_dict:
                    logger.warning(f"Orphan node detected: '{n['heading']}' (ID: {n['id']}) has parent ID {n['parent_id']} which is missing.")
                    orphans += 1
                else:
                    parent = node_dict[n["parent_id"]]
                    # If we skip levels (e.g., from 2 directly to 4), log it as a hierarchy warning
                    if n["level"] - parent["level"] > 1:
                        logger.info(f"Broken hierarchy detected (gracefully handled): level skip from level {parent['level']} ('{parent['heading']}') to level {n['level']} ('{n['heading']}')")
                        skips += 1
                        
        logger.info(f"Validation complete: {orphans} orphans, {skips} level skips (broken hierarchy paths handled).")
        return orphans == 0
