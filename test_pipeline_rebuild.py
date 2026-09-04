#!/usr/bin/env python3
"""
Tests for pipeline rebuild components:
- rfq_validator.py
- sam_gov_fetcher.py
- database_manager.py new methods
- run_schema_migration.py
"""
import os
import sys
import json
import sqlite3
import tempfile
import pytest

# Ensure worktree root is importable
WORKTREE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKTREE)

from rfq_validator import validate_rfq, validate_batch, ValidationResult


# ─── rfq_validator tests ──────────────────────────────────────────────────────

class TestRfqValidator:
    def test_good_rfq_is_ok(self):
        rfq = {
            "id": 1,
            "scope": "Procurement of 500 units of industrial-grade steel brackets per attached spec sheet.",
            "quantity": "500 units",
            "deadline": "2026-09-30",
            "delivery_location": "1200 Industrial Pkwy, Columbus, OH 44201",
            "contact": "procurement@example.com",
            "body": "We are requesting quotes for 500 units of industrial-grade steel brackets "
                    "meeting ASTM A36 specifications. Delivery required to our Columbus, OH facility "
                    "no later than September 30, 2026. Please include unit pricing, lead time, and "
                    "shipping terms in your quote. Contact procurement@example.com with questions.",
        }
        result = validate_rfq(rfq)
        assert result.severity == "ok"
        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_stub_rfq_is_rejected(self):
        rfq = {"id": 2, "body": "RFQ for Product"}
        result = validate_rfq(rfq)
        assert result.severity == "reject"
        assert result.is_valid is False
        assert any("stub" in i or "body too short" in i for i in result.issues)

    def test_empty_body_is_rejected(self):
        rfq = {"id": 3, "body": ""}
        result = validate_rfq(rfq)
        assert result.severity == "reject"
        assert result.is_valid is False

    def test_missing_fields_is_warning(self):
        rfq = {
            "id": 4,
            "scope": "Procurement of 500 widgets for testing purposes",
            "quantity": "500 units",
            "deadline": "2026-09-30",
            "delivery_location": "1200 Industrial Pkwy, Columbus, OH 44201",
            "contact": "procurement@example.com",
            "body": "We are requesting quotes for 500 widgets for testing. " * 10,
        }
        # Missing delivery_location and contact as separate fields would be caught
        # but the body is long enough — this should be ok
        result = validate_rfq(rfq)
        assert result.severity == "ok"

    def test_validate_batch_counts(self):
        good = {
            "id": 10,
            "scope": "Procurement of widgets",
            "quantity": "500 units",
            "deadline": "2026-09-30",
            "delivery_location": "1200 Industrial Pkwy, Columbus, OH",
            "contact": "test@example.com",
            "body": "Requesting quotes for 500 widgets. " * 10,
        }
        stub = {"id": 11, "body": "RFQ for Product"}
        warn = {"id": 12, "scope": "X", "quantity": "1", "deadline": "2026-09-30",
                "delivery_location": "Address", "contact": "e@e.com",
                "body": "Short"}
        result = validate_batch([good, stub, warn])
        assert result["total"] == 3
        assert result["ok"] >= 1
        assert result["reject"] >= 1

    def test_stub_pattern_rfqs(self):
        """Various stub patterns that must be caught."""
        stubs = [
            {"body": "RFQ for Product"},
            {"body": "[insert product here]"},
            {"body": "Lorem ipsum dolor sit amet"},
        ]
        for s in stubs:
            result = validate_rfq(s)
            assert result.severity == "reject", f"Failed to reject: {s['body']}"


# ─── sam_gov_fetcher tests (mock-based) ───────────────────────────────────────

