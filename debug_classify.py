
from template_schemas import classify_solicitation_type

text = "Subject: RFQ: N0010425QNF13 - 59--CABLE ASSEMBLY,SPEC, IN REPAIR/MODIFICATION OF. The contract contains requirements for repair and contract quality requirements for the CABLE ASSEMBLY,SPEC. All repair work shall be performed in accordance with the contractors repair/overhaul standard practices, manuals and directives including but not limited to drawings, technical orders, manufacturing operations, tooling instructions, approved repair standards and any other contractor or government approved documents developed to provide technical repair procedures. Material supplied is intended for use on submarines/surface ships and shall contain no metallic mercury and be free from mercury contamination."

classification = classify_solicitation_type(text)
print(f"Classification: {classification}")
