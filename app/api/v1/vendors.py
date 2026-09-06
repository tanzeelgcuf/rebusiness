"""
Vendors API Endpoints
List, view, and manage vendor contacts
"""

from flask import Blueprint, jsonify, request, g
from app import db
from app.models import Vendor
from app.auth.tenant_auth import tenant_required
import logging

logger = logging.getLogger(__name__)

vendors_bp = Blueprint('vendors', __name__, url_prefix='/vendors')


@vendors_bp.route('', methods=['GET'])
@tenant_required
def list_vendors():
    """
    Get paginated list of vendors for the tenant.

    Query Parameters:
        page: Page number (default: 1)
        limit: Results per page (default: 20)
        contract_id: Filter by contract ID
        email_status: Filter by email status (Ready, Sent, Bounced, Invalid)
        min_confidence: Filter by minimum confidence score

    Returns:
        JSON with paginated vendor list
    """
    try:
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)
        contract_id = request.args.get('contract_id')
        email_status = request.args.get('email_status')
        min_confidence = request.args.get('min_confidence', default=0, type=int)

        query = Vendor.query.filter_by(tenant_id=g.tenant_id)

        if contract_id:
            query = query.filter_by(contract_id=contract_id)

        if email_status:
            query = query.filter_by(email_status=email_status)

        if min_confidence > 0:
            query = query.filter(Vendor.confidence_score >= min_confidence)

        # Paginate
        paginated = query.order_by(Vendor.created_at.desc()).paginate(
            page=page,
            per_page=limit
        )

        response = {
            'page': page,
            'per_page': limit,
            'total': paginated.total,
            'total_pages': paginated.pages,
            'vendors': []
        }

        for vendor in paginated.items:
            response['vendors'].append({
                'vendor_id': vendor.id,
                'contract_id': vendor.contract_id,
                'name': vendor.name,
                'website': vendor.website,
                'email': vendor.email,
                'phone': vendor.phone,
                'location': vendor.location,
                'confidence_score': vendor.confidence_score,
                'email_status': vendor.email_status,
                'created_at': vendor.created_at.isoformat()
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to list vendors: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@vendors_bp.route('/<int:vendor_id>', methods=['GET'])
@tenant_required
def get_vendor(vendor_id):
    """
    Get details of a specific vendor.

    Args:
        vendor_id: Vendor ID

    Returns:
        JSON with full vendor details
    """
    try:
        vendor = Vendor.query.filter_by(
            id=vendor_id,
            tenant_id=g.tenant_id
        ).first()

        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404

        response = {
            'vendor_id': vendor.id,
            'contract_id': vendor.contract_id,
            'name': vendor.name,
            'website': vendor.website,
            'email': vendor.email,
            'phone': vendor.phone,
            'location': vendor.location,
            'confidence_score': vendor.confidence_score,
            'email_status': vendor.email_status,
            'created_at': vendor.created_at.isoformat()
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get vendor: {e}",
            extra={'tenant_id': g.tenant_id, 'vendor_id': vendor_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@vendors_bp.route('/<int:vendor_id>', methods=['PATCH'])
@tenant_required
def update_vendor(vendor_id):
    """
    Update vendor details (email status, contact info, etc).

    Args:
        vendor_id: Vendor ID

    Returns:
        JSON with updated vendor details
    """
    try:
        vendor = Vendor.query.filter_by(
            id=vendor_id,
            tenant_id=g.tenant_id
        ).first()

        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404

        data = request.get_json() or {}

        # Update allowed fields
        if 'email_status' in data:
            vendor.email_status = data['email_status']
        if 'email' in data:
            vendor.email = data['email']
        if 'phone' in data:
            vendor.phone = data['phone']
        if 'confidence_score' in data:
            vendor.confidence_score = data['confidence_score']

        db.session.commit()

        logger.info(
            f"Vendor updated",
            extra={'tenant_id': g.tenant_id, 'vendor_id': vendor_id}
        )

        response = {
            'vendor_id': vendor.id,
            'contract_id': vendor.contract_id,
            'name': vendor.name,
            'website': vendor.website,
            'email': vendor.email,
            'phone': vendor.phone,
            'location': vendor.location,
            'confidence_score': vendor.confidence_score,
            'email_status': vendor.email_status,
            'created_at': vendor.created_at.isoformat()
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to update vendor: {e}",
            extra={'tenant_id': g.tenant_id, 'vendor_id': vendor_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@vendors_bp.route('/by-contract/<contract_id>', methods=['GET'])
@tenant_required
def list_vendors_by_contract(contract_id):
    """
    Get all vendors for a specific contract/solicitation.

    Args:
        contract_id: SAM.gov contract ID

    Returns:
        JSON with vendor list
    """
    try:
        vendors = Vendor.query.filter_by(
            contract_id=contract_id,
            tenant_id=g.tenant_id
        ).all()

        response = {
            'contract_id': contract_id,
            'total': len(vendors),
            'vendors': []
        }

        for vendor in vendors:
            response['vendors'].append({
                'vendor_id': vendor.id,
                'name': vendor.name,
                'website': vendor.website,
                'email': vendor.email,
                'phone': vendor.phone,
                'location': vendor.location,
                'confidence_score': vendor.confidence_score,
                'email_status': vendor.email_status
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to list vendors by contract: {e}",
            extra={'tenant_id': g.tenant_id, 'contract_id': contract_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500
