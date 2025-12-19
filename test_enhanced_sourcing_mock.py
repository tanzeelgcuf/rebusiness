import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import sys

# Mock modules before import
sys.modules['ai_agents.ThomasNetAgent.thomasnet_agent'] = MagicMock()
sys.modules['ai_agents.OutreachAgent.form_filler'] = MagicMock()
sys.modules['database_manager'] = MagicMock()

# Now import the script logic (we need to import it as a module or load source)
# Since run_enhanced_sourcing is a script, we might need to modify it to be importable or just exec it.
# Easier: Just exec the file content with mocked globals.

class TestEnhancedWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_logic(self):
        # Mocks
        mock_db = MagicMock()
        mock_tn = MagicMock()
        mock_filler = AsyncMock()
        
        # Setup DB returns
        mock_db._connect_db.return_value = MagicMock()
        mock_cursor = mock_db._connect_db.return_value.cursor.return_value
        # Return 1 pending product
        mock_cursor.execute.return_value.fetchall.return_value = [
            (101, "Test Bolt", "SOL-123", "2025-01-01")
        ]
        
        # Setup ThomasNet returns
        mock_tn.find_suppliers_for_product.return_value = [
            {'name': 'Supplier A', 'website': 'http://a.com', 'location': 'US'},
            {'name': 'Supplier B', 'website': 'http://b.com', 'location': 'CA'}
        ]
        
        # Setup Outreach returns
        mock_filler.process_supplier_outreach.return_value = {
            'form_filled': True, 'emails_sent': 1, 'emails_found': ['a@a.com'], 'error': None
        }

        # Inject into global namespace for exec
        global_vars = {
            'DatabaseManager': MagicMock(return_value=mock_db),
            'ThomasNetAgent': MagicMock(return_value=mock_tn),
            'FormFiller': MagicMock(return_value=mock_filler),
            'asyncio': asyncio,
            'time': MagicMock(),
            'LIMIT_SUPPLIERS': 2
        }
        
        # Read the script
        with open('run_enhanced_sourcing.py', 'r') as f:
            script_content = f.read()
        
        # Strip imports so our injected globals are used
        script_content = script_content.replace('from database_manager import DatabaseManager', 'pass')
        script_content = script_content.replace('from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent', 'pass')
        script_content = script_content.replace('from ai_agents.OutreachAgent.form_filler import FormFiller', 'pass')

        # We need to strip the "if __name__" block to avoid auto-run
        script_content = script_content.replace('if __name__ == "__main__":', 'if False:')
        
        # Execute script definition to get the function
        exec(script_content, global_vars)
        
        # Run the function
        await global_vars['run_enhanced_workflow']()
        
        # Assertions
        # 1. DB should fetch products
        mock_db.update_sourcing_status.assert_any_call(101, 'sourcing')
        
        # 2. TN Agent called
        mock_tn.find_suppliers_for_product.assert_called_with({'product_name': 'Test Bolt'}, limit=2) # Uses global LIMIT
        
        # 3. Outreach called for each supplier
        self.assertEqual(mock_filler.process_supplier_outreach.call_count, 2)
        mock_filler.process_supplier_outreach.assert_any_call('http://a.com', {
            'product_name': 'Test Bolt',
            'notice_id': 'SOL-123',
            'due_date': '2025-01-01', 
            'quantity': 'See attached/linked solicitation'
        })
        
        # 4. Final Status Update
        mock_db.update_sourcing_status.assert_called_with(101, 'outreach_complete', found_inc=2)
        print("Test Passed: Workflow Orchestration verified.")

if __name__ == "__main__":
    unittest.main()
