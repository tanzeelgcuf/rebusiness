"""CLI for procurement source scrapers.

Usage:
    python -m source_scrapers.cli usaspending --limit 50
    python -m source_scrapers.cli federal_register --limit 20
    python -m source_scrapers.cli regulations --limit 20
    python -m source_scrapers.cli all --limit 20
"""
import argparse
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s")


def get_agent(name):
    if name == "usaspending":
        from .usaspending import USAspendingAgent
        return USAspendingAgent
    if name == "federal_register":
        from .federal_register import FederalRegisterAgent
        return FederalRegisterAgent
    if name == "regulations":
        from .regulations import RegulationsAgent
        return RegulationsAgent
    raise KeyError(f"Unknown source: {name}")


def main():
    ap = argparse.ArgumentParser(description="Procurement source scrapers")
    ap.add_argument("source", help="usaspending | federal_register | regulations | all")
    ap.add_argument("--limit", type=int, default=50,
                    help="max records per source (default 50)")
    ap.add_argument("--db", default=None,
                    help="override source DB path")
    args = ap.parse_args()

    sources = ["usaspending", "federal_register", "regulations"]
    if args.source != "all":
        sources = [args.source]

    for src in sources:
        cls = get_agent(src)
        try:
            agent = cls(limit=args.limit)
            if args.db:
                agent.db = agent.db.__class__(args.db)
            added, seen = agent.load()
            print(f"[{src}] added={added} seen={seen}")
        except Exception as e:
            print(f"[{src}] FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
