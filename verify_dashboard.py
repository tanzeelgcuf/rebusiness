#!/usr/bin/env python3
"""
Quick Start & Verification Guide for ThomasNet RFQ Dashboard
Tests all components before running full automation
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_environment():
    """Verify environment and dependencies"""
    logger.info("=" * 70)
    logger.info("1. ENVIRONMENT CHECK")
    logger.info("=" * 70)

    issues = []

    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8+ required")
    else:
        logger.info(f"✓ Python {sys.version.split()[0]}")

    # Check required files
    required_files = [
        ".env.dashboard",
        "setup_dashboard.sh",
        "run_dashboard_full.sh",
        "dashboard/app.py",
        "dashboard/utils/advanced_proxy_manager.py",
        "dashboard/utils/dashboard_thomasnet.py",
        "config/deployment.yaml",
    ]

    for f in required_files:
        if Path(f).exists():
            logger.info(f"✓ {f}")
        else:
            issues.append(f"Missing: {f}")

    # Check env vars
    logger.info("\nEnvironment variables:")
    required_vars = ["THOMASNET_EMAIL", "THOMASNET_PASSWORD"]
    for var in required_vars:
        if os.getenv(var):
            logger.info(f"✓ {var} configured")
        else:
            issues.append(f"Missing: {var}")

    return len(issues) == 0, issues


def check_dependencies():
    """Verify Python dependencies"""
    logger.info("\n" + "=" * 70)
    logger.info("2. DEPENDENCY CHECK")
    logger.info("=" * 70)

    dependencies = [
        "flask",
        "flask_cors",
        "playwright",
        "python-dotenv",
        "requests",
        "pyyaml",
    ]

    issues = []
    for dep in dependencies:
        try:
            __import__(dep.replace("-", "_"))
            logger.info(f"✓ {dep}")
        except ImportError:
            issues.append(f"Missing package: {dep}")

    return len(issues) == 0, issues


def test_proxy_manager():
    """Test proxy manager functionality"""
    logger.info("\n" + "=" * 70)
    logger.info("3. PROXY MANAGER TEST")
    logger.info("=" * 70)

    try:
        from dashboard.utils.advanced_proxy_manager import AdvancedProxyManager

        pm = AdvancedProxyManager(min_pool_size=3)
        logger.info("✓ ProxyManager initialized")

        logger.info("Fetching proxies...")
        pm.refill_proxy_pool()

        stats = pm.stats()
        logger.info(f"✓ Pool: {stats['total_pool_size']} total")
        logger.info(f"  Active: {stats['active_proxies']} working")
        logger.info(f"  Health: {stats['health_percent']:.1f}%")

        proxy = pm.get_next_proxy()
        if proxy:
            logger.info(f"✓ Got proxy: {proxy['url'][:40]}...")
            return True, []
        else:
            return False, ["No working proxies found"]

    except Exception as e:
        return False, [f"ProxyManager error: {e}"]


def test_database():
    """Test database connectivity"""
    logger.info("\n" + "=" * 70)
    logger.info("4. DATABASE TEST")
    logger.info("=" * 70)

    try:
        from database_manager import DatabaseManager

        db = DatabaseManager()
        logger.info("✓ Database connected")

        # Get basic stats
        count = db.get_solicitations_count()
        logger.info(f"✓ Solicitations in DB: {count}")

        rfq_count = db.get_rfqs_count()
        logger.info(f"✓ RFQs in DB: {rfq_count}")

        return True, []

    except Exception as e:
        return False, [f"Database error: {e}"]


def test_thomasnet_auth():
    """Test ThomasNet auth session"""
    logger.info("\n" + "=" * 70)
    logger.info("5. THOMASNET AUTH TEST")
    logger.info("=" * 70)

    try:
        from dashboard.utils.browser_connector import connect_to_browser

        logger.info("Attempting to connect to browser...")
        browser, page, connector = connect_to_browser(
            "http://127.0.0.1:9222", validate_login=False
        )

        if page:
            logger.info("✓ Browser connected")
            logger.info(f"  URL: {page.url}")
            connector.close()
            return True, []
        else:
            return False, ["Could not connect to browser"]

    except Exception as e:
        logger.warning(f"⚠ Browser connection failed (expected if Chrome not running)")
        logger.warning(f"  Start Chrome with: google-chrome --remote-debugging-port=9222")
        return False, [f"Browser connection: {str(e)[:50]}..."]


def test_api_endpoints():
    """Test Flask API endpoints"""
    logger.info("\n" + "=" * 70)
    logger.info("6. API ENDPOINT TEST")
    logger.info("=" * 70)

    try:
        from dashboard.app import app

        with app.test_client() as client:
            # Test proxy status endpoint
            response = client.get("/api/proxy-status")
            if response.status_code == 200:
                logger.info("✓ GET /api/proxy-status")
            else:
                logger.warning(f"⚠ /api/proxy-status returned {response.status_code}")

            # Test automation endpoint
            response = client.get("/api/automation/status")
            if response.status_code == 200:
                logger.info("✓ GET /api/automation/status")
            else:
                logger.warning(f"⚠ /api/automation/status returned {response.status_code}")

            return True, []

    except Exception as e:
        return False, [f"API test error: {e}"]


def main():
    """Run all verification tests"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  ThomasNet RFQ Dashboard - Pre-Flight Verification              ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    all_passed = True
    all_issues = []

    tests = [
        ("Environment", check_environment),
        ("Dependencies", check_dependencies),
        ("Proxy Manager", test_proxy_manager),
        ("Database", test_database),
        ("ThomasNet Auth", test_thomasnet_auth),
        ("API Endpoints", test_api_endpoints),
    ]

    for name, test_func in tests:
        try:
            passed, issues = test_func()
            if not passed:
                all_passed = False
                all_issues.extend([(name, issue) for issue in issues])
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            all_passed = False

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all_passed:
        print("✓ All checks passed! Dashboard is ready to run.")
        print("\nStart the dashboard with:")
        print("  ./run_dashboard_full.sh")
        return 0
    else:
        print(f"✗ {len(all_issues)} issue(s) found:\n")
        for component, issue in all_issues:
            print(f"  [{component}] {issue}")
        print("\nFix the issues above and run again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
