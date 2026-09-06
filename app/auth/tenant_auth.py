"""
Tenant Authentication & Authorization
Multi-tenant JWT handling and access control
"""

from functools import wraps
from flask import g, abort, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import User
import logging

logger = logging.getLogger(__name__)


def tenant_required(f):
    """
    Decorator to enforce tenant context and authorization.

    Requirements:
    - Valid JWT token in Authorization header
    - Token must contain tenant_id and user_id
    - User must exist and belong to tenant
    - User must be active

    Usage:
        @app.route('/api/v1/endpoint')
        @tenant_required
        def endpoint():
            # g.tenant_id and g.user_id are available
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verify JWT exists and is valid
            verify_jwt_in_request()

            # Extract claims
            claims = get_jwt_identity()

            if not isinstance(claims, dict):
                logger.warning("Invalid JWT format: claims not a dict")
                abort(401, "Invalid token format")

            # Extract tenant and user IDs
            tenant_id = claims.get('tenant_id')
            user_id = claims.get('user_id')

            if not tenant_id or not user_id:
                logger.warning("Missing tenant_id or user_id in JWT claims")
                abort(401, "Invalid token: missing tenant or user context")

            # Verify user exists and belongs to tenant
            user = User.query.filter_by(
                id=user_id,
                tenant_id=tenant_id
            ).first()

            if not user:
                logger.warning(
                    f"User {user_id} not found in tenant {tenant_id}"
                )
                abort(403, "Access denied: user not in tenant")

            if not user.is_active:
                logger.warning(
                    f"User {user_id} is inactive in tenant {tenant_id}"
                )
                abort(403, "Access denied: user account inactive")

            # Store in g for request context
            g.tenant_id = tenant_id
            g.user_id = user_id
            g.user_role = claims.get('role', 'viewer')
            g.user = user

            return f(*args, **kwargs)

        except Exception as e:
            if hasattr(e, 'code') and e.code in [401, 403]:
                raise
            logger.error(f"Authorization error: {e}", exc_info=True)
            abort(401, "Unauthorized")

    return decorated_function


def admin_required(f):
    """
    Decorator to enforce admin role within a tenant.

    Requirements:
    - Must pass @tenant_required first
    - User role must be 'admin'

    Usage:
        @app.route('/api/v1/admin/endpoint')
        @admin_required
        @tenant_required
        def endpoint():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user_role') or g.user_role != 'admin':
            logger.warning(
                f"Non-admin access attempt by user {g.user_id}",
                extra={'tenant_id': g.tenant_id}
            )
            abort(403, "Admin access required")

        return f(*args, **kwargs)

    return decorated_function


def get_tenant_from_request():
    """
    Extract tenant ID from current request context.

    Returns:
        Integer tenant_id or None if not authenticated
    """
    return getattr(g, 'tenant_id', None)


def get_user_from_request():
    """
    Extract user ID from current request context.

    Returns:
        Integer user_id or None if not authenticated
    """
    return getattr(g, 'user_id', None)


def get_current_user():
    """
    Get current authenticated user object.

    Returns:
        User model instance or None
    """
    return getattr(g, 'user', None)


def scoped_query(query, model_class=None):
    """
    Scope a database query to current tenant.

    Args:
        query: SQLAlchemy query object
        model_class: Model class (for reference)

    Returns:
        Scoped query filtered to current tenant_id
    """
    tenant_id = get_tenant_from_request()
    if tenant_id and hasattr(query, 'filter_by'):
        return query.filter_by(tenant_id=tenant_id)
    return query
