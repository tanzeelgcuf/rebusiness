-- Database Migration: Add ThomasNet Vendor Tracking
-- Run this to add the new table for tracking vendor submissions

-- Create thomasnet_submissions table
CREATE TABLE IF NOT EXISTS thomasnet_submissions (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(255),
    rfq_file_path TEXT,
    vendor_name VARCHAR(500),
    vendor_company VARCHAR(500),
    vendor_location VARCHAR(500),
    product_searched VARCHAR(500),
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id) ON DELETE CASCADE
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_thomasnet_contract ON thomasnet_submissions(contract_id);
CREATE INDEX IF NOT EXISTS idx_thomasnet_timestamp ON thomasnet_submissions(submission_timestamp);
CREATE INDEX IF NOT EXISTS idx_thomasnet_vendor ON thomasnet_submissions(vendor_company);

-- Add indexes to existing tables for better dashboard performance
CREATE INDEX IF NOT EXISTS idx_rfq_contract ON rfq_outputs(contract_id);
CREATE INDEX IF NOT EXISTS idx_rfq_created ON rfq_outputs(created_at);
CREATE INDEX IF NOT EXISTS idx_solicitation_created ON solicitations(created_at);

-- View for dashboard statistics
CREATE OR REPLACE VIEW dashboard_stats AS
SELECT 
    (SELECT COUNT(*) FROM solicitations) as total_solicitations,
    (SELECT COUNT(*) FROM rfq_outputs) as total_rfqs,
    (SELECT COUNT(*) FROM thomasnet_submissions WHERE success = TRUE) as successful_submissions,
    (SELECT COUNT(DISTINCT vendor_company) FROM thomasnet_submissions) as unique_vendors,
    (SELECT COUNT(*) FROM solicitations WHERE created_at >= NOW() - INTERVAL '7 days') as solicitations_last_week,
    (SELECT COUNT(*) FROM rfq_outputs WHERE created_at >= NOW() - INTERVAL '7 days') as rfqs_last_week,
    (SELECT COUNT(*) FROM thomasnet_submissions WHERE submission_timestamp >= NOW() - INTERVAL '7 days') as submissions_last_week;

COMMENT ON TABLE thomasnet_submissions IS 'Tracks all vendor submissions made through ThomasNet automation';
COMMENT ON VIEW dashboard_stats IS 'Aggregated statistics for dashboard display';
