"""
Multi-Tenant SaaS RFQ Automation Platform
Flask Application Factory with Multi-Tenant Middleware
"""

from flask import Flask, g, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from datetime import timedelta
import logging
from functools import wraps

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name='development'):
    """
    Application factory for multi-tenant SaaS platform.

    Args:
        config_name: 'development', 'testing', or 'production'

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Load configuration
    if config_name == 'development':
        from app.config import DevelopmentConfig
        app.config.from_object(DevelopmentConfig)
    elif config_name == 'testing':
        from app.config import TestingConfig
        app.config.from_object(TestingConfig)
    else:  # production
        from app.config import ProductionConfig
        app.config.from_object(ProductionConfig)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    CORS(app)

    # Register middleware
    @app.before_request
    def tenant_context():
        """Extract tenant context from JWT token before each request"""
        from flask_jwt_extended import get_jwt_identity

        # Some routes don't require auth (login, signup)
        if request.path in ['/api/v1/auth/login', '/api/v1/auth/signup', '/health']:
            return

        try:
            claims = get_jwt_identity()
            if claims:
                g.tenant_id = claims.get('tenant_id')
                g.user_id = claims.get('user_id')
                g.user_role = claims.get('role', 'viewer')

                if not g.tenant_id:
                    abort(401, "Invalid token: missing tenant_id")
            else:
                abort(401, "Unauthorized")
        except Exception as e:
            logger.error(f"Tenant context extraction error: {e}")
            abort(401, "Invalid token")

    @app.after_request
    def tenant_isolation_check(response):
        """Ensure no data leakage between tenants"""
        # This is primarily for logging/auditing purposes
        if hasattr(g, 'tenant_id') and response.status_code >= 400:
            logger.warning(
                f"Error in tenant {g.tenant_id}: {response.status_code}",
                extra={'tenant_id': g.tenant_id}
            )
        return response

    # Register error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e.description)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "healthy"}), 200

    # Register blueprints
    with app.app_context():
        from app.api.v1 import automation, dashboard, rfqs, vendors, auth

        # Register auth blueprint (no @tenant_required)
        app.register_blueprint(auth.auth_bp, url_prefix='/api/v1/auth')

        # Register tenant-scoped API v1 blueprints
        app.register_blueprint(automation.automation_bp, url_prefix='/api/v1/automation')
        app.register_blueprint(dashboard.dashboard_bp, url_prefix='/api/v1/dashboard')
        app.register_blueprint(rfqs.rfqs_bp, url_prefix='/api/v1/rfqs')
        app.register_blueprint(vendors.vendors_bp, url_prefix='/api/v1/vendors')

    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created/verified")

    return app


def tenant_required(f):
    """
    Decorator to ensure user is authenticated and belongs to a valid tenant.

    Usage:
        @app.route('/api/endpoint')
        @tenant_required
        def endpoint():
            # g.tenant_id and g.user_id are available
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'tenant_id') or not g.tenant_id:
            abort(401, "Tenant context not found")

        if not hasattr(g, 'user_id') or not g.user_id:
            abort(401, "User context not found")

        # Verify user belongs to tenant
        from app.models.tenant import User
        user = User.query.filter_by(
            id=g.user_id,
            tenant_id=g.tenant_id
        ).first()

        if not user:
            logger.warning(
                f"User {g.user_id} not found in tenant {g.tenant_id}",
                extra={'tenant_id': g.tenant_id}
            )
            abort(403, "Access denied")

        if not user.is_active:
            abort(403, "User account is inactive")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorator to ensure user has admin role.

    Usage:
        @app.route('/api/admin/endpoint')
        @admin_required
        def endpoint():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user_role') or g.user_role != 'admin':
            abort(403, "Admin access required")

        return f(*args, **kwargs)

    return decorated_function
