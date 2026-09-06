"""
Dashboard API Endpoints
Tenant-specific statistics and overview
"""

from flask import Blueprint, jsonify, g
from app import db
from app.models import AutomationRun, RFQOutput, Vendor, Solicitation
from app.auth.tenant_auth import tenant_required
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/stats', methods=['GET'])
@tenant_required
def get_dashboard_stats():
    """
    Get dashboard overview statistics for the tenant.

    Returns:
        JSON with aggregated metrics
    """
    try:
        # Total automations
        total_automations = AutomationRun.query.filter_by(
            tenant_id=g.tenant_id
        ).count()

        completed_automations = AutomationRun.query.filter_by(
            tenant_id=g.tenant_id,
            status='completed'
        ).count()

        failed_automations = AutomationRun.query.filter_by(
            tenant_id=g.tenant_id,
            status='failed'
        ).count()

        # Total RFQs generated
        total_rfqs = RFQOutput.query.filter_by(
            tenant_id=g.tenant_id
        ).count()

        rfqs_sent = RFQOutput.query.filter_by(
            tenant_id=g.tenant_id,
            sent_to_vendor=True
        ).count()

        # Total vendors found
        total_vendors = Vendor.query.filter_by(
            tenant_id=g.tenant_id
        ).count()

        vendors_with_email = Vendor.query.filter_by(
            tenant_id=g.tenant_id
        ).filter(Vendor.email != None).count()

        # Total solicitations
        total_solicitations = Solicitation.query.filter_by(
            tenant_id=g.tenant_id
        ).count()

        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        recent_automations = AutomationRun.query.filter_by(
            tenant_id=g.tenant_id
        ).filter(AutomationRun.created_at >= seven_days_ago).count()

        recent_rfqs = RFQOutput.query.filter_by(
            tenant_id=g.tenant_id
        ).filter(RFQOutput.generated_date >= seven_days_ago).count()

        # Success rate
        success_rate = 0
        if total_automations > 0:
            success_rate = (completed_automations / total_automations) * 100

        response = {
            'automations': {
                'total': total_automations,
                'completed': completed_automations,
                'failed': failed_automations,
                'success_rate_percent': round(success_rate, 2)
            },
            'rfqs': {
                'total': total_rfqs,
                'sent': rfqs_sent
            },
            'vendors': {
                'total': total_vendors,
                'with_email': vendors_with_email
            },
            'solicitations': {
                'total': total_solicitations
            },
            'recent_activity': {
                'automations_7d': recent_automations,
                'rfqs_7d': recent_rfqs
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get dashboard stats: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/recent-runs', methods=['GET'])
@tenant_required
def get_recent_runs():
    """
    Get 5 most recent automation runs for dashboard summary.

    Returns:
        JSON with recent runs
    """
    try:
        recent_runs = AutomationRun.query.filter_by(
            tenant_id=g.tenant_id
        ).order_by(AutomationRun.created_at.desc()).limit(5).all()

        response = {
            'runs': []
        }

        for run in recent_runs:
            response['runs'].append({
                'run_id': run.id,
                'status': run.status,
                'created_at': run.created_at.isoformat(),
                'results': run.results
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get recent runs: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500
