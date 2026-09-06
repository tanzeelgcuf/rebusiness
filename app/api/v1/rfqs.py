"""
RFQs API Endpoints
List, view, and manage generated RFQ documents
"""

from flask import Blueprint, jsonify, request, g
from app import db
from app.models import RFQOutput, Solicitation
from app.auth.tenant_auth import tenant_required
import logging

logger = logging.getLogger(__name__)

rfqs_bp = Blueprint('rfqs', __name__, url_prefix='/rfqs')


@rfqs_bp.route('', methods=['GET'])
@tenant_required
def list_rfqs():
    """
    Get paginated list of RFQ outputs for the tenant.

    Query Parameters:
        page: Page number (default: 1)
        limit: Results per page (default: 20)
        status: Filter by status (sent, pending, draft)
        contract_id: Filter by contract ID

    Returns:
        JSON with paginated RFQ list
    """
    try:
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)
        status_filter = request.args.get('status')
        contract_id = request.args.get('contract_id')

        query = RFQOutput.query.filter_by(tenant_id=g.tenant_id)

        if status_filter == 'sent':
            query = query.filter_by(sent_to_vendor=True)
        elif status_filter == 'pending':
            query = query.filter_by(sent_to_vendor=False)

        if contract_id:
            query = query.filter_by(contract_id=contract_id)

        # Paginate
        paginated = query.order_by(RFQOutput.generated_date.desc()).paginate(
            page=page,
            per_page=limit
        )

        response = {
            'page': page,
            'per_page': limit,
            'total': paginated.total,
            'total_pages': paginated.pages,
            'rfqs': []
        }

        for rfq in paginated.items:
            response['rfqs'].append({
                'rfq_id': rfq.id,
                'contract_id': rfq.contract_id,
                'rfq_type': rfq.rfq_type,
                'format': rfq.format,
                'generated_date': rfq.generated_date.isoformat(),
                'sent_to_vendor': rfq.sent_to_vendor,
                'sent_date': rfq.sent_date.isoformat() if rfq.sent_date else None,
                'vendor_email_recipient': rfq.vendor_email_recipient,
                'content_length': len(rfq.rfq_content)
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to list RFQs: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@rfqs_bp.route('/<int:rfq_id>', methods=['GET'])
@tenant_required
def get_rfq(rfq_id):
    """
    Get details of a specific RFQ.

    Args:
        rfq_id: RFQ ID

    Returns:
        JSON with full RFQ details
    """
    try:
        rfq = RFQOutput.query.filter_by(
            id=rfq_id,
            tenant_id=g.tenant_id
        ).first()

        if not rfq:
            return jsonify({'error': 'RFQ not found'}), 404

        # Get associated solicitation
        solicitation = Solicitation.query.filter_by(
            contract_id=rfq.contract_id,
            tenant_id=g.tenant_id
        ).first()

        response = {
            'rfq_id': rfq.id,
            'contract_id': rfq.contract_id,
            'rfq_type': rfq.rfq_type,
            'format': rfq.format,
            'generated_date': rfq.generated_date.isoformat(),
            'sent_to_vendor': rfq.sent_to_vendor,
            'sent_date': rfq.sent_date.isoformat() if rfq.sent_date else None,
            'vendor_email_recipient': rfq.vendor_email_recipient,
            'content': rfq.rfq_content,
            'solicitation': {
                'contract_id': solicitation.contract_id,
                'title': solicitation.title,
                'description': solicitation.description,
                'location': solicitation.location
            } if solicitation else None
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get RFQ: {e}",
            extra={'tenant_id': g.tenant_id, 'rfq_id': rfq_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@rfqs_bp.route('/<int:rfq_id>/content', methods=['GET'])
@tenant_required
def get_rfq_content(rfq_id):
    """
    Get raw RFQ content (for download/display).

    Args:
        rfq_id: RFQ ID

    Returns:
        JSON with raw content
    """
    try:
        rfq = RFQOutput.query.filter_by(
            id=rfq_id,
            tenant_id=g.tenant_id
        ).first()

        if not rfq:
            return jsonify({'error': 'RFQ not found'}), 404

        return jsonify({
            'contract_id': rfq.contract_id,
            'rfq_type': rfq.rfq_type,
            'format': rfq.format,
            'content': rfq.rfq_content
        }), 200

    except Exception as e:
        logger.error(
            f"Failed to get RFQ content: {e}",
            extra={'tenant_id': g.tenant_id, 'rfq_id': rfq_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@rfqs_bp.route('/by-contract/<contract_id>', methods=['GET'])
@tenant_required
def get_rfq_by_contract(contract_id):
    """
    Get RFQ by contract ID.

    Args:
        contract_id: SAM.gov contract ID

    Returns:
        JSON with RFQ details
    """
    try:
        rfq = RFQOutput.query.filter_by(
            contract_id=contract_id,
            tenant_id=g.tenant_id
        ).first()

        if not rfq:
            return jsonify({'error': 'RFQ not found for this contract'}), 404

        return jsonify({
            'rfq_id': rfq.id,
            'contract_id': rfq.contract_id,
            'rfq_type': rfq.rfq_type,
            'format': rfq.format,
            'generated_date': rfq.generated_date.isoformat(),
            'sent_to_vendor': rfq.sent_to_vendor,
            'sent_date': rfq.sent_date.isoformat() if rfq.sent_date else None,
            'vendor_email_recipient': rfq.vendor_email_recipient
        }), 200

    except Exception as e:
        logger.error(
            f"Failed to get RFQ by contract: {e}",
            extra={'tenant_id': g.tenant_id, 'contract_id': contract_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500
