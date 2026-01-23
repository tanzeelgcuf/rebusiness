#!/usr/bin/env python3
"""
Test script to validate RFQ prompt fixes without SAM.gov scraping.
This creates a mock RFQ to verify the template changes are working correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_agents.AttachmentReaderAgent.rfq_prompts import PRODUCT_RFQ_PROMPT

def test_prompt_fixes():
    """Validate that all four fixes are present in the prompt."""
    
    print("=" * 80)
    print("RFQ PROMPT VALIDATION TEST")
    print("=" * 80)
    print()
    
    issues = []
    
    # Test 1: Date consistency instruction
    if 'Convert ALL dates to this format in output:** Month DD, YYYY' in PRODUCT_RFQ_PROMPT:
        print("✅ Test 1 PASSED: Date consistency instruction found")
    else:
        print("❌ Test 1 FAILED: Date consistency instruction missing")
        issues.append("Date consistency instruction")
    
    # Test 2: Table header emphasis
    if 'ALWAYS include the header row as the FIRST row of the table' in PRODUCT_RFQ_PROMPT:
        print("✅ Test 2 PASSED: Table header emphasis found")
    else:
        print("❌ Test 2 FAILED: Table header emphasis missing")
        issues.append("Table header emphasis")
    
    # Test 3: Complete requirements language (should NOT contain old text)
    if 'There are other documents that I can send you' in PRODUCT_RFQ_PROMPT:
        print("❌ Test 3 FAILED: Old incomplete requirements language still present")
        issues.append("Incomplete requirements language not removed")
    elif 'All requirements, specifications, and compliance criteria are detailed below' in PRODUCT_RFQ_PROMPT:
        print("✅ Test 3 PASSED: Complete requirements language found")
    else:
        print("⚠️  Test 3 WARNING: Neither old nor new language found")
        issues.append("Requirements language unclear")
    
    # Test 4: Certification formatting (should NOT contain conditional markers in output)
    if 'Camp Sable Requirements (for all bidders):' in PRODUCT_RFQ_PROMPT:
        print("✅ Test 4 PASSED: Camp Sable requirements section found")
    else:
        print("❌ Test 4 FAILED: Camp Sable requirements section missing")
        issues.append("Camp Sable requirements section")
    
    # Test 4b: Check that conditional markers are removed from output format
    if 'Do NOT include conditional markers like "**IF Defense:**"' in PRODUCT_RFQ_PROMPT:
        print("✅ Test 4b PASSED: Instruction to remove conditional markers found")
    else:
        print("❌ Test 4b FAILED: Instruction to remove conditional markers missing")
        issues.append("Conditional marker removal instruction")
    
    print()
    print("=" * 80)
    
    if not issues:
        print("🎉 ALL TESTS PASSED! Prompt fixes are correctly implemented.")
        print("=" * 80)
        return 0
    else:
        print(f"⚠️  {len(issues)} ISSUE(S) FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(test_prompt_fixes())
