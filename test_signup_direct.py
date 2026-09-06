#!/usr/bin/env python3
"""
Direct test of tenant signup using Flask test client.
This runs the app in memory without needing an external server.
"""

import sys
import os
sys.path.insert(0, '/Users/apple/Downloads/rebusinessautomationproject')

# Set testing environment
os.environ['FLASK_ENV'] = 'testing'

from app import create_app, db
from app.models import Tenant, User
import json

def test_signup():
    """
    Test the signup endpoint using Flask test client.

    Returns:
        dict: {success: bool, tenant_id: int|null, user_id: int|null,
               access_token: string|null, error: string|null}
    """
    try:
        # Create app with testing config (uses in-memory SQLite)
        app = create_app(config_name='testing')

        with app.app_context():
            # Create all tables
            db.create_all()

            # Create test client
            client = app.test_client()

            # Test data
            signup_data = {
                "tenant_slug": "test-tenant-1",
                "tenant_name": "Test Tenant 1",
                "email": "tenant1@test.com",
                "password": "TestPass123!",
                "full_name": "Test User"
            }

            print(f"Testing signup endpoint...")
            print(f"Payload: {json.dumps(signup_data, indent=2)}")

            # Make POST request to signup endpoint
            response = client.post(
                '/api/v1/auth/signup',
                json=signup_data,
                content_type='application/json'
            )

            print(f"Status Code: {response.status_code}")
            response_data = response.get_json()
            print(f"Response: {json.dumps(response_data, indent=2)}")

            if response.status_code == 201:
                # Success
                result = {
                    "success": True,
                    "tenant_id": response_data.get('tenant', {}).get('id'),
                    "user_id": response_data.get('user', {}).get('id'),
                    "access_token": response_data.get('tokens', {}).get('access_token'),
                    "error": None
                }

                print(f"\nSignup successful!")
                print(f"Tenant ID: {result['tenant_id']}")
                print(f"User ID: {result['user_id']}")
                print(f"Access Token: {result['access_token'][:50]}..." if result['access_token'] else "None")

                return result

            elif response.status_code == 409:
                # Conflict
                error_msg = response_data.get('error', 'Conflict')
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
                error_msg = response_data.get('error', 'Bad request')
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
                error_msg = response_data.get('error', f'HTTP {response.status_code}')
                print(f"Error: {error_msg}")
                return {
                    "success": False,
                    "tenant_id": None,
                    "user_id": None,
                    "access_token": None,
                    "error": error_msg
                }

    except Exception as e:
        error_msg = str(e)
        print(f"Exception: {error_msg}")
        import traceback
        traceback.print_exc()
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
