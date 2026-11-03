#!/usr/bin/env python3
"""
Unified Test Runner for GenHealth DME Order Intake Service.
Discovers and executes all unit and integration tests.
"""

import os
import sys
import unittest

# Ensure api directory and root are in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(root_dir, "api")

for path in (root_dir, api_dir):
    if path not in sys.path:
        sys.path.insert(0, path)


def run_all_tests():
    print("=" * 70)
    print(" GenHealth AI — DME Order Intake Service: Running Test Suite")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(root_dir, "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f" Summary: Ran {result.testsRun} tests.")
    if result.wasSuccessful():
        print(" ALL TESTS PASSED! Strict zero-guessing & validation confirmed.")
        print("=" * 70)
        return 0
    else:
        print(f" TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

