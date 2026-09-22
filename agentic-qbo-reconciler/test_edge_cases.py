#!/usr/bin/env python3
"""Test script for edge cases in the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
from pathlib import Path

def create_test_csv_with_edge_cases():
    """Create a temporary CSV file with test data including edge cases."""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Write test data with edge cases
    writer = csv.writer(temp_file)
    writer.writerow(['date', 'amount', 'description'])
    writer.writerow(['2024-09-01', '-150.00', 'Office Supplies'])
    writer.writerow(['2024-09-02', '2000.00', 'Client Payment'])
    writer.writerow(['2024-09-03', '-75.50', 'Utility Bill'])
    writer.writerow(['2024-09-04', '500.00', 'Consulting Fee'])
    writer.writerow(['2024-09-05', '-200.00', 'Software Subscription'])
    writer.writerow(['2024-09-06', '1000.00', 'Large Payment'])  # This should not match
    writer.writerow(['2024-09-07', '-50.00', 'Small Expense'])  # This should not match
    
    temp_file.close()
    return temp_file.name

def test_edge_cases():
    """Test the reconciliation endpoint with edge cases."""
    # Create test CSV
    csv_file = create_test_csv_with_edge_cases()
    
    try:
        # Test the reconciliation endpoint
        with open(csv_file, 'rb') as f:
            files = {'file': (os.path.basename(csv_file), f, 'text/csv')}
            response = requests.post('http://localhost:8000/reconcile', files=files)
        
        if response.status_code == 200:
            results = response.json()
            print("✅ Edge cases test passed!")
            print(f"\nFound {len(results)} transactions:")
            
            matched_count = 0
            unmatched_count = 0
            
            for i, result in enumerate(results, 1):
                print(f"\nTransaction {i}:")
                print(f"  Bank: {result['bank_transaction']['date']} - ${result['bank_transaction']['amount']}")
                print(f"  Description: {result['bank_transaction']['description']}")
                
                if result['qbo_match']:
                    print(f"  QBO Match: {result['qbo_match']['date']} - ${result['qbo_match']['amount']}")
                    print(f"  QBO Description: {result['qbo_match']['description']}")
                    matched_count += 1
                else:
                    print(f"  QBO Match: None")
                    unmatched_count += 1
                
                print(f"  Status: {result['status']}")
            
            print(f"\nSummary:")
            print(f"  Matched: {matched_count}")
            print(f"  Unmatched: {unmatched_count}")
            print(f"  Total: {len(results)}")
                
        else:
            print(f"❌ Edge cases test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        os.unlink(csv_file)

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler with Edge Cases...")
    print("=" * 50)
    
    # Test the reconciliation endpoint
    test_edge_cases()
    
    print("\n" + "=" * 50)
    print("Test completed!")