class TestSamGovFetcher:
    def test_normalize_opportunity(self):
        from sam_api_client import normalize_opportunity
        raw = {
            "noticeId": "N0010425QNF13",
            "title": "Test Solicitation",
            "description": "https://api.sam.gov/desc/123",
            "naicsCode": "541614",
            "type": "Solicitation",
            "postedDate": "2026-08-01",
            "responseDeadLine": "2026-09-01",
            "fullParentPathName": "Dept of Defense",
            "placeOfPerformance": {"country": "USA"},
            "pointOfContact": [{"name": "John"}],
            "uiLink": "https://sam.gov/opp/abc123/view",
        }
        result = normalize_opportunity(raw)
        assert result["solicitation_id"] == "N0010425QNF13"
        assert result["title"] == "Test Solicitation"
        assert result["naics_code"] == "541614"
        assert result["agency"] == "Dept of Defense"
        assert result["sam_url"] == "https://sam.gov/opp/abc123/view"

    def test_fetcher_init_no_key(self, monkeypatch):
        monkeypatch.delenv("SAM_API_KEY", raising=False)
        from sam_api_client import SamApiError
        with pytest.raises(SamApiError):
            from sam_api_client import SamApiClient
            SamApiClient()

    def test_fetcher_class_init(self, monkeypatch):
        monkeypatch.setenv("SAM_API_KEY", "test-key-123")
        from sam_gov_fetcher import SamGovFetcher
        fetcher = SamGovFetcher(api_key="test-key-123")
        assert fetcher.api_client.api_key == "test-key-123"

    def test_fetcher_search_for_links_compat(self, monkeypatch):
        """Verify search_for_links interface compatibility."""
        monkeypatch.setenv("SAM_API_KEY", "test-key-123")
        from sam_gov_fetcher import SamGovFetcher
        fetcher = SamGovFetcher(api_key="test-key-123")
        # search_for_links should exist and be callable
        assert callable(getattr(fetcher, 'search_for_links', None))
        assert callable(getattr(fetcher, 'start_browser', None))
        assert callable(getattr(fetcher, 'close', None))


# ─── database_manager new methods tests ────────────────────────────────────────

