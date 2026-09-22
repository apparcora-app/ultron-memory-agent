#!/usr/bin/env python3
"""Final test script for the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
import time
from pathlib import Path

def create_final_test_csv():
    """Create a temporary CSV file with final test data."""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Write final test data
    writer = csv.writer(temp_file)
    writer.writerow(['date', 'amount', 'description'])
    writer.writerow(['2024-09-01', '-150.00', 'Office Supplies'])
    writer.writerow(['2024-09-02', '2000.00', 'Client Payment'])
    writer.writerow(['2024-09-03', '-75.50', 'Utility Bill'])
    writer.writerow(['2024-09-04', '500.00', 'Consulting Fee'])
    writer.writerow(['2024-09-05', '-200.00', 'Software Subscription'])
    writer.writerow(['2024-09-06', '1000.00', 'Large Payment'])
    writer.writerow(['2024-09-07', '-50.00', 'Small Expense'])
    
    temp_file.close()
    return temp_file.name

def run_final_tests():
    """Run final tests on the reconciliation endpoint."""
    # Create test CSV
    csv_file = create_final_test_csv()
    
    try:
        # Test the reconciliation endpoint
        with open(csv_file, 'rb') as f:
            files = {'file': (os.path.basename(csv_file), f, 'text/csv')}
            response = requests.post('http://localhost:8000/reconcile', files=files)
        
        if response.status_code == 200:
            results = response.json()
            print("✅ Final test passed!")
            print(f"\nFound {len(results)} transactions:")
            
            # Test the QBO mock endpoint
            qbo_response = requests.get('http://localhost:8000/qbo-mock')
            if qbo_response.status_code == 200:
                qbo_data = qbo_response.json()
                print(f"\nQBO mock endpoint returned {len(qbo_data)} transactions")
            else:
                print(f"\n⚠️  QBO mock endpoint failed: {qbo_response.status_code}")
            
            # Verify the structure of the response
            print(f"\nResponse structure verification:")
            for i, result in enumerate(results, 1):
                print(f"\nTransaction {i}:")
                print(f"  Has bank_transaction: {'bank_transaction' in result}")
                print(f"  Has qbo_match: {'qbo_match' in result}")
                print(f"  Has status: {'status' in result}")
                
                if 'bank_transaction' in result:
                    print(f"    Bank transaction fields: {list(result['bank_transaction'].keys())}")
                    
                if 'qbo_match' in result and result['qbo_match']:
                    print(f"    QBO match fields: {list(result['qbo_match'].keys())}")
                elif 'qbo_match' in result and not result['qbo_match']:
                    print(f"    QBO match: None")
                    
                print(f"    Status: {result['status']}")
            
            # Verify all transactions are processed
            if len(results) == 7:
                print(f"\n✅ All 7 transactions were processed")
            else:
                print(f"\n⚠️  Expected 7 transactions, got {len(results)}")
                
        else:
            print(f"❌ Final test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        os.unlink(csv_file)

if __name__ == '__main__':
    print("Running Final Tests for Agentic QBO Reconciler...")
    print("=" * 50)
    
    # Run final tests
    run_final_tests()
    
    print("\n" + "=" * 50)
    print("Test completed!")