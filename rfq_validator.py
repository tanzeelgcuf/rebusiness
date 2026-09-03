"""
RFQ quality gate. Runs after LLM generation, before an RFQ is eligible
for the human-approval queue or vendor submission.

Goal: catch the "RFQ for Product" (15-char stub) failure mode automatically,
so bad generations get flagged instead of silently sitting in the DB or
(worse) going out to a vendor.
"""

from dataclasses import dataclass, field
import re

REQUIRED_FIELDS = ["scope", "quantity", "deadline", "delivery_location", "contact"]
MIN_BODY_LENGTH = 200
# Short numeric/quantity fields (e.g. "500 units") shouldn't need the same
# minimum length as prose fields like scope or delivery_location.
MIN_FIELD_LENGTH = 10
SHORT_FIELD_OVERRIDES = {"quantity": 3, "deadline": 4}

# Phrases that indicate the LLM produced a placeholder/refusal instead of real content
STUB_PATTERNS = [
    r"^\s*RFQ for \w+\s*$",
    r"^\s*\[.*\]\s*$",          # e.g. "[insert product here]"
    r"lorem ipsum",
    r"as an ai( language model)?",
    r"i (cannot|can't|am unable to)",
    r"placeholder",
]


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)
    severity: str = "ok"  # "ok" | "warning" | "reject"


def validate_rfq(rfq: dict) -> ValidationResult:
    issues = []

    body = rfq.get("body", "") or ""
    if len(body) < MIN_BODY_LENGTH:
        issues.append(f"body too short ({len(body)} chars, need {MIN_BODY_LENGTH}+)")

    for pattern in STUB_PATTERNS:
        if re.search(pattern, body, re.IGNORECASE):
            issues.append(f"body matches stub/refusal pattern: '{pattern}'")

    for f in REQUIRED_FIELDS:
        val = rfq.get(f)
        min_len = SHORT_FIELD_OVERRIDES.get(f, MIN_FIELD_LENGTH)
        if not val or len(str(val).strip()) < min_len:
            issues.append(f"missing or too short: '{f}'")

    # Sanity check: deadline should look like a date, not empty prose
    deadline = str(rfq.get("deadline", ""))
    if deadline and not re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", deadline):
        issues.append(f"deadline doesn't look like a parseable date: '{deadline}'")

    if not issues:
        return ValidationResult(is_valid=True, severity="ok")

    # Hard rejects: stub patterns or missing body entirely
    hard_fail = any("stub/refusal" in i or "body too short" in i for i in issues)
    severity = "reject" if hard_fail else "warning"
    return ValidationResult(is_valid=False, issues=issues, severity=severity)


def validate_batch(rfqs: list[dict]) -> dict:
    """Run validation across a batch, return summary counts + per-item results."""
    results = {"ok": [], "warning": [], "reject": []}
    for rfq in rfqs:
        result = validate_rfq(rfq)
        bucket = result.severity
        results[bucket].append({"rfq_id": rfq.get("id"), "result": result})
    return {
        "total": len(rfqs),
        "ok": len(results["ok"]),
        "warning": len(results["warning"]),
        "reject": len(results["reject"]),
        "details": results,
    }


if __name__ == "__main__":
    sample_good = {
        "id": 1,
        "scope": "Procurement of 500 units of industrial-grade steel brackets per attached spec sheet.",
        "quantity": "500 units",
        "deadline": "2026-09-30",
        "delivery_location": "1200 Industrial Pkwy, Columbus, OH 44201",
        "contact": "procurement@example.com",
        "body": "We are requesting quotes for 500 units of industrial-grade steel brackets "
                "meeting ASTM A36 specifications. Delivery required to our Columbus, OH facility "
                "no later than September 30, 2026. Please include unit pricing, lead time, and "
                "shipping terms in your quote. Contact procurement@example.com with questions." * 1,
    }
    sample_stub = {"id": 2, "body": "RFQ for Product"}

    print(validate_rfq(sample_good))
    print(validate_rfq(sample_stub))
    print(validate_batch([sample_good, sample_stub]))