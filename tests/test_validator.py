"""
Unit tests for DME Order Validation and Zero-Guessing Policy.
"""

from datetime import date, timedelta
import os
import sys
import unittest

# Ensure api is in sys.path
api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.services.validator import (
    is_placeholder,
    parse_and_validate_dob,
    sanitize_name,
    sanitize_npi,
    sanitize_provider_name,
    validate_and_sanitize_order,
    validate_npi_luhn,
)


class TestValidator(unittest.TestCase):
    """Test suite for strict clinical data validation rules."""

    # ─── 1. Placeholder Detection Tests ──────────────────────────────────────

    def test_placeholder_detection(self):
        """Verify placeholder strings are recognized and treated as missing."""
        placeholders = [
            "", " ", "   ", "-", "--", "N/A", "n/a", "NA", "None", "NONE",
            "null", "Null", "Unknown", "unknown", "NOT PROVIDED", "Unspecified",
            "pending", "Missing", "blank"
        ]
        for p in placeholders:
            self.assertTrue(is_placeholder(p), f"Failed for placeholder: '{p}'")

        self.assertFalse(is_placeholder("John"))
        self.assertFalse(is_placeholder("1234567890"))
        self.assertFalse(is_placeholder("1980-05-14"))

    # ─── 2. Name Sanitization Tests ──────────────────────────────────────────

    def test_sanitize_name_valid(self):
        """Verify standard names are properly cleaned and preserved."""
        self.assertEqual(sanitize_name("John"), "John")
        self.assertEqual(sanitize_name("  Jane  "), "Jane")
        self.assertEqual(sanitize_name("O'Connor"), "O'Connor")
        self.assertEqual(sanitize_name("Smith-Jones"), "Smith-Jones")

    def test_sanitize_first_name_strips_prefixes(self):
        """Verify honorific prefixes are stripped from first names."""
        self.assertEqual(sanitize_name("Mr. Robert", is_first_name=True), "Robert")
        self.assertEqual(sanitize_name("Mrs. Eleanor", is_first_name=True), "Eleanor")
        self.assertEqual(sanitize_name("Ms. Sarah", is_first_name=True), "Sarah")
        self.assertEqual(sanitize_name("Patient: David", is_first_name=True), "David")

    def test_sanitize_name_zero_guessing_on_invalid(self):
        """Verify invalid or placeholder names strictly return None (no guessing)."""
        self.assertIsNone(sanitize_name(None))
        self.assertIsNone(sanitize_name(""))
        self.assertIsNone(sanitize_name("N/A"))
        self.assertIsNone(sanitize_name("Unknown"))
        self.assertIsNone(sanitize_name("12345"))  # No letters
        self.assertIsNone(sanitize_name("---"))

    # ─── 3. Provider Name Sanitization Tests ─────────────────────────────────

    def test_sanitize_provider_name(self):
        """Verify provider names are preserved and placeholders rejected."""
        self.assertEqual(sanitize_provider_name("Dr. Marcus Welby, MD"), "Dr. Marcus Welby, MD")
        self.assertEqual(sanitize_provider_name("Jane Smith, DO"), "Jane Smith, DO")
        self.assertIsNone(sanitize_provider_name("N/A"))
        self.assertIsNone(sanitize_provider_name("None"))
        self.assertIsNone(sanitize_provider_name(None))

    # ─── 4. Date of Birth Parsing & Validation Tests ─────────────────────────

    def test_parse_valid_dob_formats(self):
        """Verify multiple valid date formats normalize to ISO YYYY-MM-DD."""
        test_cases = [
            ("1980-05-14", "1980-05-14"),
            ("05/14/1980", "1980-05-14"),
            ("5/14/1980", "1980-05-14"),
            ("05-14-1980", "1980-05-14"),
            ("May 14, 1980", "1980-05-14"),
            ("14 May 1980", "1980-05-14"),
            ("DOB: 1985-12-01", "1985-12-01"),
            ("Date of Birth: 03/22/1992", "1992-03-22"),
        ]
        for raw, expected in test_cases:
            cleaned, err = parse_and_validate_dob(raw)
            self.assertIsNone(err, f"Unexpected error for '{raw}': {err}")
            self.assertEqual(cleaned, expected, f"Failed converting '{raw}'")

    def test_dob_future_date_rejected(self):
        """Verify dates in the future are strictly rejected."""
        tomorrow = date.today() + timedelta(days=1)
        cleaned, err = parse_and_validate_dob(tomorrow.isoformat())
        self.assertIsNone(cleaned)
        self.assertIn("cannot be in the future", err)

    def test_dob_ancient_date_rejected(self):
        """Verify dates before 1900 are rejected."""
        cleaned, err = parse_and_validate_dob("1880-01-01")
        self.assertIsNone(cleaned)
        self.assertIn("outside valid clinical range", err)

    def test_dob_invalid_calendar_date_rejected(self):
        """Verify invalid calendar days (e.g. Feb 30) are rejected."""
        cleaned, err = parse_and_validate_dob("02/30/1990")
        self.assertIsNone(cleaned)
        self.assertIn("Could not parse date of birth", err)

    def test_dob_placeholder_returns_none(self):
        """Verify missing or placeholder DOB strictly returns None."""
        for p in [None, "", "N/A", "Unknown", "Missing"]:
            cleaned, err = parse_and_validate_dob(p)
            self.assertIsNone(cleaned)
            self.assertIsNotNone(err)

    # ─── 5. Provider NPI Validation Tests ────────────────────────────────────

    def test_npi_luhn_valid(self):
        """Verify known real CMS NPI checksums pass."""
        valid_npis = [
            "1234567893",  # Standard CMS example
            "1497746457",  # Valid Luhn NPI
            "1679584171",  # Valid Luhn NPI
            "1083692859",  # Valid Luhn NPI
        ]
        for npi in valid_npis:
            self.assertTrue(validate_npi_luhn(npi), f"Valid NPI failed Luhn check: {npi}")

    def test_npi_luhn_invalid(self):
        """Verify invalid NPI check digits fail Luhn check."""
        invalid_npis = [
            "1234567890",  # Check digit should be 3
            "1111111111",  # Invalid checksum
            "9999999999",  # Invalid checksum
        ]
        for npi in invalid_npis:
            self.assertFalse(validate_npi_luhn(npi), f"Invalid NPI passed Luhn check: {npi}")

    def test_sanitize_npi_must_be_10_digits(self):
        """Verify NPIs with wrong digit counts are rejected."""
        # Too short (9 digits)
        cleaned, err = sanitize_npi("123456789")
        self.assertIsNone(cleaned)
        self.assertIn("must be exactly 10 digits", err)

        # Too long (11 digits)
        cleaned, err = sanitize_npi("12345678901")
        self.assertIsNone(cleaned)
        self.assertIn("must be exactly 10 digits", err)

        # Letters / non-digits
        cleaned, err = sanitize_npi("ABCDEFGHIJ")
        self.assertIsNone(cleaned)
        self.assertIn("contains no digits", err)

        # Missing / Placeholder
        for p in [None, "", "N/A", "Pending", "Unknown"]:
            cleaned, err = sanitize_npi(p)
            self.assertIsNone(cleaned)
            self.assertIn("missing", err.lower())

    # ─── 6. Full Order Zero-Guessing Integration Tests ───────────────────────

    def test_validate_and_sanitize_complete_order_verified(self):
        """Verify an order with all 5 valid clinical fields gets status 'verified'."""
        raw_order = {
            "patient_first_name": "Eleanor",
            "patient_last_name": "Vance",
            "patient_dob": "05/14/1980",
            "provider_name": "Dr. Marcus Welby, MD",
            "provider_npi": "1497746459",
        }
        sanitized, issues = validate_and_sanitize_order(raw_order)

        self.assertEqual(len(issues), 0)
        self.assertEqual(sanitized["status"], "verified")
        self.assertEqual(sanitized["patient_first_name"], "Eleanor")
        self.assertEqual(sanitized["patient_last_name"], "Vance")
        self.assertEqual(sanitized["patient_dob"], "1980-05-14")
        self.assertEqual(sanitized["provider_name"], "Dr. Marcus Welby, MD")
        self.assertEqual(sanitized["provider_npi"], "1497746459")

    def test_validate_and_sanitize_missing_dob_needs_review(self):
        """Verify missing DOB results in status 'needs_review' and DOB stays None."""
        raw_order = {
            "patient_first_name": "Eleanor",
            "patient_last_name": "Vance",
            "patient_dob": None,  # Missing DOB from fax
            "provider_name": "Dr. Marcus Welby",
            "provider_npi": "1497746459",
        }
        sanitized, issues = validate_and_sanitize_order(raw_order)

        self.assertEqual(sanitized["status"], "needs_review")
        self.assertIsNone(sanitized["patient_dob"])
        self.assertTrue(any("Date of birth" in i for i in issues))

    def test_validate_and_sanitize_missing_npi_needs_review(self):
        """Verify missing NPI results in status 'needs_review' and NPI stays None."""
        raw_order = {
            "patient_first_name": "John",
            "patient_last_name": "Doe",
            "patient_dob": "1975-08-20",
            "provider_name": "Dr. Jane Smith",
            "provider_npi": "N/A",  # Missing on messy fax
        }
        sanitized, issues = validate_and_sanitize_order(raw_order)

        self.assertEqual(sanitized["status"], "needs_review")
        self.assertIsNone(sanitized["provider_npi"])
        self.assertTrue(any("NPI" in i for i in issues))

    def test_zero_guessing_all_missing(self):
        """Verify completely empty extraction results in all None and 'needs_review'."""
        empty_order = {
            "patient_first_name": None,
            "patient_last_name": None,
            "patient_dob": None,
            "provider_name": None,
            "provider_npi": None,
        }
        sanitized, issues = validate_and_sanitize_order(empty_order)

        self.assertEqual(sanitized["status"], "needs_review")
        self.assertIsNone(sanitized["patient_first_name"])
        self.assertIsNone(sanitized["patient_last_name"])
        self.assertIsNone(sanitized["patient_dob"])
        self.assertIsNone(sanitized["provider_name"])
        self.assertIsNone(sanitized["provider_npi"])
        self.assertEqual(len(issues), 5)


if __name__ == "__main__":
    unittest.main()