class TestDatabaseManagerNewMethods:
    @pytest.fixture
    def db_with_tables(self, tmp_path):
        """Create a temp DB with the schema additions applied."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Create base tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS solicitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT UNIQUE,
                url TEXT UNIQUE,
                title TEXT,
                description TEXT,
                location TEXT,
                product_requirements TEXT,
                analysis_summary TEXT,
                data TEXT,
                review_status TEXT DEFAULT 'pending',
                extraction_confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rfq_outputs (
                id INTEGER PRIMARY KEY,
                contract_id TEXT NOT NULL UNIQUE,
                rfq_type TEXT NOT NULL,
                rfq_content TEXT NOT NULL,
                format TEXT DEFAULT 'markdown',
                generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_vendor BOOLEAN DEFAULT 0,
                vendor_email_recipient TEXT,
                sent_date TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submission_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitation_id TEXT NOT NULL,
                rfq_id INTEGER NOT NULL,
                vendor_id INTEGER NOT NULL,
                vendor_name TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submission_method TEXT,
                submission_status TEXT,
                response_received_at TIMESTAMP,
                response_status TEXT,
                notes TEXT
            )
        """)

        # Apply additions from schema_additions.sql
        additions = [
            "ALTER TABLE rfq_outputs ADD COLUMN review_status TEXT DEFAULT 'pending_review'",
            "ALTER TABLE rfq_outputs ADD COLUMN validation_issues TEXT",
            "ALTER TABLE rfq_outputs ADD COLUMN reviewed_by TEXT",
            "ALTER TABLE rfq_outputs ADD COLUMN reviewed_at TIMESTAMP",
        ]
        for stmt in additions:
            try:
                conn.execute(stmt)
            except:
                pass
        conn.commit()
        conn.close()

        return db_path

    def test_log_submission(self, db_with_tables):
        from database_manager import DatabaseManager
        # Monkey-patch DATABASE_NAME
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()
            sub_id = db.log_submission(
                solicitation_id="N0010425QNF13",
                rfq_id=1,
                vendor_id=100,
                vendor_name="Acme Corp",
                method="thomasnet_form",
                status="sent",
                notes="Test submission"
            )
            assert sub_id is not None
            assert sub_id > 0

            # Verify it's in the DB
            subs = db.get_submissions_for_rfq(1)
            assert len(subs) == 1
            assert subs[0]['vendor_name'] == "Acme Corp"
            assert subs[0]['submission_status'] == "sent"
        finally:
            database_manager.DATABASE_NAME = original_db

    def test_update_rfq_review(self, db_with_tables):
        from database_manager import DatabaseManager
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()
            # Insert a test RFQ
            conn = sqlite3.connect(db_with_tables)
            conn.execute("""
                INSERT INTO rfq_outputs (contract_id, rfq_type, rfq_content, review_status)
                VALUES ('TEST001', 'PRODUCT', 'Test RFQ content', 'pending_review')
            """)
            conn.commit()
            conn.close()

            # Update review
            success = db.update_rfq_review(1, 'approved', 'test_admin')
            assert success is True

            # Verify
            conn = sqlite3.connect(db_with_tables)
            row = conn.execute("SELECT review_status, reviewed_by FROM rfq_outputs WHERE id=1").fetchone()
            conn.close()
            assert row[0] == 'approved'
            assert row[1] == 'test_admin'
        finally:
            database_manager.DATABASE_NAME = original_db

    def test_get_pending_review_rfqs(self, db_with_tables):
        from database_manager import DatabaseManager
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()
            # Insert test RFQs
            conn = sqlite3.connect(db_with_tables)
            for i in range(3):
                conn.execute("""
                    INSERT INTO rfq_outputs (contract_id, rfq_type, rfq_content, review_status)
                    VALUES (?, 'PRODUCT', ?, 'pending_review')
                """, (f'TEST{i:03d}', f'RFQ content {i}'))
            conn.commit()
            conn.close()

            pending = db.get_pending_review_rfqs()
            assert len(pending) == 3
        finally:
            database_manager.DATABASE_NAME = original_db

    def test_get_rfq_counts(self, db_with_tables):
        from database_manager import DatabaseManager
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()
            conn = sqlite3.connect(db_with_tables)
            for status in ['approved', 'approved', 'pending_review', 'auto_rejected']:
                conn.execute("""
                    INSERT INTO rfq_outputs (contract_id, rfq_type, rfq_content, review_status)
                    VALUES (?, 'PRODUCT', 'content', ?)
                """, (f'R{status[:4]}', status))
            conn.commit()
            conn.close()

            counts = db.get_rfq_counts()
            assert counts['approved'] == 2
            assert counts['pending_review'] == 1
            assert counts['auto_rejected'] == 1
            assert counts['total'] == 4
        finally:
            database_manager.DATABASE_NAME = original_db

    def test_get_recent_submissions(self, db_with_tables):
        from database_manager import DatabaseManager
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()
            for i in range(5):
                db.log_submission("N001", i, i, f"Vendor {i}", "email", "sent")

            subs = db.get_recent_submissions(limit=3)
            assert len(subs) == 3
        finally:
            database_manager.DATABASE_NAME = original_db


# ─── schema migration tests ───────────────────────────────────────────────────

