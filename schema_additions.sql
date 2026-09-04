-- Additions to the existing SQLite schema:
-- 1. Review queue status on RFQs (instead of auto-submit)
-- 2. Submission audit trail linking solicitation -> RFQ -> vendor -> outcome

-- Add review status to existing rfqs table (adjust table name to match yours)
ALTER TABLE rfqs ADD COLUMN review_status TEXT DEFAULT 'pending_review';
-- values: 'pending_review' | 'approved' | 'rejected' | 'auto_rejected'
ALTER TABLE rfqs ADD COLUMN validation_issues TEXT;  -- JSON array from rfq_validator
ALTER TABLE rfqs ADD COLUMN reviewed_by TEXT;
ALTER TABLE rfqs ADD COLUMN reviewed_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS submission_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitation_id TEXT NOT NULL,
    rfq_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    vendor_name TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submission_method TEXT,          -- 'thomasnet_form', 'email', 'api'
    submission_status TEXT,          -- 'sent', 'failed', 'bounced'
    response_received_at TIMESTAMP,
    response_status TEXT,            -- 'quoted', 'declined', 'no_response'
    notes TEXT,
    FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
);

CREATE INDEX IF NOT EXISTS idx_submission_log_solicitation ON submission_log(solicitation_id);
CREATE INDEX IF NOT EXISTS idx_submission_log_rfq ON submission_log(rfq_id);
CREATE INDEX IF NOT EXISTS idx_rfqs_review_status ON rfqs(review_status);

-- Quick view for the dashboard's "pending review" queue
CREATE VIEW IF NOT EXISTS v_pending_review AS
SELECT id, solicitation_id, title, review_status, validation_issues, created_at
FROM rfqs
WHERE review_status = 'pending_review'
ORDER BY created_at ASC;

-- Quick view for pipeline metrics (useful for the "sellable" story too)
CREATE VIEW IF NOT EXISTS v_pipeline_metrics AS
SELECT
    (SELECT COUNT(*) FROM rfqs) AS total_rfqs,
    (SELECT COUNT(*) FROM rfqs WHERE review_status = 'approved') AS approved_rfqs,
    (SELECT COUNT(*) FROM rfqs WHERE review_status = 'pending_review') AS pending_rfqs,
    (SELECT COUNT(*) FROM rfqs WHERE review_status = 'auto_rejected') AS rejected_rfqs,
    (SELECT COUNT(*) FROM submission_log) AS total_submissions,
    (SELECT COUNT(*) FROM submission_log WHERE response_status = 'quoted') AS quotes_received;