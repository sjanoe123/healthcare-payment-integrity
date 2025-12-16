#!/usr/bin/env python3
"""Test the fraud analysis endpoint."""
from __future__ import annotations

import requests

BASE_URL = "http://localhost:8080"


def test_health():
    """Test health endpoint."""
    print("Testing /health...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")
    return resp.status_code == 200


def test_analysis():
    """Test claim analysis."""
    print("\nTesting /api/analyze...")

    # Sample claim with potential fraud indicators
    claim = {
        "claim_id": "TEST-001",
        "billed_amount": 15000.00,
        "diagnosis_codes": ["J06.9", "M54.5"],
        "items": [
            {
                "procedure_code": "99214",
                "diagnosis_code": "J06.9",
                "quantity": 1,
                "line_amount": 150.00,
            },
            {
                "procedure_code": "99215",
                "diagnosis_code": "M54.5",
                "quantity": 1,
                "line_amount": 200.00,
            },
            {
                "procedure_code": "99213",
                "diagnosis_code": "J06.9",
                "quantity": 2,  # MUE violation - should only be 1
                "line_amount": 180.00,
            },
        ],
        "provider": {
            "npi": "1234567890",  # This is on the OIG exclusion list in samples
            "specialty": "internal medicine",
        },
        "member": {
            "age": 45,
            "gender": "F",
        },
    }

    # First upload the claim
    print("  Uploading claim...")
    upload_resp = requests.post(f"{BASE_URL}/api/upload", json=claim)
    print(f"  Upload status: {upload_resp.status_code}")
    upload_data = upload_resp.json()
    job_id = upload_data.get("job_id")
    print(f"  Job ID: {job_id}")

    # Then analyze it
    print("  Running analysis...")
    analyze_resp = requests.post(f"{BASE_URL}/api/analyze/{job_id}", json=claim)
    print(f"  Analysis status: {analyze_resp.status_code}")

    if analyze_resp.status_code == 200:
        result = analyze_resp.json()
        print("\n  === ANALYSIS RESULTS ===")
        print(f"  Fraud Score: {result['fraud_score']:.2f}")
        print(f"  Decision Mode: {result['decision_mode']}")
        print(f"  NCCI Flags: {result['ncci_flags']}")
        print(f"  Coverage Flags: {result['coverage_flags']}")
        print(f"  Provider Flags: {result['provider_flags']}")
        print(f"  ROI Estimate: ${result['roi_estimate'] or 0:,.2f}")

        print(f"\n  Rule Hits ({len(result['rule_hits'])}):")
        for hit in result["rule_hits"]:
            print(f"    - [{hit['severity'].upper()}] {hit['rule_id']}: {hit['description']}")

        if result.get("claude_analysis"):
            claude = result["claude_analysis"]
            print("\n  === CLAUDE ANALYSIS ===")
            print(f"  Model: {claude.get('model', 'N/A')}")
            print(f"  Tokens: {claude.get('tokens_used', 0)}")
            if claude.get("explanation"):
                print(f"\n  Explanation:\n  {claude['explanation'][:500]}...")

        return True
    else:
        print(f"  Error: {analyze_resp.text}")
        return False


def test_search():
    """Test RAG search."""
    print("\nTesting /api/search...")
    resp = requests.post(
        f"{BASE_URL}/api/search",
        json={"query": "NCCI PTP edit billing modifier", "n_results": 3},
    )
    print(f"  Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total documents: {data.get('total_documents', 0)}")
        print(f"  Results found: {len(data.get('results', []))}")
        for r in data.get("results", []):
            print(f"    - {r['metadata'].get('topic', 'Unknown')}")
    return resp.status_code == 200


def main():
    print("=" * 60)
    print("Healthcare Payment Integrity Prototype - Test Suite")
    print("=" * 60)

    results = {
        "health": test_health(),
        "search": test_search(),
        "analysis": test_analysis(),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
