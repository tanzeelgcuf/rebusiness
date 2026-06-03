import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import classes to test
try:
    from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
    from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT, SERVICE_RFQ_PROMPT
except ImportError as e:
    print(f"Import Error: {e}")
    # Fallback to absolute if path append fails?
    sys.path.append("/Users/apple/Downloads/rebusinessautomationproject")
    from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
    from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT, SERVICE_RFQ_PROMPT

class TestRFQGeneration(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.reader = AttachmentReaderAgent()
        
    def test_type_detection(self):
        """Test Case 2: Type Detection"""
        # Product Product Indicators
        prod_content = ["This solicitation requires NSN 1234-56-789-0000. CAGE Code 12345 required. IPI is mandatory."]
        self.assertEqual(self.reader._detect_type(prod_content), "PRODUCT")
        
        # Service Indicators
        svc_content = ["The contractor shall provide maintenance services. Reference PWS Section 5."]
        self.assertEqual(self.reader._detect_type(svc_content), "SERVICE")
        
        # Ambiguous case (PWS implies Service)
        mixed_content = ["NSN items included but also refer to PWS for installation."]
        self.assertEqual(self.reader._detect_type(mixed_content), "SERVICE")

    def test_prompt_integrity(self):
        """Test Case 3, 4, 5: Prompt Integrity Checks"""
        # Ensure Critical Rules are in Product Prompt
        self.assertIn("Internal deadline calculated (4 business days before official)", PRODUCT_RFQ_PROMPT)
        self.assertIn("bobbysmitty078@gmail.com", PRODUCT_RFQ_PROMPT)
        self.assertIn("NO OTHER BOLD", PRODUCT_RFQ_PROMPT)
        self.assertIn("PRODUCT RFQ SPECIFIC REQUIREMENTS", PRODUCT_RFQ_PROMPT)
        
        # Ensure Critical Rules are in Service Prompt
        self.assertIn("Internal deadline calculated (4 business days before official)", SERVICE_RFQ_PROMPT)
        self.assertIn("bobbysmitty078@gmail.com", SERVICE_RFQ_PROMPT)
        self.assertIn("NO OTHER BOLD", SERVICE_RFQ_PROMPT)
        self.assertIn("SERVICE RFQ SPECIFIC REQUIREMENTS", SERVICE_RFQ_PROMPT)

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_content_product(self, mock_model_cls):
        """Test Case 6: Mocked LLM Integration (Product Path)"""
        # Mock the Gemini Model response
        mock_instance = mock_model_cls.return_value
        mock_response = MagicMock()
        # Ensure text is > 100 chars to pass validation
        mock_response.text = ("# RFQ Output\n\nThis is a mocked Product RFQ that is long enough to pass validation. "
                              "It needs to be at least 100 characters long to avoid the empty response check. "
                              "Adding more text here to be sure.\n\n### 🔹 Overview")
        mock_instance.generate_content.return_value = mock_response
        
        content = ["NSN 1234. Please supply."]
        
        # Run analysis
        result = self.reader._analyze_content_with_llm(content, strict_fidelity=True)
        
        # Verify
        self.assertEqual(result['rfq_type'], "PRODUCT")
        self.assertIn("# RFQ Output", result['rfq_content'])
        self.assertTrue(result['success'])
        
        # Verify the prompt contained the PRODUCT_RFQ_PROMPT
        args, kwargs = mock_instance.generate_content.call_args
        sent_prompt = args[0]
        self.assertIn(PRODUCT_RFQ_PROMPT, sent_prompt)

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_content_service(self, mock_model_cls):
        """Test Case 6b: Mocked LLM Integration (Service Path)"""
        mock_instance = mock_model_cls.return_value
        mock_response = MagicMock()
        mock_response.text = ("# RFQ Output\n\nThis is a mocked Service RFQ that is long enough to pass validation. "
                              "It needs to be at least 100 characters long to avoid the empty response check. "
                              "Adding more text here to be sure.")
        mock_instance.generate_content.return_value = mock_response
        
        content = ["See PWS for details."]
        
        result = self.reader._analyze_content_with_llm(content, strict_fidelity=True)
        
        self.assertEqual(result['rfq_type'], "SERVICE")
        self.assertTrue(result['success'])
        
        args, kwargs = mock_instance.generate_content.call_args
        sent_prompt = args[0]
        self.assertIn(SERVICE_RFQ_PROMPT, sent_prompt)

if __name__ == '__main__':
    unittest.main()
