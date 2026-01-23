#!/usr/bin/env python3
"""Check RFQ for our specific fixes"""
from docx import Document
import re

doc = Document('./rfq_downloads/2026-01-17/f3d327c5ae8341f0a54658b1283ce4c7_RFQ_PRODUCT.docx')
text = '\n'.join([p.text for p in doc.paragraphs])

print("=" * 80)
print("RFQ QUALITY FIX VERIFICATION")
print("=" * 80)
print()

# Check Fix 1: Date consistency
print("✅ FIX 1: DATE CONSISTENCY")
dates = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b', text)
print(f"Found {len(dates)} dates in 'Month DD, YYYY' format:")
for d in dates[:10]:
    print(f"  - {d}")
print()

# Check Fix 2: Table headers
print("✅ FIX 2: TABLE HEADERS")
if "CLIN Table" in text:
    print("✓ CLIN Table section found")
    # Check if instruction text leaked
    if "CRITICAL: ALWAYS include the header row" in text:
        print("❌ WARNING: Instruction text leaked into output!")
    else:
        print("✓ No instruction leakage")
else:
    print("❌ CLIN Table section not found")
print()

# Check Fix 3: Complete requirements language
print("✅ FIX 3: COMPLETE REQUIREMENTS DISCLOSURE")
if "interested in bidding" in text.lower():
    print("❌ FAILED: Old 'interested in bidding' language still present")
elif "All requirements, specifications, and compliance criteria are detailed below" in text:
    print("✓ PASSED: New complete requirements language found")
else:
    print("⚠️  WARNING: Neither old nor new language found")
print()

# Check Fix 4: Certification formatting
print("✅ FIX 4: CERTIFICATION FORMATTING")
if "Camp Sable Requirements (for all bidders):" in text:
    print("✓ PASSED: Camp Sable requirements section found")
    if "(This is a Camp Sable requirement.)" in text:
        print("✓ PASSED: Camp Sable requirements properly labeled")
    else:
        print("⚠️  WARNING: Camp Sable requirements not labeled")
else:
    print("❌ FAILED: Camp Sable requirements section missing")

if "Government Requirements (from solicitation):" in text:
    print("✓ PASSED: Government requirements section found")
else:
    print("❌ FAILED: Government requirements section missing")

# Check for conditional markers
if "**IF Defense:**" in text or "**IF ITAR:**" in text:
    print("❌ FAILED: Conditional markers still present in output")
else:
    print("✓ PASSED: No conditional markers in output")

print()
print("=" * 80)
