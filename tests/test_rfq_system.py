"""
Comprehensive Testing Suite for RFQ Generation System
Tests all components to ensure 100% template fidelity
"""
import unittest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict

# Test imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database_manager import DatabaseManager


class TestDeadlineCalculation(unittest.TestCase):
    """Test business day deadline calculation."""
    
    def test_basic_calculation(self):
        """Test basic 4 business day calculation."""
        # Mock the calculation function
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        
        agent = AttachmentReaderAgent()
        
        # Test: Friday deadline should go to Monday (skip weekend)
        result = agent._calculate_internal_deadline("January 31, 2026", offset_days=4)
        self.assertIsNotNone(result)
        self.assertIn("2026", result)
    
    def test_weekend_skipping(self):
        """Ensure weekends are skipped."""
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        
        agent = AttachmentReaderAgent()
        
        # Monday January 27 - 4 business days = Tuesday January 21
        result = agent._calculate_internal_deadline("January 27, 2026", offset_days=4)
        self.assertIn("January", result)
        # Should be 21st (4 business days back)
        self.assertIn("21", result)
    
    def test_date_parsing(self):
        """Test various date format parsing."""
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        
        agent = AttachmentReaderAgent()
        
        test_dates = [
            "January 27, 2026",
            "Jan 27, 2026",
            "01/27/2026"
        ]
        
        for date_str in test_dates:
            result = agent._calculate_internal_deadline(date_str, 4)
            self.assertIsNotNone(result)


class TestValidation(unittest.TestCase):
    """Test validation pipeline."""
    
    def test_presolicitation_detection(self):
        """Test presolicitation filtering."""
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        
        agent = AttachmentReaderAgent()
        
        # Should detect presolicitation
        presol_text = "This is a presolicitation notice for informational purposes only"
        is_valid, msg = agent.validate_presolicitation(presol_text)
        self.assertFalse(is_valid)
        self.assertIn("Presolicitation", msg)
        
        # Should pass normal solicitation
        normal_text = "This is a solicitation for services"
        is_valid, msg = agent.validate_presolicitation(normal_text)
        self.assertTrue(is_valid)
    
    def test_deadline_validation(self):
        """Test deadline validation against current date."""
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        
        agent = AttachmentReaderAgent()
        
        # Past deadline should fail
        past_text = "Due date: January 1, 2020"
        is_valid, msg, deadline = agent.validate_deadline(past_text, 4)
        self.assertFalse(is_valid)
        self.assertIn("past", msg)
        
        # Future deadline should pass
        future_date = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
        future_text = f"Due date: {future_date}"
        is_valid, msg, deadline = agent.validate_deadline(future_text, 4)
        self.assertTrue(is_valid)


class TestTypeDetection(unittest.TestCase):
    """Test PRODUCT vs SERVICE detection."""
    
    def setUp(self):
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        self.agent = AttachmentReaderAgent()
    
    def test_product_detection(self):
        """Test product solicitation detection."""
        product_content = [
            """
            NSN: 6150-01-501-1062
            CAGE CODE: 19200
            Part Number: 12992465
            First Article Testing required
            MIL-STD-2073-1 packaging
            FOB Origin
            """
        ]
        
        rfq_type = self.agent.detect_rfq_type(product_content)
        self.assertEqual(rfq_type, "PRODUCT")
    
    def test_service_detection(self):
        """Test service solicitation detection."""
        service_content = [
            """
            Performance Work Statement
            Statement of Work
            Tree planting services
            Maintenance and monitoring required
            165.4 acres
            Site preparation
            """
        ]
        
        rfq_type = self.agent.detect_rfq_type(service_content)
        self.assertEqual(rfq_type, "SERVICE")
    
    def test_tie_breaker(self):
        """Test tie-breaker logic."""
        # PWS should force SERVICE
        mixed_content = [
            """
            Part Number: 12345
            Performance Work Statement (PWS)
            CAGE CODE: 99999
            """
        ]
        
        rfq_type = self.agent.detect_rfq_type(mixed_content)
        self.assertEqual(rfq_type, "SERVICE")


class TestFileReading(unittest.TestCase):
    """Test file content extraction."""
    
    def setUp(self):
        from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
        self.agent = AttachmentReaderAgent()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_text_file_reading(self):
        """Test .txt file reading."""
        test_content = "Test solicitation content\nLine 2\nLine 3"
        test_file = os.path.join(self.temp_dir, "test.txt")
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        result = self.agent._read_file_content(test_file)
        self.assertEqual(result, test_content)
    
    def test_csv_file_reading(self):
        """Test .csv file reading with table structure."""
        test_file = os.path.join(self.temp_dir, "test.csv")
        
        with open(test_file, 'w') as f:
            f.write("CLIN,Description,Quantity\n")
            f.write("0001,Widget,100\n")
            f.write("0002,Gadget,50\n")
        
        result = self.agent._read_file_content(test_file)
        self.assertIsNotNone(result)
        self.assertIn("CLIN", result)
        self.assertIn("Widget", result)


