"""
API v1 Blueprint Package
Multi-tenant REST API for RFQ automation platform
"""

from flask import Blueprint

# Create API v1 blueprint
api_v1_bp = Blueprint('api_v1', __name__)

# Import route handlers
from app.api.v1 import automation, dashboard, rfqs, vendors

# Register sub-blueprints
api_v1_bp.register_blueprint(automation.automation_bp)
api_v1_bp.register_blueprint(dashboard.dashboard_bp)
api_v1_bp.register_blueprint(rfqs.rfqs_bp)
api_v1_bp.register_blueprint(vendors.vendors_bp)
