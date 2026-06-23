#!/usr/bin/env python3
"""
Export existing RFQ files to markdown format for ThomasNet submission testing.
This bridges the gap between the text RFQs we have and what the submission system expects.
"""

import os
import sys
from pathlib import Path
import shutil

def export_rfqs_to_markdown():
    """Export text RFQs to markdown format for CLI processing"""

    project_root = Path(__file__).parent
    rfq_files = list(project_root.glob('*RFQ*.txt'))

    if not rfq_files:
        print("No RFQ text files found in project root")
        return False

    # Create output directory
    output_dir = project_root / 'generated_rfqs'
    output_dir.mkdir(exist_ok=True)

    print(f"Exporting {len(rfq_files)} RFQ files to {output_dir}")

    for rfq_file in rfq_files[:1]:  # Start with just one for testing
        print(f"\nProcessing: {rfq_file.name}")

        # Read the RFQ content
        with open(rfq_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Create markdown version
        # Extract the contract ID or use filename
        base_name = rfq_file.stem  # e.g., "N0010425QNF13_RFQ_service_final_V7"

        # Convert to markdown
        md_content = f"""# Request for Quote (RFQ)

{content}

---
**Source:** {rfq_file.name}
**Format:** Markdown export for ThomasNet submission
"""

        # Save as markdown
        output_file = output_dir / f"{base_name}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"✓ Exported to: {output_file.name}")
        print(f"  Content length: {len(md_content)} bytes")

    # Also create a simple test RFQ if none exist
    test_rfq_path = output_dir / "test_rfq.md"
    if not test_rfq_path.exists():
        test_content = """# Test RFQ - Cable Assembly Repair

## Product Requirements

We are seeking quotes for the following:

**Item:** Cable Assembly, SPEC (NSN: 5995-01-604-0910)
**Quantity:** 2 units
**Service:** Teardown, Evaluate, Repair and/or Modify

## Scope of Work

Repair and modification services to restore Cable Assembly units to operable condition.

- Teardown and evaluation
- Repair services
- Quality testing
- Packaging and marking per MIL standards

## Timeline

Response needed by: February 23, 2026

## Contact

Please submit quotes to: bobbysmitty078@gmail.com

---
This is a test RFQ for ThomasNet submission workflow validation.
"""
        with open(test_rfq_path, 'w') as f:
            f.write(test_content)
        print(f"\n✓ Created test RFQ: {test_rfq_path.name}")

    return True

if __name__ == '__main__':
    success = export_rfqs_to_markdown()
    sys.exit(0 if success else 1)
