#!/usr/bin/env python3
"""Simple test script for the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
from pathlib import Path

def test_reconciliation():
    """Test the reconciliation endpoint."""
    # Create test CSV
    csv_file = "test_bank_statement.csv"
    
    try:
        # Test the reconciliation endpoint
        with open(csv_file, 'rb') as f:
            files = {'file': (os.path.basename(csv_file), f, 'text/csv')}
            response = requests.post('http://localhost:8000/reconcile', files=files)
        
        if response.status_code == 200:
            results = response.json()
            print("✅ Reconciliation test passed!")
            print(f"\nFound {len(results)} transactions:")
            
            for i, result in enumerate(results, 1):
                print(f"\nTransaction {i}:")
                print(f"  Bank: {result['bank_transaction']['date']} - ${result['bank_transaction']['amount']}")
                print(f"  Description: {result['bank_transaction']['description']}")
                
                if result['qbo_match']:
                    print(f"  QBO Match: {result['qbo_match']['date']} - ${result['qbo_match']['amount']}")
                    print(f"  QBO Description: {result['qbo_match']['description']}")
                else:
                    print(f"  QBO Match: None")
                
                print(f"  Status: {result['status']}")
            
            # Verify all transactions are matched
            unmatched_count = sum(1 for r in results if r['status'] == 'unmatched')
            if unmatched_count == 0:
                print(f"\n✅ All {len(results)} transactions were successfully matched!")
            else:
                print(f"\n⚠️  {unmatched_count} transactions were not matched.")
                
        else:
            print(f"❌ Reconciliation test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        if os.path.exists(csv_file):
            os.unlink(csv_file)

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler...")
    print("=" * 50)
    
    # Test the reconciliation endpoint
    test_reconciliation()
    
    print("\n" + "=" * 50)
    print("Test completed!")