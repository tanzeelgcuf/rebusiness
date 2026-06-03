            CREATE TABLE IF NOT EXISTS solicitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT UNIQUE,
                url TEXT UNIQUE,
                title TEXT,
                description TEXT,
                location TEXT,
                product_requirements TEXT,
                analysis_summary TEXT, -- To store the structured analysis from attachment_reader_agent
                data TEXT, -- To store the full JSON of scraped data
                review_status TEXT DEFAULT 'pending', -- pending, reviewed, flagged
                extraction_confidence REAL, -- 0.0 to 1.0
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solicitation_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT UNIQUE,
                analysis_json TEXT, -- Full JSON output from Gemini
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)
        
        # Migration for existing tables
        try:
            cursor.execute("ALTER TABLE solicitations ADD COLUMN review_status TEXT DEFAULT 'pending'")
            cursor.execute("ALTER TABLE solicitations ADD COLUMN extraction_confidence REAL")
            print("Migrated 'solicitations' table with new review columns.")
        except sqlite3.OperationalError:
            pass # Columns likely exist

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT,
                file_name TEXT,
                file_path TEXT,
                url TEXT,
                download_date REAL, -- Unix timestamp
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT UNIQUE,
                proposal_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT,
                name TEXT,
                website TEXT,
                email TEXT,
                phone TEXT,
                confidence_score INTEGER,
                has_gov_page BOOLEAN,
                has_past_performance BOOLEAN,
                gov_agencies_worked_with TEXT,
                past_performance_summary TEXT,
                key_personnel TEXT,
                linkedin_url TEXT,
                place_types TEXT,
                email_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)

        # Manufacturer Price Discovery Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                website TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip_code TEXT,
                certifications TEXT,
                naics_codes TEXT,
                is_us_based BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT,
                product_name TEXT NOT NULL,
                description TEXT,
                specifications TEXT,
                quantity INTEGER,
                naics_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manufacturer_id INTEGER,
                product_id INTEGER,
                sku TEXT,
                unit_price REAL,
                bulk_price REAL,
                min_order_qty INTEGER,
                lead_time_days INTEGER,
                discount_percent REAL,
                valid_until DATE,
                file_path TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # cursor.execute("DROP TABLE IF EXISTS manufacturer_requests")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturer_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manufacturer_id INTEGER,
                product_id INTEGER,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_date TIMESTAMP,
                status TEXT DEFAULT 'pending', -- pending, sent, failed, replied
                method TEXT, -- email, form
                payload TEXT, -- Content of the message sent
                email_thread_id TEXT,
                notes TEXT,
                FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)



        # cursor.execute("DROP TABLE IF EXISTS product_sourcing_status") # Removed destructive drop
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_sourcing_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL UNIQUE,
                suppliers_found_count INTEGER DEFAULT 0,
                outreach_sent_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, sourcing, sourcing_complete, outreach_complete
                last_sourcing_date TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                manufacturer_id INTEGER,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validation_status TEXT DEFAULT 'pending', -- pending, valid, invalid
                validation_notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id),
                UNIQUE(product_id, manufacturer_id)
            )
        """)
        
        # Migration for product_suppliers
        try:
            cursor.execute("ALTER TABLE product_suppliers ADD COLUMN validation_status TEXT DEFAULT 'pending'")
            cursor.execute("ALTER TABLE product_suppliers ADD COLUMN validation_notes TEXT")
            print("Migrated 'product_suppliers' table with validation columns.")
        except sqlite3.OperationalError:
            pass # Columns likely exist

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rfq_outputs (
                id INTEGER PRIMARY KEY,
                contract_id TEXT NOT NULL UNIQUE,
                rfq_type TEXT NOT NULL,  -- "PRODUCT" or "SERVICE"
                rfq_content TEXT NOT NULL,
                format TEXT DEFAULT 'markdown',
                generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_to_vendor BOOLEAN DEFAULT 0,
                vendor_email_recipient TEXT,
                sent_date TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
            )
        """)

        conn.commit()
        self._close_db()
        print("Database tables created or already exist.")

    def update_supplier_validation(self, product_id, manufacturer_id, status, notes=None):
        """Updates the validation status of a product-supplier link."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE product_suppliers SET validation_status = ?, validation_notes = ? WHERE product_id = ? AND manufacturer_id = ?",
                (status, notes, product_id, manufacturer_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating supplier validation link: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_solicitation(self, contract_id, url, title, description, location, product_requirements, analysis_summary, data):
        """
        Adds a new solicitation to the database.
        `data` should be a JSON string of the full scraped details.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO solicitations (contract_id, url, title, description, location, product_requirements, analysis_summary, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (contract_id, url, title, description, location, product_requirements, analysis_summary, data)
            )
            conn.commit()
            print(f"Added solicitation {contract_id} to database.")
            return True
        except sqlite3.IntegrityError:
            print(f"Solicitation with contract_id {contract_id} already exists. Updating existing entry.")
            cursor.execute(
                "UPDATE solicitations SET url=?, title=?, description=?, location=?, product_requirements=?, analysis_summary=?, data=? WHERE contract_id=?",
                (url, title, description, location, product_requirements, analysis_summary, data, contract_id)
            )
            conn.commit()
            print(f"Updated solicitation {contract_id} in database.")
            return True
        except Exception as e:
            print(f"Error adding/updating solicitation {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_attachment(self, contract_id, file_name, file_path, url, download_date):
        """
        Adds attachment metadata to the database.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO attachments (contract_id, file_name, file_path, url, download_date) VALUES (?, ?, ?, ?, ?)",
                (contract_id, file_name, file_path, url, download_date)
            )
            conn.commit()
            print(f"Added attachment {file_name} for {contract_id} to database.")
            return True
        except sqlite3.IntegrityError:
            print(f"Attachment {file_name} for {contract_id} already exists. Skipping.")
            return False
        except Exception as e:
            print(f"Error adding attachment {file_name} for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_proposal(self, contract_id, proposal_text):
        """
        Adds a new proposal to the database.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO proposals (contract_id, proposal_text) VALUES (?, ?)",
                (contract_id, proposal_text)
--
                CREATE TABLE IF NOT EXISTS rfq_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id TEXT NOT NULL UNIQUE,
                    rfq_type TEXT NOT NULL,
                    rfq_content TEXT NOT NULL,
                    format TEXT DEFAULT 'markdown',
                    generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_to_vendor BOOLEAN DEFAULT 0,
                    vendor_email_recipient TEXT,
                    sent_date TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES solicitations(contract_id)
                )
            """)
            
            # Insert or update
            cursor.execute("""
                INSERT INTO rfq_outputs (contract_id, rfq_type, rfq_content, format, sent_to_vendor)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(contract_id) DO UPDATE SET
                    rfq_type=?,
                    rfq_content=?,
                    format=?,
                    generated_date=CURRENT_TIMESTAMP
            """, (contract_id, rfq_type, rfq_content, format, sent_to_vendor,
                  rfq_type, rfq_content, format))
            
            conn.commit()
            print(f"Stored RFQ for {contract_id} ({rfq_type}) in database.")
            return True
        except Exception as e:
            print(f"Error storing RFQ for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def update_rfq_content(self, contract_id, content):
        """Updates the RFQ content for a specific contract."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE rfq_outputs SET rfq_content = ?, generated_date = CURRENT_TIMESTAMP WHERE contract_id = ?",
                (content, contract_id)
            )
            conn.commit()
            print(f"Updated RFQ content for {contract_id}.")
            return True
        except Exception as e:
            print(f"Error updating RFQ content for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def get_rfq_output(self, contract_id):
        """Retrieves the RFQ output for a contract."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM rfq_outputs WHERE contract_id = ?", (contract_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self._close_db()

    def mark_rfq_sent(self, contract_id, recipient_email):
        """Marks an RFQ as sent to a vendor."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE rfq_outputs SET sent_to_vendor = 1, vendor_email_recipient = ?, sent_date = CURRENT_TIMESTAMP WHERE contract_id = ?",
                (recipient_email, contract_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking RFQ for {contract_id} as sent: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()
    # ========================================================================
    # Dashboard API Methods
    # ========================================================================
    
    def get_all_rfqs(self, limit=50, offset=0, sent_status=None):
        """
        Get RFQs with pagination for dashboard
        
        Args:
            limit: Number of records
            offset: Pagination offset
            sent_status: 'pending' (sent_to_vendor=0) or 'sent' (sent_to_vendor=1), or None for all
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            query = """
                SELECT r.*, s.title as solicitation_title
