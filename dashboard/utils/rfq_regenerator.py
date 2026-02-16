"""
RFQ Regeneration Utility
Handles regeneration of single or batch RFQs
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager
import glob

def regenerate_single_rfq(contract_id):
    """
    Regenerate a single RFQ
    
    Args:
        contract_id: Contract ID to regenerate
        
    Returns:
        dict: {'success': bool, 'message': str, 'contract_id': str}
    """
    try:
        print(f"Regenerating RFQ for {contract_id}...")
        
        # Initialize agent
        reader = AttachmentReaderAgent()
        
        # Regenerate
        result = reader.create_summary_report(
            notice_id=contract_id,
            skip_json=True,
            strict_fidelity=True,
            enable_self_healing=True,
            max_healing_iterations=3
        )
        
        if result.get('success'):
            return {
                'success': True,
                'message': f'RFQ regenerated successfully for {contract_id}',
                'contract_id': contract_id
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'contract_id': contract_id
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'contract_id': contract_id
        }

def regenerate_batch(contract_ids):
    """
    Regenerate multiple RFQs
    
    Args:
        contract_ids: List of contract IDs
        
    Returns:
        list: List of results for each RFQ
    """
    results = []
    
    for contract_id in contract_ids:
        result = regenerate_single_rfq(contract_id)
        results.append(result)
    
    return results

if __name__ == "__main__":
    # Test regeneration
    if len(sys.argv) > 1:
        contract_id = sys.argv[1]
        result = regenerate_single_rfq(contract_id)
        print(result)
    else:
        print("Usage: python rfq_regenerator.py <contract_id>")
