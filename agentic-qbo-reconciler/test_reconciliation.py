#!/usr/bin/env python3
"""Test script for the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
from pathlib import Path

def create_test_csv():
    """Create a temporary CSV file with test data."""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Write test data
    writer = csv.writer(temp_file)
    writer.writerow(['date', 'amount', 'description'])
    writer.writerow(['2024-09-01', '-150.00', 'Office Supplies'])
    writer.writerow(['2024-09-02', '2000.00', 'Client Payment'])
    writer.writerow(['2024-09-03', '-75.50', 'Utility Bill'])
    
    temp_file.close()
    return temp_file.name

def test_reconciliation():
    """Test the reconciliation endpoint."""
    # Create test CSV
    csv_file = create_test_csv()
    
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
        os.unlink(csv_file)

def test_qbo_mock():
    """Test the QBO mock endpoint."""
    response = requests.get('http://localhost:8000/qbo-mock')
    
    if response.status_code == 200:
        qbo_data = response.json()
        print("✅ QBO mock endpoint test passed!")
        print(f"\nFound {len(qbo_data)} mock QBO transactions:")
        
        for i, tx in enumerate(qbo_data, 1):
            print(f"\nTransaction {i}:")
            print(f"  ID: {tx['id']}")
            print(f"  Date: {tx['date']}")
            print(f"  Amount: ${tx['amount']}")
            print(f"  Description: {tx['description']}")
            
    else:
        print(f"❌ QBO mock endpoint test failed!")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler...")
    print("=" * 50)
    
    # Test the QBO mock endpoint first
    test_qbo_mock()
    print("\n" + "=" * 50)
    
    # Test the reconciliation endpoint
    test_reconciliation()
    
    print("\n" + "=" * 50)
    print("Test completed!")