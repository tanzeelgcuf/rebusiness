"""
Multi-Tenant Data Models
Database schema with tenant isolation
"""

from app import db
from datetime import datetime
import json
from sqlalchemy.dialects.sqlite import JSON


class Tenant(db.Model):
    """Represents a SaaS tenant (organization/workspace)"""
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)  # URL-safe identifier
    name = db.Column(db.String(255), nullable=False)
    subscription_tier = db.Column(
        db.String(20),
        default='basic',
        nullable=False
        # basic, pro, enterprise
    )
    status = db.Column(
        db.String(20),
        default='active',
        nullable=False
        # active, trial, suspended, canceled
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Settings stored as JSON
    # Includes: feature_flags, automation_defaults, limits, usage tracking
    settings = db.Column(JSON, default={}, nullable=False)

    # Relationships
    users = db.relationship('User', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    solicitations = db.relationship('Solicitation', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    rfqs = db.relationship('RFQOutput', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    vendors = db.relationship('Vendor', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    automation_runs = db.relationship('AutomationRun', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tenant {self.slug} ({self.subscription_tier})>'

    def get_settings(self):
        """Parse and return settings dict"""
        if isinstance(self.settings, str):
            return json.loads(self.settings)
        return self.settings or {}

    def set_settings(self, settings_dict):
        """Store settings as JSON"""
        self.settings = json.dumps(settings_dict) if isinstance(settings_dict, dict) else settings_dict
        db.session.commit()

    def get_feature_flag(self, feature_name, default=False):
        """Check if a feature is enabled for this tenant"""
        settings = self.get_settings()
        features = settings.get('features', {})
        return features.get(feature_name, default)

    def get_subscription_limit(self, limit_name):
        """Get subscription limit based on tier"""
        limits_by_tier = {
            'basic': {
                'automations_per_month': 10,
                'rfqs_per_month': 100,
                'vendors_per_rfq': 10,
                'max_retries': 2,
            },
            'pro': {
                'automations_per_month': 100,
                'rfqs_per_month': 1000,
                'vendors_per_rfq': 50,
                'max_retries': 3,
            },
            'enterprise': {
                'automations_per_month': 1000,
                'rfqs_per_month': 10000,
                'vendors_per_rfq': 500,
                'max_retries': 5,
            },
        }
        tier_limits = limits_by_tier.get(self.subscription_tier, limits_by_tier['basic'])
        return tier_limits.get(limit_name)


class User(db.Model):
    """Represents a user within a tenant"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=True)

    role = db.Column(
        db.String(20),
        default='procurement_manager',
        nullable=False
        # admin, procurement_manager, viewer
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Composite unique constraint: email unique per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'email', name='uq_tenant_email'),
    )

    # Relationships
    automation_runs = db.relationship('AutomationRun', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.email} (tenant: {self.tenant_id})>'


class AutomationRun(db.Model):
    """Represents a single automation execution"""
    __tablename__ = 'automation_runs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(
        db.String(20),
        default='queued',
        nullable=False
        # queued, running, completed, failed, paused
    )

    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    # Results stored as JSON: {solicitations: 5, rfqs_generated: 12, vendors_found: 47, submissions_sent: 235}
    results = db.Column(JSON, default={}, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    agent_logs = db.relationship('AgentLoopLog', backref='automation_run', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='automation_run', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<AutomationRun {self.id} ({self.status})>'

    def get_duration_seconds(self):
        """Get total duration of automation run"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds()
        return None


class AgentLoopLog(db.Model):
    """Logs for each agent step in automation workflow"""
    __tablename__ = 'agent_loop_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    automation_run_id = db.Column(db.Integer, db.ForeignKey('automation_runs.id'), nullable=False)

    agent_name = db.Column(
        db.String(50),
        nullable=False
        # SamGovAgent, RFQAgent, ParserAgent, VendorSearchAgent, SubmissionAgent
    )
    step_number = db.Column(db.Integer, nullable=False)  # 1-5

    status = db.Column(
        db.String(20),
        default='pending',
        nullable=False
        # pending, running, success, retry, failed
    )

    attempt_number = db.Column(db.Integer, default=1, nullable=False)
    retry_count_max = db.Column(db.Integer, nullable=False)  # Based on subscription tier

    error_message = db.Column(db.Text, nullable=True)
    log_output = db.Column(db.Text, nullable=True)  # Detailed agent logs

    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    next_retry_at = db.Column(db.DateTime, nullable=True)  # For backoff scheduling

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AgentLoopLog {self.agent_name}:{self.step_number} ({self.status})>'

    def get_duration_ms(self):
        """Get duration in milliseconds"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None


class AuditLog(db.Model):
    """Audit trail for all important actions"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    action = db.Column(db.String(100), nullable=False)  # automation_started, vendors_found, submission_sent, etc
    resource_type = db.Column(db.String(50), nullable=True)  # automation_run, rfq, vendor
    resource_id = db.Column(db.Integer, nullable=True)

    details = db.Column(JSON, default={}, nullable=False)  # Additional context

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AuditLog {self.action} ({self.resource_type})>'


# Extended existing models with tenant_id

class Solicitation(db.Model):
    """Solicitation from SAM.gov (modified for multi-tenancy)"""
    __tablename__ = 'solicitations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    contract_id = db.Column(db.String(100), nullable=False)
    url = db.Column(db.Text, unique=False, nullable=False)  # Removed unique to allow same URL per tenant
    title = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)

    analysis_summary = db.Column(db.Text, nullable=True)
    data = db.Column(JSON, nullable=True)

    review_status = db.Column(db.String(50), default='pending')
    extraction_confidence = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Composite unique per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'contract_id', name='uq_tenant_contract_id'),
    )

    def __repr__(self):
        return f'<Solicitation {self.contract_id} (tenant: {self.tenant_id})>'


class RFQOutput(db.Model):
    """Generated RFQ documents (modified for multi-tenancy)"""
    __tablename__ = 'rfq_outputs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    contract_id = db.Column(db.String(100), nullable=False)
    rfq_type = db.Column(db.String(20), nullable=False)  # PRODUCT or SERVICE
    rfq_content = db.Column(db.Text, nullable=False)
    format = db.Column(db.String(20), default='markdown')

    generated_date = db.Column(db.DateTime, default=datetime.utcnow)
    sent_to_vendor = db.Column(db.Boolean, default=False)
    vendor_email_recipient = db.Column(db.String(255), nullable=True)
    sent_date = db.Column(db.DateTime, nullable=True)

    # Composite unique per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'contract_id', name='uq_tenant_rfq_contract'),
    )

    def __repr__(self):
        return f'<RFQOutput {self.contract_id} ({self.rfq_type})>'


class Vendor(db.Model):
    """Vendor from ThomasNet (modified for multi-tenancy)"""
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    contract_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    website = db.Column(db.String(500), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    confidence_score = db.Column(db.Integer, default=0)
    location = db.Column(db.String(255), nullable=True)

    email_status = db.Column(db.String(50), default='Ready')  # Ready, Sent, Bounced, Invalid

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Vendor {self.name} (tenant: {self.tenant_id})>'


# =============================================================================
# SAM.gov Integration Models
# =============================================================================


class SamGovCredentials(db.Model):
    """
    Tenant-specific SAM.gov API credentials.
    API key is encrypted at rest using Fernet (AES-128-CBC + HMAC).
    """
    __tablename__ = 'sam_gov_credentials'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )

    # Encrypted API key (never expose in API responses)
    api_key_encrypted = db.Column(db.Text, nullable=False)
    entity_id = db.Column(db.String(128), nullable=False)

    # Display fields (safe to expose)
    api_key_last4 = db.Column(db.String(4), nullable=True)

    # Connection state
    connection_status = db.Column(
        db.String(20),
        default='disconnected',
        nullable=False,
        # disconnected, connected, syncing, error, rate_limited
    )
    last_test_at = db.Column(db.DateTime, nullable=True)
    last_test_success = db.Column(db.Boolean, nullable=True)
    last_test_error = db.Column(db.Text, nullable=True)

    # Sync stats
    last_sync_at = db.Column(db.DateTime, nullable=True)
    sync_count = db.Column(db.Integer, default=0, nullable=False)

    # Rate limit info (from SAM.gov response headers)
    rate_limit_remaining = db.Column(db.Integer, nullable=True)
    rate_limit_reset_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship
    sync_history = db.relationship(
        'SamGovSyncHistory', backref='credentials', lazy='dynamic', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<SamGovCredentials tenant={self.tenant_id} status={self.connection_status}>'

    def to_dict(self):
        """Safe dict for API responses (no secrets)."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'entity_id': self.entity_id,
            'api_key_last4': self.api_key_last4,
            'connection_status': self.connection_status,
            'last_test_at': self.last_test_at.isoformat() if self.last_test_at else None,
            'last_test_success': self.last_test_success,
            'last_test_error': self.last_test_error if not self.last_test_success else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_count': self.sync_count,
        }


class SamGovSyncHistory(db.Model):
    """
    History of SAM.gov sync operations.
    Each sync records: start time, completion, solicitations fetched, errors.
    """
    __tablename__ = 'sam_gov_sync_history'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    credentials_id = db.Column(
        db.Integer,
        db.ForeignKey('sam_gov_credentials.id', ondelete='CASCADE'),
        nullable=False,
    )

    # Sync timing
    sync_started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sync_completed_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)

    # Sync state
    status = db.Column(
        db.String(20),
        default='running',
        nullable=False,
        # running, success, failed
    )
    solicitations_fetched = db.Column(db.Integer, default=0, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<SamGovSyncHistory {self.id} ({self.status})>'
