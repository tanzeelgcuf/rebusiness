"""
Automation API Endpoints
Single-click automation workflow orchestration
"""

from flask import Blueprint, jsonify, request, g
from app import db
from app.models import AutomationRun, AgentLoopLog, AuditLog
from app.auth.tenant_auth import tenant_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

automation_bp = Blueprint('automation', __name__, url_prefix='/automation')


@automation_bp.route('/start', methods=['POST'])
@tenant_required
def start_automation():
    """
    Single-click entry point to start RFQ automation workflow.

    Returns:
        JSON with automation_run_id for polling progress
    """
    try:
        # Parse request
        data = request.get_json() or {}

        # Create automation run record
        automation_run = AutomationRun(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            status='queued',
            results={}
        )
        db.session.add(automation_run)
        db.session.commit()

        logger.info(
            f"Automation started",
            extra={
                'tenant_id': g.tenant_id,
                'user_id': g.user_id,
                'run_id': automation_run.id
            }
        )

        # Create audit log
        audit_log = AuditLog(
            tenant_id=g.tenant_id,
            action='automation_started',
            resource_type='automation_run',
            resource_id=automation_run.id,
            details={'user_id': g.user_id}
        )
        db.session.add(audit_log)
        db.session.commit()

        # Queue background job (will implement Celery later)
        # For now, return run_id for polling
        # TODO: queue_automation_workflow.delay(automation_run.id, g.tenant_id)

        return jsonify({
            'run_id': automation_run.id,
            'status': 'queued',
            'created_at': automation_run.created_at.isoformat(),
            'message': 'Automation workflow queued. Poll /automation/{run_id} for progress.'
        }), 202

    except Exception as e:
        logger.error(
            f"Failed to start automation: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/<int:run_id>', methods=['GET'])
@tenant_required
def get_automation_status(run_id):
    """
    Get status and progress of an automation run.

    Args:
        run_id: Automation run ID

    Returns:
        JSON with status, progress, agent logs, and results
    """
    try:
        # Fetch automation run (scoped to tenant)
        automation_run = AutomationRun.query.filter_by(
            id=run_id,
            tenant_id=g.tenant_id
        ).first()

        if not automation_run:
            return jsonify({'error': 'Automation run not found'}), 404

        # Get agent logs for this run
        agent_logs = AgentLoopLog.query.filter_by(
            automation_run_id=run_id,
            tenant_id=g.tenant_id
        ).order_by(AgentLoopLog.created_at).all()

        # Calculate progress (1-5 steps)
        completed_steps = len([
            log for log in agent_logs
            if log.status == 'success'
        ])
        progress_percent = (completed_steps / 5) * 100

        # Build response
        response = {
            'run_id': automation_run.id,
            'status': automation_run.status,
            'progress_percent': progress_percent,
            'created_at': automation_run.created_at.isoformat(),
            'start_time': automation_run.start_time.isoformat() if automation_run.start_time else None,
            'end_time': automation_run.end_time.isoformat() if automation_run.end_time else None,
            'duration_seconds': automation_run.get_duration_seconds(),
            'results': automation_run.results,
            'error_message': automation_run.error_message,
            'agent_logs': []
        }

        # Add agent logs
        for log in agent_logs:
            response['agent_logs'].append({
                'agent_name': log.agent_name,
                'step_number': log.step_number,
                'status': log.status,
                'attempt_number': log.attempt_number,
                'retry_count_max': log.retry_count_max,
                'error_message': log.error_message,
                'start_time': log.start_time.isoformat() if log.start_time else None,
                'end_time': log.end_time.isoformat() if log.end_time else None,
                'duration_ms': log.get_duration_ms()
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get automation status: {e}",
            extra={'tenant_id': g.tenant_id, 'run_id': run_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/<int:run_id>/logs', methods=['GET'])
@tenant_required
def get_automation_logs(run_id):
    """
    Get detailed logs for an automation run (for real-time monitoring).

    Args:
        run_id: Automation run ID

    Returns:
        JSON with agent logs, optionally filtered by agent name or step
    """
    try:
        # Parse query parameters
        agent_name = request.args.get('agent')
        step_number = request.args.get('step', type=int)
        limit = request.args.get('limit', default=100, type=int)

        # Fetch logs (scoped to tenant)
        query = AgentLoopLog.query.filter_by(
            automation_run_id=run_id,
            tenant_id=g.tenant_id
        )

        if agent_name:
            query = query.filter_by(agent_name=agent_name)
        if step_number:
            query = query.filter_by(step_number=step_number)

        logs = query.order_by(AgentLoopLog.created_at.desc()).limit(limit).all()

        if not logs and not AutomationRun.query.filter_by(id=run_id, tenant_id=g.tenant_id).first():
            return jsonify({'error': 'Automation run not found'}), 404

        response = {
            'run_id': run_id,
            'logs': []
        }

        for log in logs:
            response['logs'].append({
                'log_id': log.id,
                'agent_name': log.agent_name,
                'step_number': log.step_number,
                'status': log.status,
                'attempt_number': log.attempt_number,
                'error_message': log.error_message,
                'log_output': log.log_output,
                'created_at': log.created_at.isoformat(),
                'start_time': log.start_time.isoformat() if log.start_time else None,
                'end_time': log.end_time.isoformat() if log.end_time else None
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get automation logs: {e}",
            extra={'tenant_id': g.tenant_id, 'run_id': run_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/<int:run_id>', methods=['DELETE'])
@tenant_required
def cancel_automation(run_id):
    """
    Cancel a running automation workflow.

    Args:
        run_id: Automation run ID

    Returns:
        JSON with cancellation status
    """
    try:
        automation_run = AutomationRun.query.filter_by(
            id=run_id,
            tenant_id=g.tenant_id
        ).first()

        if not automation_run:
            return jsonify({'error': 'Automation run not found'}), 404

        if automation_run.status not in ['queued', 'running']:
            return jsonify({'error': f'Cannot cancel automation in {automation_run.status} state'}), 400

        automation_run.status = 'paused'
        automation_run.end_time = datetime.utcnow()

        audit_log = AuditLog(
            tenant_id=g.tenant_id,
            action='automation_cancelled',
            resource_type='automation_run',
            resource_id=automation_run.id,
            details={'user_id': g.user_id}
        )
        db.session.add(audit_log)
        db.session.commit()

        logger.info(
            f"Automation cancelled",
            extra={'tenant_id': g.tenant_id, 'run_id': run_id}
        )

        return jsonify({
            'run_id': automation_run.id,
            'status': automation_run.status,
            'message': 'Automation workflow cancelled'
        }), 200

    except Exception as e:
        logger.error(
            f"Failed to cancel automation: {e}",
            extra={'tenant_id': g.tenant_id, 'run_id': run_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500


@automation_bp.route('/history', methods=['GET'])
@tenant_required
def get_automation_history():
    """
    Get history of all automation runs for the tenant.

    Returns:
        JSON with paginated list of automation runs
    """
    try:
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)
        status = request.args.get('status')  # Filter by status

        query = AutomationRun.query.filter_by(tenant_id=g.tenant_id)

        if status:
            query = query.filter_by(status=status)

        # Paginate
        paginated = query.order_by(AutomationRun.created_at.desc()).paginate(
            page=page,
            per_page=limit
        )

        response = {
            'page': page,
            'per_page': limit,
            'total': paginated.total,
            'total_pages': paginated.pages,
            'runs': []
        }

        for run in paginated.items:
            response['runs'].append({
                'run_id': run.id,
                'status': run.status,
                'created_at': run.created_at.isoformat(),
                'start_time': run.start_time.isoformat() if run.start_time else None,
                'end_time': run.end_time.isoformat() if run.end_time else None,
                'duration_seconds': run.get_duration_seconds(),
                'results': run.results
            })

        return jsonify(response), 200

    except Exception as e:
        logger.error(
            f"Failed to get automation history: {e}",
            extra={'tenant_id': g.tenant_id},
            exc_info=True
        )
        return jsonify({'error': str(e)}), 500