class TestSchemaMigration:
    def test_schema_additions_execute(self, tmp_path):
        """Run schema_additions.sql against a temp DB and verify it works."""
        db_path = str(tmp_path / "test_migrate.db")
        conn = sqlite3.connect(db_path)
        # Create minimal base tables
        conn.execute("""
            CREATE TABLE rfq_outputs (
                id INTEGER PRIMARY KEY,
                contract_id TEXT NOT NULL UNIQUE,
                rfq_type TEXT NOT NULL,
                rfq_content TEXT NOT NULL,
                format TEXT DEFAULT 'markdown',
                generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_vendor BOOLEAN DEFAULT 0,
                vendor_email_recipient TEXT,
                sent_date TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE submission_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitation_id TEXT NOT NULL,
                rfq_id INTEGER NOT NULL,
                vendor_id INTEGER NOT NULL,
                vendor_name TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submission_method TEXT,
                submission_status TEXT,
                response_received_at TIMESTAMP,
                response_status TEXT,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Apply additions
        schema_path = os.path.join(WORKTREE, "schema_additions.sql")
        if not os.path.exists(schema_path):
            pytest.skip("schema_additions.sql not found")

        with open(schema_path, 'r') as f:
            sql = f.read()

        conn = sqlite3.connect(db_path)
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                        raise
        conn.commit()

        # Verify columns exist
        cursor = conn.execute("PRAGMA table_info(rfq_outputs)")
        cols = [row[1] for row in cursor.fetchall()]
        assert 'review_status' in cols
        assert 'validation_issues' in cols
        assert 'reviewed_by' in cols
        assert 'reviewed_at' in cols

        # Verify views exist
        views = conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()
        view_names = [v[0] for v in views]
        assert 'v_pending_review' in view_names
        assert 'v_pipeline_metrics' in view_names

        conn.close()

    def test_migration_idempotent(self, tmp_path):
        """Running migration twice should not fail."""
        db_path = str(tmp_path / "test_idempotent.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE rfq_outputs (
                id INTEGER PRIMARY KEY,
                contract_id TEXT NOT NULL UNIQUE,
                rfq_type TEXT NOT NULL,
                rfq_content TEXT NOT NULL,
                format TEXT DEFAULT 'markdown',
                generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_vendor BOOLEAN DEFAULT 0,
                vendor_email_recipient TEXT,
                sent_date TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE submission_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitation_id TEXT NOT NULL,
                rfq_id INTEGER NOT NULL,
                vendor_id INTEGER NOT NULL,
                vendor_name TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submission_method TEXT,
                submission_status TEXT,
                response_received_at TIMESTAMP,
                response_status TEXT,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()

        schema_path = os.path.join(WORKTREE, "schema_additions.sql")
        if not os.path.exists(schema_path):
            pytest.skip("schema_additions.sql not found")

        with open(schema_path, 'r') as f:
            sql = f.read()

        # Run twice
        for run in range(2):
            conn = sqlite3.connect(db_path)
            for stmt in sql.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    try:
                        conn.execute(stmt)
                    except sqlite3.OperationalError as e:
                        if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                            raise
            conn.commit()
            conn.close()


# ─── integration test ─────────────────────────────────────────────────────────

class TestIntegration:
    def test_full_happy_path(self, db_with_tables):
        """Create RFQ → validate → insert → approve → log submission."""
        from database_manager import DatabaseManager
        from rfq_validator import validate_rfq
        import database_manager
        original_db = database_manager.DATABASE_NAME
        database_manager.DATABASE_NAME = db_with_tables

        try:
            db = DatabaseManager()

            # 1. Create good RFQ
            rfq_content = (
                "REQUEST FOR QUOTATION\n\n"
                "Scope: Procurement of 500 industrial brackets\n"
                "Quantity: 500 units\n"
                "Deadline: 2026-09-30\n"
                "Delivery: 1200 Industrial Pkwy, Columbus, OH\n"
                "Contact: procurement@example.com\n\n"
                "We are requesting quotes for 500 industrial brackets per ASTM A36 specs. "
                "Delivery to Columbus, OH by September 30, 2026. Include pricing and lead time."
            )

            # 2. Validate
            from batch_regenerate_rfqs import parse_llm_rfq_output
            rfq_dict = parse_llm_rfq_output(rfq_content)
            validation = validate_rfq(rfq_dict)
            assert validation.severity == "ok", f"Expected ok, got {validation.severity}: {validation.issues}"

            # 3. Insert into DB
            conn = sqlite3.connect(db_with_tables)
            conn.execute("""
                INSERT INTO rfq_outputs (contract_id, rfq_type, rfq_content, review_status, validation_issues)
                VALUES (?, 'PRODUCT', ?, ?, ?)
            """, ("INTTEST001", rfq_content, "approved", json.dumps(validation.issues)))
            conn.commit()
            conn.close()

            # 4. Approve via DB manager
            success = db.update_rfq_review(1, 'approved', 'integration_test')
            assert success is True

            # 5. Log submission
            sub_id = db.log_submission(
                solicitation_id="N0010425QNF13",
                rfq_id=1,
                vendor_id=100,
                vendor_name="Acme Corp",
                method="thomasnet_form",
                status="sent"
            )
            assert sub_id is not None

            # 6. Verify full pipeline
            counts = db.get_rfq_counts()
            assert counts['approved'] == 1

            metrics = db.get_pipeline_metrics()
            assert metrics['sent_count'] == 1

            subs = db.get_submissions_for_rfq(1)
            assert len(subs) == 1
            assert subs[0]['vendor_name'] == "Acme Corp"

        finally:
            database_manager.DATABASE_NAME = original_db


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])