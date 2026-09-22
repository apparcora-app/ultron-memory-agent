#!/usr/bin/env python3
"""Test script for error handling in the Agentic QBO Reconciler."""

import requests
import json
import csv
import tempfile
import os
from pathlib import Path

def test_invalid_file_type():
    """Test the reconciliation endpoint with an invalid file type."""
    # Create a temporary file with invalid extension
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    
    # Write some text data
    temp_file.write("This is not a CSV file")
    temp_file.close()
    
    try:
        # Test the reconciliation endpoint
        with open(temp_file.name, 'rb') as f:
            files = {'file': (os.path.basename(temp_file.name), f, 'text/plain')}
            response = requests.post('http://localhost:8000/reconcile', files=files)
        
        if response.status_code == 400:
            print("✅ Invalid file type test passed!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Invalid file type test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        os.unlink(temp_file.name)

def test_invalid_csv_format():
    """Test the reconciliation endpoint with an invalid CSV format."""
    # Create a temporary file with invalid CSV format
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    
    # Write invalid CSV data (missing required columns)
    temp_file.write("date,amount\n2024-09-01,-150.00\n2024-09-02,2000.00")
    temp_file.close()
    
    try:
        # Test the reconciliation endpoint
        with open(temp_file.name, 'rb') as f:
            files = {'file': (os.path.basename(temp_file.name), f, 'text/csv')}
            response = requests.post('http://localhost:8000/reconcile', files=files)
        
        if response.status_code == 400:
            print("✅ Invalid CSV format test passed!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Invalid CSV format test failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    finally:
        # Clean up the temporary file
        os.unlink(temp_file.name)

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler Error Handling...")
    print("=" * 50)
    
    # Test invalid file type
    test_invalid_file_type()
    print("\n" + "=" * 50)
    
    # Test invalid CSV format
    test_invalid_csv_format()
    
    print("\n" + "=" * 50)
    print("Test completed!")