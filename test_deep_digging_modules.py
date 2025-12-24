
import sys
import os
import unittest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
from SamGovAgent.sam_gov_agent import SamGovAgent
from AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

class TestDeepDigging(unittest.TestCase):
    def test_sam_gov_link_extraction(self):
        agent = SamGovAgent()
        text = """
        This is a solicitation description.
        Please see specs at https://www.dropbox.com/s/12345/specs.pdf
        Also visit http://drive.google.com/file/d/abcdefg for more info.
        Ignore this: https://www.google.com/search?q=ignore
        """
        links = agent._extract_external_links(text)
        print(f"SamGov Extracted: {links}")
        target = ['https://www.dropbox.com/s/12345/specs.pdf', 'http://drive.google.com/file/d/abcdefg']
        for t in target:
            self.assertIn(t, links)
        self.assertNotIn('https://www.google.com/search?q=ignore', links)
        agent.close()

    def test_reader_link_filtering(self):
        reader = AttachmentReaderAgent()
        text = "Check out https://valid.com/file.zip and ignore https://google.com/search"
        # We simulate the inner method logic since we can't easily mock the full LLM flow in unit test without cost
        regex_links = reader._extract_links_from_content(text)
        print(f"Reader Extracted: {regex_links}")
        self.assertIn('https://valid.com/file.zip', regex_links[0] if regex_links else '')

if __name__ == '__main__':
    unittest.main()