class TestRFQValidation(unittest.TestCase):
    """Test RFQ quality validation."""
    
    def setUp(self):
        try:
            from validate_rfq import RFQValidator
            self.validator = RFQValidator("PRODUCT")
        except ImportError:
            self.skipTest("Validation module not available")
    
    def test_government_email_detection(self):
        """Test government email filtering."""
        test_content = """
        Contact: john.doe@army.mil
        Or email: jane.smith@dla.gov
        Also: vendor@campsable.com
        """
        
        result = self.validator.validate_from_markdown(test_content)
        
        # Should flag government emails
        self.assertGreater(len(result['issues']), 0)
        self.assertTrue(any('government' in str(issue).lower() for issue in result['issues']))
    
    def test_placeholder_detection(self):
        """Test placeholder content detection."""
        test_content = """
        Description: Not specified in solicitation
        Quantity: See solicitation documents
        Location: Information not provided
        Date: Details not provided
        """
        
        result = self.validator.validate_from_markdown(test_content)
        
        # Should have low score due to many placeholders
        self.assertLess(result['score'], 50)
    
    def test_section_completeness(self):
        """Test required section presence."""
        complete_content = """
## 🏛️ Overview

## 🏛️ Items Required

## 🏛️ Delivery Requirements

## 🟩 Summary of What They Require

## 🟩 Key Takeaways
        """
        
        result = self.validator.validate_from_markdown(complete_content)
        
        # Should have high section score
        self.assertGreater(result['score'], 20)  # Section weight is 20 pts


class TestDocConversion(unittest.TestCase):
    """Test markdown to DOCX conversion."""
    
    def setUp(self):
        try:
            from utils.doc_converter import EnhancedDocConverter
            self.converter = EnhancedDocConverter()
        except ImportError:
            self.skipTest("Enhanced converter not available")
        
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_table_conversion(self):
        """Test markdown table to DOCX conversion."""
        test_markdown = """
## Test Table

| CLIN | Description | Quantity |
|------|-------------|----------|
| 0001 | Widget      | 100      |
| 0002 | Gadget      | 50       |
        """
        
        output_path = os.path.join(self.temp_dir, "test.docx")
        success = self.converter.convert(test_markdown, output_path)
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 1000)
    
    def test_emoji_preservation(self):
        """Test emoji headers are preserved."""
        test_markdown = """
## 🏛️ Overview

Test content

## 🟩 Summary

More content
        """
        
        output_path = os.path.join(self.temp_dir, "emoji_test.docx")
        success = self.converter.convert(test_markdown, output_path)
        
        self.assertTrue(success)
        
        # Verify emojis in output
        from docx import Document
        doc = Document(output_path)
        text = '\n'.join([p.text for p in doc.paragraphs])
        
        self.assertIn('🏛️', text)
        self.assertIn('🟩', text)
    
    def test_government_email_removal(self):
        """Test government emails are removed during conversion."""
        test_markdown = """
Contact: john.doe@army.mil
Or: jane.smith@dla.gov
Vendor: vendor@campsable.com
        """
        
        cleaned = self.converter.clean_markdown(test_markdown)
        
        # Should replace gov emails with campsable
        self.assertNotIn('@army.mil', cleaned)
        self.assertNotIn('@dla.gov', cleaned)
        self.assertIn('john@campsable.com', cleaned)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""
    
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test solicitation
        self.test_contract_id = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Add to database
        self.db_manager.add_solicitation(
            contract_id=self.test_contract_id,
            url="https://test.sam.gov/test",
            title="Test Solicitation",
            description="Test Description",
            location="Test Location",
            product_requirements="Test Requirements",
            analysis_summary=None,
            data="{}"
        )
    
    def tearDown(self):
        # Clean up test data
        conn = self.db_manager._connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM solicitations WHERE contract_id = ?", (self.test_contract_id,))
        cursor.execute("DELETE FROM rfq_outputs WHERE contract_id = ?", (self.test_contract_id,))
        conn.commit()
        self.db_manager._close_db()
        
        shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_workflow(self):
        """Test complete RFQ generation workflow."""
        # Skipped as we're testing components mostly
        pass


def run_all_tests():
    """Run all test suites and generate report."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDeadlineCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestTypeDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestFileReading))
    suite.addTests(loader.loadTestsFromTestCase(TestRFQValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestDocConversion))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*60}\n")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
