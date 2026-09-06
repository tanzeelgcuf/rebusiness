"""
API v1 Package
Multi-tenant REST API endpoints
"""

from flask import Blueprint

# Create main API v1 blueprint
api_v1_bp = Blueprint('api_v1', __name__)

# Import route modules to register them
from app.api.v1 import automation, dashboard, rfqs, vendors

# Sub-blueprints are auto-registered via their own bp definitions
# which get registered in app/__init__.py
