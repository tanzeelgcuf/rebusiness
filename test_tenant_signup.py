#!/usr/bin/env python3
"""
Test tenant signup for SaaS platform.
Tests the signup endpoint with the provided credentials.
"""

import sys
import requests
import json

# Configuration
API_BASE_URL = "http://localhost:5000"
SIGNUP_ENDPOINT = f"{API_BASE_URL}/api/v1/auth/signup"

# Test data
TENANT_DATA = {
    "tenant_slug": "test-tenant-1",
    "tenant_name": "Test Tenant 1",
    "email": "tenant1@test.com",
    "password": "TestPass123!",
    "full_name": "Test User"
}


def test_signup():
    """
    Test the signup endpoint.

    Returns:
        dict: {success: bool, tenant_id: int|null, user_id: int|null,
               access_token: string|null, error: string|null}
    """
    try:
        print(f"Testing signup at {SIGNUP_ENDPOINT}")
        print(f"Payload: {json.dumps(TENANT_DATA, indent=2)}")

        response = requests.post(
            SIGNUP_ENDPOINT,
            json=TENANT_DATA,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 201:
            data = response.json()

            result = {
                "success": True,
                "tenant_id": data.get('tenant', {}).get('id'),
                "user_id": data.get('user', {}).get('id'),
                "access_token": data.get('tokens', {}).get('access_token'),
                "error": None
            }

            print(f"\nSignup successful!")
            print(f"Tenant ID: {result['tenant_id']}")
            print(f"User ID: {result['user_id']}")

            return result

        elif response.status_code == 409:
            # Conflict - entity already exists
            error_msg = response.json().get('error', 'Conflict')
            print(f"Conflict: {error_msg}")
            return {
                "success": False,
                "tenant_id": None,
                "user_id": None,
                "access_token": None,
                "error": error_msg
            }

        elif response.status_code == 400:
            # Bad request
            error_msg = response.json().get('error', 'Bad request')
            print(f"Bad Request: {error_msg}")
            return {
                "success": False,
                "tenant_id": None,
                "user_id": None,
                "access_token": None,
                "error": error_msg
            }

        else:
            # Other error
            error_msg = response.json().get('error', f'HTTP {response.status_code}')
            print(f"Error: {error_msg}")
            return {
                "success": False,
                "tenant_id": None,
                "user_id": None,
                "access_token": None,
                "error": error_msg
            }

    except requests.exceptions.ConnectionError as e:
        error_msg = "Could not connect to API server"
        print(f"Connection Error: {error_msg}")
        return {
            "success": False,
            "tenant_id": None,
            "user_id": None,
            "access_token": None,
            "error": error_msg
        }

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        return {
            "success": False,
            "tenant_id": None,
            "user_id": None,
            "access_token": None,
            "error": error_msg
        }


if __name__ == "__main__":
    result = test_signup()
    print(f"\nFinal Result: {json.dumps(result, indent=2)}")
    sys.exit(0 if result['success'] else 1)
