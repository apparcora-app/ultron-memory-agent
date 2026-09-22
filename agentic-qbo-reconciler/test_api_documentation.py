#!/usr/bin/env python3
"""Test script to verify API documentation and endpoints."""

import requests
import json
from pathlib import Path

def test_api_documentation():
    """Test the API documentation endpoint."""
    # Test the root endpoint
    response = requests.get('http://localhost:8000/')
    
    if response.status_code == 200:
        print("✅ Root endpoint test passed!")
        print(f"Response: {response.text}")
    else:
        print(f"❌ Root endpoint test failed!")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

def test_api_docs():
    """Test the API documentation endpoint."""
    # Test the API documentation endpoint
    response = requests.get('http://localhost:8000/docs')
    
    if response.status_code == 200:
        print("✅ API documentation test passed!")
        print(f"Response length: {len(response.text)} characters")
        
        # Check if the response contains key API documentation elements
        if 'reconcile' in response.text.lower():
            print("✅ API documentation contains 'reconcile' endpoint")
        else:
            print("⚠️  API documentation may not contain 'reconcile' endpoint")
            
        if 'openapi' in response.text.lower():
            print("✅ API documentation contains OpenAPI specification")
        else:
            print("⚠️  API documentation may not contain OpenAPI specification")
            
    else:
        print(f"❌ API documentation test failed!")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

def test_qbo_mock_endpoint():
    """Test the QBO mock endpoint."""
    response = requests.get('http://localhost:8000/qbo-mock')
    
    if response.status_code == 200:
        qbo_data = response.json()
        print("✅ QBO mock endpoint test passed!")
        print(f"Response length: {len(qbo_data)} transactions")
        
        # Check if the response contains expected fields
        if qbo_data and isinstance(qbo_data, list):
            print("✅ Response is a list")
            
            if qbo_data and isinstance(qbo_data[0], dict):
                print("✅ Response items are dictionaries")
                
                # Check for expected fields
                expected_fields = ['id', 'date', 'amount', 'description']
                for field in expected_fields:
                    if field in qbo_data[0]:
                        print(f"✅ Response contains '{field}' field")
                    else:
                        print(f"⚠️  Response may not contain '{field}' field")
                        
        else:
            print("⚠️  Response may not be in expected format")
            
    else:
        print(f"❌ QBO mock endpoint test failed!")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == '__main__':
    print("Testing Agentic QBO Reconciler API Documentation...")
    print("=" * 50)
    
    # Test the root endpoint
    test_api_documentation()
    print("\n" + "=" * 50)
    
    # Test the API documentation endpoint
    test_api_docs()
    print("\n" + "=" * 50)
    
    # Test the QBO mock endpoint
    test_qbo_mock_endpoint()
    
    print("\n" + "=" * 50)
    print("Test completed!")