#!/usr/bin/env python3
"""
Schema migration script for the pipeline rebuild.

Applies schema_additions.sql to the existing SQLite database.
Handles idempotent execution (safe to run multiple times).
"""

import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "rebusiness_automation.db"
SCHEMA_FILE = "schema_additions.sql"


def execute_migration():
    """Execute all SQL statements from schema_additions.sql."""
    if not os.path.exists(SCHEMA_FILE):
        logger.error(f"Schema file not found: {SCHEMA_FILE}")
        return False

    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found: {DB_PATH}")
        return False

    # Read and parse SQL file
    with open(SCHEMA_FILE, 'r') as f:
        sql_content = f.read()

    # Split into individual statements (naive but works for our schema)
    # Remove comments and split by semicolon
    statements = []
    current = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--') or not stripped:
            continue
        current.append(line)
        if stripped.endswith(';'):
            statements.append('\n'.join(current).strip())
            current = []

    if current:
        statements.append('\n'.join(current).strip())

    logger.info(f"Found {len(statements)} SQL statements to execute")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, stmt in enumerate(statements, 1):
        try:
            logger.info(f"Executing statement {i}/{len(statements)}...")
            logger.debug(f"SQL: {stmt[:100]}...")
            cursor.execute(stmt)
            conn.commit()
            success_count += 1
            logger.info(f"  ✓ Statement {i} executed successfully")
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "duplicate column" in error_msg or "already exists" in error_msg:
                logger.info(f"  ⊘ Statement {i} skipped: {e}")
                skip_count += 1
            else:
                logger.error(f"  ✗ Statement {i} failed: {e}")
                error_count += 1
        except Exception as e:
            logger.error(f"  ✗ Statement {i} error: {e}")
            error_count += 1

    conn.close()

    logger.info(f"\n{'='*60}")
    logger.info(f"MIGRATION COMPLETE")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped (already exist): {skip_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"{'='*60}")

    return error_count == 0


def verify_migration():
    """Verify the migration created expected tables/columns/views."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    checks = [
        ("rfq_outputs.review_status column", "PRAGMA table_info(rfq_outputs)"),
        ("rfq_outputs.validation_issues column", "PRAGMA table_info(rfq_outputs)"),
        ("rfq_outputs.reviewed_by column", "PRAGMA table_info(rfq_outputs)"),
        ("rfq_outputs.reviewed_at column", "PRAGMA table_info(rfq_outputs)"),
        ("submission_log table", "SELECT name FROM sqlite_master WHERE type='table' AND name='submission_log'"),
        ("v_pending_review view", "SELECT name FROM sqlite_master WHERE type='view' AND name='v_pending_review'"),
        ("v_pipeline_metrics view", "SELECT name FROM sqlite_master WHERE type='view' AND name='v_pipeline_metrics'"),
    ]

    logger.info("\nVerifying migration...")
    all_ok = True

    for name, query in checks:
        try:
            cursor.execute(query)
            result = cursor.fetchall()
            if "table_info" in query:
                # Check for specific columns
                cols = [row['name'] for row in result]
                if name.split('.')[-1].split()[0] in cols:
                    logger.info(f"  ✓ {name}")
                else:
                    logger.warning(f"  ⚠ {name} - column not found in: {cols}")
                    all_ok = False
            else:
                if result:
                    logger.info(f"  ✓ {name}")
                else:
                    logger.warning(f"  ⚠ {name} - not found")
                    all_ok = False
        except Exception as e:
            logger.error(f"  ✗ {name} - check failed: {e}")
            all_ok = False

    conn.close()

    if all_ok:
        logger.info("\n✅ All migration checks passed!")
    else:
        logger.warning("\n⚠️ Some checks failed - review output above")

    return all_ok


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run schema migration for pipeline rebuild")
    parser.add_argument("--verify-only", action="store_true", help="Only verify, don't apply migration")
    args = parser.parse_args()

    if args.verify_only:
        verify_migration()
    else:
        success = execute_migration()
        if success:
            verify_migration()


if __name__ == "__main__":
    main()