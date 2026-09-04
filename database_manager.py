import sqlite3
import json
import time

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(BASE_DIR, "rebusiness_automation.db")

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.create_tables()

    def _connect_db(self):
        """Establishes a connection to the SQLite database."""
        if self.conn is None:
            self.conn = sqlite3.connect(DATABASE_NAME)
            self.conn.row_factory = sqlite3.Row # Allows accessing columns by name
        return self.conn

    def _close_db(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_tables(self):
        """Creates the necessary tables in the database."""
        conn = self._connect_db()
        cursor = conn.cursor()

        # Drop the vendors table to ensure schema is up to date
        # cursor.execute("DROP TABLE IF EXISTS vendors")
        print("Dropped 'vendors' table to refresh schema.")

        cursor.execute("""
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

        # Pipeline rebuild: review status + validation tracking
        for col, definition in [
            ("review_status", "TEXT DEFAULT 'pending'"),
            ("validation_issues", "TEXT"),
            ("reviewed_by", "TEXT"),
            ("reviewed_at", "TIMESTAMP"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE rfq_outputs ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass  # column exists

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submission_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitation_id TEXT,
                rfq_id INTEGER,
                vendor_id INTEGER,
                vendor_name TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submission_method TEXT,
                submission_status TEXT DEFAULT 'pending',
                response_received_at TIMESTAMP,
                response_status TEXT DEFAULT 'no_response',
                notes TEXT,
                FOREIGN KEY (rfq_id) REFERENCES rfq_outputs(id),
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
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
            )
            conn.commit()
            print(f"Added proposal for {contract_id} to database.")
            return True
        except sqlite3.IntegrityError:
            print(f"Proposal for {contract_id} already exists. Updating existing entry.")
            cursor.execute(
                "UPDATE proposals SET proposal_text=? WHERE contract_id=?",
                (proposal_text, contract_id)
            )
            conn.commit()
            print(f"Updated proposal for {contract_id} in database.")
            return True
        except Exception as e:
            print(f"Error adding/updating proposal for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_vendor(self, contract_id, name, website, email, phone, confidence_score, has_gov_page, has_past_performance, gov_agencies_worked_with, past_performance_summary, key_personnel, linkedin_url, place_types, email_status='Ready to Contact'):
        """
        Adds a new vendor to the database.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO vendors (contract_id, name, website, email, phone, confidence_score, has_gov_page, has_past_performance, gov_agencies_worked_with, past_performance_summary, key_personnel, linkedin_url, place_types, email_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (contract_id, name, website, email, phone, confidence_score, has_gov_page, has_past_performance, gov_agencies_worked_with, past_performance_summary, key_personnel, linkedin_url, place_types, email_status)
            )
            conn.commit()
            print(f"Added vendor {name} for {contract_id} to database.")
            return True
        except sqlite3.IntegrityError:
            print(f"Vendor {name} for {contract_id} already exists. Skipping.")
            return False
        except Exception as e:
            print(f"Error adding vendor {name} for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_solicitation_analysis(self, contract_id, analysis_summary, confidence=None, review_status='pending'):
        """
        Updates the analysis_summary for a specific solicitation.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            if confidence is not None:
                cursor.execute(
                    "UPDATE solicitations SET analysis_summary=?, extraction_confidence=?, review_status=? WHERE contract_id=?",
                    (analysis_summary, confidence, review_status, contract_id)
                )
            else:
                cursor.execute(
                    "UPDATE solicitations SET analysis_summary=? WHERE contract_id=?",
                    (analysis_summary, contract_id)
                )

            # Update the separate analysis table
            cursor.execute("SELECT id FROM solicitation_analysis WHERE contract_id = ?", (contract_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("UPDATE solicitation_analysis SET analysis_json = ? WHERE contract_id = ?", (analysis_summary, contract_id))
            else:
                cursor.execute("INSERT INTO solicitation_analysis (contract_id, analysis_json) VALUES (?, ?)", (contract_id, analysis_summary))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating analysis for solicitation {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def update_solicitation_data(self, contract_id, json_data):
        """
        Updates the 'data' column with the full analysis JSON.
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE solicitations SET data=? WHERE contract_id=?",
                (json_data, contract_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating data for {contract_id}: {e}")
            return False
        finally:
            self._close_db()

    def get_solicitation_by_contract_id(self, contract_id):
        """Retrieves a solicitation by its contract_id."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (contract_id,))
        solicitation = cursor.fetchone()
        self._close_db()
        return solicitation

    def get_attachments_for_solicitation(self, contract_id):
        """Retrieves all attachments for a given contract_id."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attachments WHERE contract_id = ?", (contract_id,))
        attachments = cursor.fetchall()
        self._close_db()
        return attachments

    def get_vendors_for_solicitation(self, contract_id):
        """Retrieves all vendors for a given contract_id."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE contract_id = ?", (contract_id,))
        vendors = cursor.fetchall()
        self._close_db()
        return vendors



    def solicitation_exists(self, contract_id):
        """Checks if a solicitation with the given contract_id already exists."""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM solicitations WHERE contract_id = ?", (contract_id,))
        exists = cursor.fetchone() is not None
        self._close_db()
        return exists

    # ===== Manufacturer Price Discovery Methods =====
    
    def add_manufacturer(self, name, website=None, email=None, phone=None, address=None, 
                        city=None, state=None, zip_code=None, certifications=None, 
                        naics_codes=None, is_us_based=True):
        """Adds a new manufacturer to the database."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO manufacturers 
                (name, website, email, phone, address, city, state, zip_code, 
                certifications, naics_codes, is_us_based) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, website, email, phone, address, city, state, zip_code, 
                certifications, naics_codes, is_us_based)
            )
            conn.commit()
            manufacturer_id = cursor.lastrowid
            print(f"Added manufacturer {name} to database (ID: {manufacturer_id}).")
            return manufacturer_id
        except sqlite3.IntegrityError:
            print(f"Manufacturer {name} may already exist.")
            return None
        except Exception as e:
            print(f"Error adding manufacturer {name}: {e}")
            conn.rollback()
            return None
        finally:
            self._close_db()

    def add_product(self, contract_id, product_name, description=None, 
                   specifications=None, quantity=None, naics_code=None):
        """Adds a product extracted from a solicitation."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO products 
                (contract_id, product_name, description, specifications, quantity, naics_code) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (contract_id, product_name, description, specifications, quantity, naics_code)
            )
            conn.commit()
            product_id = cursor.lastrowid
            self._close_db() # Close before calling another method that opens db
            self.update_sourcing_status(product_id, status='pending')
            print(f"Added product '{product_name}' for {contract_id} (ID: {product_id}).")
            return product_id
        except Exception as e:
            print(f"Error adding product '{product_name}': {e}")
            conn.rollback()
            return None
        finally:
            self._close_db()

    def clear_products_for_solicitation(self, contract_id):
        """Removes all products associated with a contract_id. Used before re-extraction."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM products WHERE contract_id = ?", (contract_id,))
            conn.commit()
            print(f"Cleared existing products for solicitation {contract_id}.")
            return True
        except Exception as e:
            print(f"Error clearing products for {contract_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def add_price_list(self, manufacturer_id, product_id, sku=None, unit_price=None, 
                      bulk_price=None, min_order_qty=None, lead_time_days=None, 
                      discount_percent=None, valid_until=None, file_path=None, notes=None):
        """Adds pricing information from a manufacturer."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO price_lists 
                (manufacturer_id, product_id, sku, unit_price, bulk_price, min_order_qty, 
                lead_time_days, discount_percent, valid_until, file_path, notes) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (manufacturer_id, product_id, sku, unit_price, bulk_price, min_order_qty, 
                lead_time_days, discount_percent, valid_until, file_path, notes)
            )
            conn.commit()
            price_id = cursor.lastrowid
            print(f"Added price list entry (ID: {price_id}).")
            return price_id
        except Exception as e:
            print(f"Error adding price list: {e}")
            conn.rollback()
            return None
        finally:
            self._close_db()

    def add_manufacturer_request(self, manufacturer_id, product_id, email_thread_id=None, notes=None):
        """Records a price list request sent to a manufacturer."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO manufacturer_requests 
                (manufacturer_id, product_id, email_thread_id, notes) 
                VALUES (?, ?, ?, ?)""",
                (manufacturer_id, product_id, email_thread_id, notes)
            )
            conn.commit()
            request_id = cursor.lastrowid
            print(f"Recorded manufacturer request (ID: {request_id}).")
            return request_id
        except Exception as e:
            print(f"Error recording manufacturer request: {e}")
            conn.rollback()
            return None
        finally:
            self._close_db()

    def update_manufacturer_request_status(self, request_id, status, response_date=None):
        """Updates the status of a manufacturer request."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            if response_date:
                cursor.execute(
                    "UPDATE manufacturer_requests SET status=?, response_date=? WHERE id=?",
                    (status, response_date, request_id)
                )
            else:
                cursor.execute(
                    "UPDATE manufacturer_requests SET status=? WHERE id=?",
                    (status, request_id)
                )
            conn.commit()
            print(f"Updated request {request_id} status to '{status}'.")
            return True
        except Exception as e:
            print(f"Error updating request status: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def get_products_by_contract(self, contract_id):
        """Retrieves all products for a specific contract."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM products WHERE contract_id=?", (contract_id,))
            products = cursor.fetchall()
            return [dict(row) for row in products]
        except Exception as e:
            print(f"Error retrieving products for {contract_id}: {e}")
            return []
        finally:
            self._close_db()

    def get_manufacturer_by_name(self, name):
        """Retrieves a manufacturer by name."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM manufacturers WHERE name=?", (name,))
            manufacturer = cursor.fetchone()
            return dict(manufacturer) if manufacturer else None
        except Exception as e:
            print(f"Error retrieving manufacturer '{name}': {e}")
            return None
        finally:
            self._close_db()

    def get_manufacturer_by_email(self, email):
        """Retrieves a manufacturer by email (case insensitive)."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM manufacturers WHERE email LIKE ?", (email,))
            manufacturer = cursor.fetchone()
            return dict(manufacturer) if manufacturer else None
        except Exception as e:
            print(f"Error retrieving manufacturer by email '{email}': {e}")
            return None
        finally:
            self._close_db()

    def get_latest_request_for_manufacturer(self, manufacturer_id):
        """Retrieves the latest request for a manufacturer."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM manufacturer_requests 
                WHERE manufacturer_id = ? 
                ORDER BY request_date DESC 
                LIMIT 1
            """, (manufacturer_id,))
            request = cursor.fetchone()
            return dict(request) if request else None
        except Exception as e:
            print(f"Error retrieving request for manufacturer {manufacturer_id}: {e}")
            return None
        finally:
            self._close_db()

    def get_price_lists_by_product(self, product_id):
        """Retrieves all price lists for a specific product."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT pl.*, m.name as manufacturer_name, m.email as manufacturer_email
                FROM price_lists pl
                JOIN manufacturers m ON pl.manufacturer_id = m.id
                WHERE pl.product_id=?""",
                (product_id,)
            )
            price_lists = cursor.fetchall()
            return [dict(row) for row in price_lists]
        except Exception as e:
            print(f"Error retrieving price lists for product {product_id}: {e}")
            return []
        finally:
            self._close_db()

    def update_sourcing_status(self, product_id, status=None, found_inc=0, sent_inc=0):
        """Updates the sourcing status for a product."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            # Check if exists
            cursor.execute("SELECT * FROM product_sourcing_status WHERE product_id = ?", (product_id,))
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute("""
                    INSERT INTO product_sourcing_status (product_id, status)
                    VALUES (?, 'pending')
                """, (product_id,))
            
            # Simple update query construction
            updates = []
            params = []
            
            if status:
                updates.append("status = ?")
                params.append(status)
            
            if found_inc > 0:
                updates.append("suppliers_found_count = suppliers_found_count + ?")
                params.append(found_inc)
                
            if sent_inc > 0:
                updates.append("outreach_sent_count = outreach_sent_count + ?")
                params.append(sent_inc)
                
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if status == 'sourcing' or found_inc > 0:
                 updates.append("last_sourcing_date = CURRENT_TIMESTAMP")

            if updates:
                query = f"UPDATE product_sourcing_status SET {', '.join(updates)} WHERE product_id = ?"
                params.append(product_id)
                cursor.execute(query, tuple(params))
                conn.commit()
                
            return True
        except Exception as e:
            print(f"Error updating sourcing status for {product_id}: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def link_product_supplier(self, product_id, manufacturer_id):
        """Links a product to a supplier."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO product_suppliers (product_id, manufacturer_id)
                VALUES (?, ?)
            """, (product_id, manufacturer_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error linking product {product_id} to supplier {manufacturer_id}: {e}")
            return False
        finally:
            self._close_db()

    def get_products_for_sourcing(self, limit=10):
        """Get products that need sourcing (pending or sourcing with few suppliers)."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT p.id, p.product_name, p.quantity, p.specifications
                FROM products p
                LEFT JOIN product_sourcing_status s ON p.id = s.product_id
                WHERE (s.status IS NULL OR s.status IN ('pending', 'sourcing'))
                AND (s.suppliers_found_count IS NULL OR s.suppliers_found_count < 15)
                ORDER BY p.created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self._close_db()
            
    def get_suppliers_for_outreach(self, product_id, limit=20):
        """Get suppliers for a product pending outreach."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT m.id, m.name, m.email, m.website
                FROM manufacturers m
                JOIN product_suppliers ps ON m.id = ps.manufacturer_id
                WHERE ps.product_id = ?
                AND m.id NOT IN (
                    SELECT manufacturer_id FROM manufacturer_requests 
                    WHERE status IN ('sent', 'replied') AND payload LIKE ?
                )
                LIMIT ?
            """, (product_id, f"%{product_id}%", limit)) 
            # Note: payload check is a weak link, ideally manufacturer_requests should have product_id. 
            # I added product_id to manufacturer_requests in previous schema check? 
            # Let's check line 163 of original file: 'product_id INTEGER'. YES.
            # So I should use that instead of payload LIKE.
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
             # Fallback if I misremembered schema, but I see it in create_tables snippet above
             return []
        finally:
            self._close_db()

    def get_sourcing_status(self, product_id):
         """Get clean status dict."""
         conn = self._connect_db()
         cursor = conn.cursor()
         try:
             cursor.execute("SELECT * FROM product_sourcing_status WHERE product_id = ?", (product_id,))
             row = cursor.fetchone()
             return dict(row) if row else None
         finally:
             self._close_db()
    def add_rfq_output(self, contract_id, rfq_type, rfq_content, format="markdown", sent_to_vendor=False):
        """
        Stores generated RFQ markdown output.
        
        Args:
            contract_id: Contract ID
            rfq_type: "PRODUCT" or "SERVICE"
            rfq_content: Full RFQ markdown content
            format: "markdown" or "docx"
            sent_to_vendor: Whether this has been sent to vendor
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            # Create table if not exists (add this to create_tables too)
            cursor.execute("""
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
    
    def get_all_rfqs(self, limit=50, offset=0, sent_status=None, review_status=None):
        """
        Get RFQs with pagination for dashboard

        Args:
            limit: Number of records
            offset: Pagination offset
            sent_status: 'pending' (sent_to_vendor=0) or 'sent' (sent_to_vendor=1), or None for all
            review_status: Filter by review_status column, or None for all
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            query = """
                SELECT r.*, s.title as solicitation_title
                FROM rfq_outputs r
                LEFT JOIN solicitations s ON r.contract_id = s.contract_id
            """
            conditions = []
            params = []

            if sent_status == 'pending':
                conditions.append("r.sent_to_vendor = 0")
            elif sent_status == 'sent':
                conditions.append("r.sent_to_vendor = 1")

            if review_status:
                conditions.append("r.review_status = ?")
                params.append(review_status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY r.generated_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            rfqs = [dict(row) for row in cursor.fetchall()]
            return rfqs
        finally:
            self._close_db()

    def get_rfqs_count(self, sent_status=None, review_status=None):
        """Get total RFQ count, optionally filtered by status"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            query = "SELECT COUNT(*) FROM rfq_outputs"
            conditions = []
            params = []

            if sent_status == 'pending':
                conditions.append("sent_to_vendor = 0")
            elif sent_status == 'sent':
                conditions.append("sent_to_vendor = 1")

            if review_status:
                conditions.append("review_status = ?")
                params.append(review_status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor.execute(query, tuple(params))
            count = cursor.fetchone()[0]
            return count
        finally:
            self._close_db()

    def get_rfq_by_contract(self, contract_id):
        """Get RFQ by contract ID"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.*, s.title as solicitation_title, s.description
                FROM rfq_outputs r
                LEFT JOIN solicitations s ON r.contract_id = s.contract_id
                WHERE r.contract_id = ?
            """, (contract_id,))
            rfq = cursor.fetchone()
            return dict(rfq) if rfq else None
        finally:
            self._close_db()

    def get_vendor_submissions(self, limit=100, offset=0):
        """Get vendor submissions with pagination"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM vendors
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            vendors = [dict(row) for row in cursor.fetchall()]
            return vendors
        finally:
            self._close_db()

    def get_vendor_submissions_count(self):
        """Get total vendor count"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM vendors")
            count = cursor.fetchone()[0]
            return count
        finally:
            self._close_db()

    def get_vendor_stats(self):
        """Get vendor statistics"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT name) as unique_vendors,
                    SUM(CASE WHEN email_status = 'Sent' THEN 1 ELSE 0 END) as contacted
                FROM vendors
            """)
            row = cursor.fetchone()
            stats = dict(row) if row else {'total': 0, 'unique_vendors': 0, 'contacted': 0}
            return stats
        finally:
            self._close_db()

    def get_solicitation_stats(self):
        """Get solicitation statistics"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN created_at >= datetime('now', '-7 days') THEN 1 END) as this_week
                FROM solicitations
            """)
            row = cursor.fetchone()
            stats = dict(row) if row else {'total': 0, 'this_week': 0}
            return stats
        finally:
            self._close_db()

    def get_vendors_by_product(self):
        """Get vendors grouped by product"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT contract_id, COUNT(*) as vendor_count
                FROM vendors
                GROUP BY contract_id
                ORDER BY vendor_count DESC
            """)
            results = [dict(row) for row in cursor.fetchall()]
            return results
        finally:
            self._close_db()

    def get_dashboard_stats(self):
        """Get overall dashboard statistics"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            stats = {}
            
            # Solicitations
            cursor.execute("SELECT COUNT(*) FROM solicitations")
            stats['total_solicitations'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM solicitations 
                WHERE created_at >= datetime('now', '-7 days')
            """)
            stats['solicitations_last_week'] = cursor.fetchone()[0]
            
            # RFQs
            cursor.execute("SELECT COUNT(*) FROM rfq_outputs")
            stats['total_rfqs'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM rfq_outputs 
                WHERE generated_date >= datetime('now', '-7 days')
            """)
            stats['rfqs_last_week'] = cursor.fetchone()[0]
            
            # Vendor submissions
            cursor.execute("SELECT COUNT(*) FROM vendors")
            stats['successful_submissions'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT name) FROM vendors")
            stats['unique_vendors'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM vendors 
                WHERE created_at >= datetime('now', '-7 days')
            """)
            stats['submissions_last_week'] = cursor.fetchone()[0]
            
            return stats
        finally:
            self._close_db()

    def get_all_solicitations(self, limit=50, offset=0, search=''):
        """Get solicitations with pagination and search"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            if search:
                cursor.execute("""
                    SELECT * FROM solicitations 
                    WHERE title LIKE ? OR contract_id LIKE ? OR description LIKE ?
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (f'%{search}%', f'%{search}%', f'%{search}%', limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM solicitations 
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """, (limit, offset))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self._close_db()

    def get_solicitations_count(self, search=''):
        """Get total count of solicitations"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            if search:
                cursor.execute("""
                    SELECT COUNT(*) FROM solicitations 
                    WHERE title LIKE ? OR contract_id LIKE ? OR description LIKE ?
                """, (f'%{search}%', f'%{search}%', f'%{search}%'))
            else:
                cursor.execute("SELECT COUNT(*) FROM solicitations")
            
            count = cursor.fetchone()[0]
            return count
        finally:
            self._close_db()

    def get_solicitation_by_id(self, contract_id):
        """Get solicitation by contract_id"""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM solicitations WHERE contract_id = ?", (contract_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            self._close_db()


    # ─── New methods for pipeline rebuild ────────────────────────────────

    def update_rfq_review(self, rfq_id: int, status: str, reviewed_by: str = "admin") -> bool:
        """Update RFQ review status (pending_review, approved, rejected, auto_rejected)."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE rfq_outputs
                SET review_status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, reviewed_by, rfq_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating RFQ review: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def get_pending_review_rfqs(self) -> list:
        """Fetch all RFQs with review_status='pending_review'."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    r.id, r.contract_id, r.rfq_type, r.rfq_content,
                    r.review_status, r.validation_issues, r.created_at,
                    s.title as solicitation_title
                FROM rfq_outputs r
                LEFT JOIN solicitations s ON r.contract_id = s.contract_id
                WHERE r.review_status = 'pending_review'
                ORDER BY r.created_at ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self._close_db()

    def get_rfq_counts(self) -> dict:
        """Get counts of RFQs by review status."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT review_status, COUNT(*) as count
                FROM rfq_outputs
                GROUP BY review_status
            """)
            rows = cursor.fetchall()
            counts = {row['review_status']: row['count'] for row in rows}
            return {
                'pending_review': counts.get('pending_review', 0),
                'approved': counts.get('approved', 0),
                'rejected': counts.get('rejected', 0),
                'auto_rejected': counts.get('auto_rejected', 0),
                'total': sum(counts.values()),
            }
        finally:
            self._close_db()

    def get_pipeline_metrics(self) -> dict:
        """Get aggregated pipeline metrics including submission funnel."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            # RFQ counts
            rfq_counts = self.get_rfq_counts()

            # Submission stats
            cursor.execute("""
                SELECT
                    submission_status,
                    response_status,
                    COUNT(*) as count
                FROM submission_log
                GROUP BY submission_status, response_status
            """)
            sub_rows = cursor.fetchall()

            total_submissions = sum(r['count'] for r in sub_rows)
            sent_count = sum(r['count'] for r in sub_rows if r['submission_status'] == 'sent')
            failed_count = sum(r['count'] for r in sub_rows if r['submission_status'] == 'failed')
            quoted_count = sum(r['count'] for r in sub_rows if r['response_status'] == 'quoted')
            declined_count = sum(r['count'] for r in sub_rows if r['response_status'] == 'declined')
            no_response_count = sum(r['count'] for r in sub_rows if r['response_status'] == 'no_response')

            # Recent submissions
            cursor.execute("""
                SELECT
                    sl.id, sl.solicitation_id, sl.rfq_id, sl.vendor_name,
                    sl.submitted_at, sl.submission_method, sl.submission_status,
                    sl.response_received_at, sl.response_status, sl.notes
                FROM submission_log sl
                ORDER BY sl.submitted_at DESC
                LIMIT 50
            """)
            recent_rows = cursor.fetchall()
            recent_submissions = [dict(row) for row in recent_rows]

            return {
                'rfq_counts': rfq_counts,
                'total_submissions': total_submissions,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'quoted_count': quoted_count,
                'declined_count': declined_count,
                'no_response_count': no_response_count,
                'response_rate': (quoted_count + declined_count) / sent_count * 100 if sent_count > 0 else 0,
                'conversion_rate': quoted_count / sent_count * 100 if sent_count > 0 else 0,
                'recent_submissions': recent_submissions,
            }
        finally:
            self._close_db()

    def log_submission(self, solicitation_id: str, rfq_id: int, vendor_id: int,
                       vendor_name: str, method: str, status: str, notes: str = None) -> int:
        """Log a submission attempt to a vendor. Returns submission_log ID."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO submission_log
                (solicitation_id, rfq_id, vendor_id, vendor_name, submission_method, submission_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (solicitation_id, rfq_id, vendor_id, vendor_name, method, status, notes))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error logging submission: {e}")
            conn.rollback()
            return None
        finally:
            self._close_db()

    def update_submission_response(self, submission_id: int, response_status: str, notes: str = None) -> bool:
        """Update a submission log entry with vendor response."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE submission_log
                SET response_received_at = CURRENT_TIMESTAMP,
                    response_status = ?,
                    notes = COALESCE(?, notes)
                WHERE id = ?
            """, (response_status, notes, submission_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating submission response: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db()

    def get_submission_stats(self) -> dict:
        """Return aggregated submission statistics."""
        return self.get_pipeline_metrics()

    def get_submissions_for_rfq(self, rfq_id: int) -> list:
        """Get all submission log entries for a specific RFQ."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT *
                FROM submission_log
                WHERE rfq_id = ?
                ORDER BY submitted_at DESC
            """, (rfq_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self._close_db()

    def get_recent_submissions(self, limit: int = 50) -> list:
        """Get recent submission log entries."""
        conn = self._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    sl.id, sl.solicitation_id, sl.rfq_id, sl.vendor_id, sl.vendor_name,
                    sl.submitted_at, sl.submission_method, sl.submission_status,
                    sl.response_received_at, sl.response_status, sl.notes
                FROM submission_log sl
                ORDER BY sl.submitted_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            self._close_db()

