"""
Authentication API Endpoints
User registration, login, and token management
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import Tenant, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    User registration endpoint.

    Request JSON:
    {
        "tenant_slug": "company-name",
        "tenant_name": "Company Name",
        "email": "user@example.com",
        "password": "secure_password",
        "full_name": "Full Name"
    }

    Returns:
        JSON with user and tenant details
    """
    try:
        data = request.get_json()

        if not all([data.get('tenant_slug'), data.get('tenant_name'),
                   data.get('email'), data.get('password')]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check if tenant already exists
        existing_tenant = Tenant.query.filter_by(slug=data['tenant_slug']).first()
        if existing_tenant:
            return jsonify({'error': 'Tenant slug already exists'}), 409

        # Check if user email already exists in any tenant (globally unique)
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'Email already registered'}), 409

        # Create tenant
        tenant = Tenant(
            slug=data['tenant_slug'],
            name=data['tenant_name'],
            subscription_tier='basic',  # Default to basic tier
            status='active',
            settings={
                'features': {
                    'automation_enabled': True,
                    'email_outreach': True,
                    'thomasnet_submission': True,
                    'vendor_extraction': True,
                    'batch_processing': False,
                    'api_access': False,
                    'white_label': False
                },
                'automation_defaults': {
                    'search_keywords': ['procurement', 'supplies'],
                    'max_vendors_per_product': 5,
                    'submission_method': 'both',
                    'llm_provider': 'gemini'
                },
                'limits': {
                    'automations_per_month': 10,
                    'rfqs_per_month': 100,
                    'vendors_per_rfq': 10
                },
                'usage': {
                    'automations_this_month': 0,
                    'rfqs_this_month': 0,
                    'submissions_this_month': 0
                }
            }
        )
        db.session.add(tenant)
        db.session.flush()  # Get tenant ID before creating user

        # Create user (admin of new tenant)
        user = User(
            tenant_id=tenant.id,
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            full_name=data.get('full_name'),
            role='admin',  # First user is admin
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        logger.info(
            f"New tenant and user created",
            extra={
                'tenant_id': tenant.id,
                'user_id': user.id,
                'tenant_slug': tenant.slug
            }
        )

        # Generate tokens
        access_token = create_access_token(identity={
            'tenant_id': tenant.id,
            'user_id': user.id,
            'role': user.role
        })
        refresh_token = create_refresh_token(identity={
            'tenant_id': tenant.id,
            'user_id': user.id,
            'role': user.role
        })

        return jsonify({
            'tenant': {
                'id': tenant.id,
                'slug': tenant.slug,
                'name': tenant.name
            },
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role
            },
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer'
            }
        }), 201

    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        return jsonify({'error': 'Signup failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login endpoint.

    Request JSON:
    {
        "email": "user@example.com",
        "password": "password"
    }

    Returns:
        JSON with access and refresh tokens
    """
    try:
        data = request.get_json()

        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Missing email or password'}), 400

        # Find user by email
        user = User.query.filter_by(email=data['email']).first()

        if not user or not check_password_hash(user.password_hash, data['password']):
            logger.warning(f"Failed login attempt for email: {data['email']}")
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'User account is inactive'}), 403

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        logger.info(
            f"User logged in",
            extra={
                'tenant_id': user.tenant_id,
                'user_id': user.id
            }
        )

        # Generate tokens
        access_token = create_access_token(identity={
            'tenant_id': user.tenant_id,
            'user_id': user.id,
            'role': user.role
        })
        refresh_token = create_refresh_token(identity={
            'tenant_id': user.tenant_id,
            'user_id': user.id,
            'role': user.role
        })

        # Get tenant
        tenant = Tenant.query.get(user.tenant_id)

        return jsonify({
            'tenant': {
                'id': tenant.id,
                'slug': tenant.slug,
                'name': tenant.name,
                'subscription_tier': tenant.subscription_tier
            },
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role
            },
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer'
            }
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token.

    Returns:
        JSON with new access token
    """
    try:
        claims = get_jwt_identity()

        # Generate new access token
        access_token = create_access_token(identity={
            'tenant_id': claims['tenant_id'],
            'user_id': claims['user_id'],
            'role': claims['role']
        })

        logger.info(
            f"Token refreshed",
            extra={
                'tenant_id': claims['tenant_id'],
                'user_id': claims['user_id']
            }
        )

        return jsonify({
            'access_token': access_token,
            'token_type': 'Bearer'
        }), 200

    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current authenticated user details.

    Returns:
        JSON with user and tenant information
    """
    try:
        claims = get_jwt_identity()

        user = User.query.filter_by(
            id=claims['user_id'],
            tenant_id=claims['tenant_id']
        ).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        tenant = Tenant.query.get(claims['tenant_id'])

        return jsonify({
            'tenant': {
                'id': tenant.id,
                'slug': tenant.slug,
                'name': tenant.name,
                'subscription_tier': tenant.subscription_tier,
                'status': tenant.status
            },
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        }), 200

    except Exception as e:
        logger.error(f"Get user error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get user'}), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout endpoint (primarily for client-side cleanup).

    Returns:
        JSON with logout confirmation
    """
    try:
        claims = get_jwt_identity()

        logger.info(
            f"User logged out",
            extra={
                'tenant_id': claims['tenant_id'],
                'user_id': claims['user_id']
            }
        )

        # Client should discard tokens on logout
        return jsonify({
            'message': 'Logged out successfully'
        }), 200

    except Exception as e:
        logger.error(f"Logout error: {e}", exc_info=True)
        return jsonify({'error': 'Logout failed'}), 500
