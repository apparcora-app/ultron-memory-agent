#!/usr/bin/env python3
"""Test script to verify performance of the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
import time
from pathlib import Path

def create_large_test_csv(num_transactions=100):
    """Create a temporary CSV file with many test transactions."""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Write test data
    writer = csv.writer(temp_file)
    writer.writerow(['date', 'amount', 'description'])
    
    # Generate test data
    for i in range(num_transactions):
        date = f"2024-09-{i % 30 + 1:02d}"
        amount = round(-150.00 + (i * 10), 2) if i % 3 == 0 else round(2000.00 - (i * 5), 2)
        description = f"Transaction {i}"
        writer.writerow([date, amount, description])
    
    temp_file.close()
    return temp_file.name

def test_performance():
    """Test the performance of the reconciliation endpoint."""
    # Create test CSV with many transactions
    csv_file = create_large_test_csv(100)
    
    try:
        # Test the reconciliation endpoint
        with open(csv_file, 'rb') as f:
            files = {'file': (os.path.basename(csv_file), f, 'text/csv')}
            
            # Measure time
            start_time = time.time()
            response = requests.post('http://localhost:8000/reconcile', files=files)
            end_time = time.time()
            
            processing_time = end_time - start_time
        
        if response.status_code == 200:
            results = response.json()
            print("✅ Performance test passed!")
            print(f"\nProcessed {len(results)} transactions in {processing_time:.2f} seconds")
            print(f"Average processing time per transaction: {processing_time/len(results):.4f} seconds")
            
            # Verify all transactions are processed
            if len(results) == 100:
                print("✅ All 100 transactions were processed")
            else:
                print(f"⚠️  Expected 100 transactions, got {len(results)}")
                
        else:
            print(f"❌ Performance test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        os.unlink(csv_file)

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler Performance...")
    print("=" * 50)
    
    # Test the performance
    test_performance()
    
    print("\n" + "=" * 50)
    print("Test completed!")