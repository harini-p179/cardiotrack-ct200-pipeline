import time
import httpx

API_URL = "http://localhost:8001"

def run_demo():
    print("=" * 80)
    print(" CARDIO TRACK CT-200 DOCUMENT PIPELINE - END-TO-END EXECUTION DEMONSTRATION")
    print("=" * 80)
    
    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        # 1. List all ingested manual versions
        print("\n[Step 1] Querying ingested document versions...")
        res = client.get("/api/nodes/versions")
        if res.status_code != 200:
            print(f"Error: {res.text}")
            return
        versions = res.json()
        for v in versions:
            print(f" - Version Number: {v['version_number']} | UUID: {v['id']} | Created At: {v['created_at']}")
            
        # Find UUIDs for V1 and V2
        v1_id = next((v['id'] for v in versions if v['version_number'] == "1.0"), None)
        v2_id = next((v['id'] for v in versions if v['version_number'] == "2.0"), None)
        
        if not v1_id or not v2_id:
            print("Error: Could not find V1.0 or V2.0 in the database.")
            return

        # 2. List V1.0 sections
        print("\n[Step 2] Fetching Version 1.0 top-level sections...")
        res = client.get("/api/nodes", params={"version_num": "1.0"})
        v1_sections = res.json()
        print(f"Found {len(v1_sections)} top-level sections in V1.0:")
        for s in v1_sections:
            print(f" - [{s['heading']}] {s['title']} | ID: {s['id']}")
            
        # Select "5 Data Management" node (which is modified in V2.0)
        target_section = next((s for s in v1_sections if s['heading'] and s['heading'].startswith("5")), v1_sections[0])
        print(f"\nSelected Target Node for pinning: Heading: '{target_section['heading']}', ID: '{target_section['id']}'")
        
        # 3. Retrieve target node details
        print("\n[Step 3] Fetching node details (reconstructed body text)...")
        res = client.get(f"/api/nodes/{target_section['id']}")
        node_details = res.json()
        print(f"Title: {node_details['title']}")
        print(f"Content Hash: {node_details['content_hash']}")
        print("Reconstructed Text Preview:")
        preview_lines = node_details['full_text_reconstruction'].splitlines()[:6]
        for line in preview_lines:
            print(f"   | {line}")
        print("   | ...")

        # 4. Compare section across versions
        print("\n[Step 4] Comparing this V1.0 section with V2.0 counterpart...")
        res = client.get(f"/api/nodes/{target_section['id']}/compare")
        comparison = res.json()
        print(f"Status: {comparison['status']}")
        print(f"Diff Summary / Change Log Preview:")
        diff_lines = (comparison['diff_summary'] or "").splitlines()[:10]
        for line in diff_lines:
            print(f"   | {line}")
            
        # 5. Create a version-pinned Selection referencing target V1.0 node
        print("\n[Step 5] Creating a named, version-pinned Selection on V1.0 specifications...")
        payload = {
            "name": "Specifications Selection (V1.0 Pinned)",
            "version_id": v1_id,
            "node_ids": [target_section['id']]
        }
        res = client.post("/api/selections", json=payload)
        selection = res.json()
        selection_id = selection['id']
        print(f"Selection Created successfully!")
        print(f" - Selection ID: {selection_id}")
        print(f" - Name: {selection['name']}")
        print(f" - Pinned Version: {selection['version_id']} (V1.0)")
        
        # 6. Generate test cases
        print("\n[Step 6] Triggering LLM/Mock QA test case generation for the selection...")
        res = client.post(f"/api/generations/{selection_id}")
        if res.status_code != 200:
            print(f"Generation failed: {res.text}")
            return
        test_cases = res.json()
        print(f"Generated {len(test_cases)} QA Test Cases successfully:")
        for idx, tc in enumerate(test_cases):
            print(f"\n   Test Case {idx + 1}: {tc['title']}")
            print(f"   Requirement: {tc['requirement']}")
            print(f"   Steps:")
            for s_idx, step in enumerate(tc['steps']):
                print(f"     {s_idx + 1}. {step}")
            print(f"   Expected Result: {tc['expected_result']}")
            print(f"   Priority: {tc['priority']} | Risk: {tc['risk']}")
            
        # 7. Query test cases and verify real-time stale status
        print("\n[Step 7] Querying test cases from NoSQL and running real-time staleness check...")
        res = client.get("/api/retrieval", params={"selection_id": selection_id})
        retrieved_cases = res.json()
        print(f"Retrieved {len(retrieved_cases)} test cases.")
        for idx, tc in enumerate(retrieved_cases):
            print(f"\n   Test Case {idx + 1}: {tc['title']}")
            print(f"   Stale Status: {tc['stale_status']}")
            print(f"   Staleness Reason: {tc['staleness_reason']}")
            
    print("=" * 80)
    print(" END OF DEMONSTRATION")
    print("=" * 80)

if __name__ == "__main__":
    run_demo()
