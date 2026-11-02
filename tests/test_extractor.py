"""
Unit tests for the DME PDF Extractor service and LLM response parsing.
"""

import os
import sys
import unittest

# Ensure api is in sys.path
api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.services.extractor import (
    fallback_extract_from_pdf_text,
    parse_json_from_llm_response,
)


class TestExtractor(unittest.TestCase):
    """Test suite for PDF extraction parsing, markdown handling, and fallback logic."""

    # ─── 1. LLM JSON Response Parsing Tests ──────────────────────────────────

    def test_parse_clean_json(self):
        """Verify standard JSON parses cleanly."""
        raw = '{"patient_first_name": "Eleanor", "patient_last_name": "Vance", "patient_dob": "1980-05-14", "provider_name": "Dr. Marcus Welby", "provider_npi": "1234567893"}'
        result = parse_json_from_llm_response(raw)
        self.assertEqual(result["patient_first_name"], "Eleanor")
        self.assertEqual(result["patient_last_name"], "Vance")
        self.assertEqual(result["patient_dob"], "1980-05-14")
        self.assertEqual(result["provider_name"], "Dr. Marcus Welby")
        self.assertEqual(result["provider_npi"], "1234567893")

    def test_parse_json_inside_code_fences(self):
        """Verify JSON wrapped inside markdown code fences is extracted."""
        raw = """Here is the extracted clinical data:
```json
{
  "patient_first_name": "John",
  "patient_last_name": "Doe",
  "patient_dob": "1972-11-03",
  "provider_name": "Dr. Sarah Connor",
  "provider_npi": "1679584171"
}
```
Extracted with zero-guessing policy."""
        result = parse_json_from_llm_response(raw)
        self.assertEqual(result["patient_first_name"], "John")
        self.assertEqual(result["patient_last_name"], "Doe")
        self.assertEqual(result["patient_dob"], "1972-11-03")
        self.assertEqual(result["provider_name"], "Dr. Sarah Connor")
        self.assertEqual(result["provider_npi"], "1679584171")

    def test_parse_json_with_null_fields(self):
        """Verify null fields in JSON are preserved as None."""
        raw = """{
  "patient_first_name": "Jane",
  "patient_last_name": "Smith",
  "patient_dob": null,
  "provider_name": "Dr. Robert Marcus",
  "provider_npi": null
}"""
        result = parse_json_from_llm_response(raw)
        self.assertEqual(result["patient_first_name"], "Jane")
        self.assertEqual(result["patient_last_name"], "Smith")
        self.assertIsNone(result["patient_dob"])
        self.assertEqual(result["provider_name"], "Dr. Robert Marcus")
        self.assertIsNone(result["provider_npi"])

    def test_parse_invalid_json_graceful_fallback(self):
        """Verify invalid or corrupted LLM output returns a safe dict with None."""
        raw = "Sorry, I could not read this blurry scanned document."
        result = parse_json_from_llm_response(raw)
        self.assertIsNone(result["patient_first_name"])
        self.assertIsNone(result["patient_last_name"])
        self.assertIsNone(result["patient_dob"])
        self.assertIsNone(result["provider_name"])
        self.assertIsNone(result["provider_npi"])
        self.assertIn("error", result.get("notes", "").lower())

    # ─── 2. Fallback Heuristic Text Extractor Tests ───────────────────────────

    def test_fallback_extractor_with_complete_text(self):
        """Verify fallback extractor reads plain text streams from PDFs."""
        simulated_pdf_bytes = b"""%PDF-1.4
Patient Name: Jane Doe
DOB: 05/14/1980
Ordering Provider: Dr. Gregory House
Provider NPI: 1083692859
Prescription: CPAP Machine with Humidifier
%%EOF"""
        result = fallback_extract_from_pdf_text(simulated_pdf_bytes)
        self.assertEqual(result["patient_first_name"], "Jane")
        self.assertEqual(result["patient_last_name"], "Doe")
        self.assertEqual(result["patient_dob"], "05/14/1980")
        self.assertEqual(result["provider_name"], "Gregory House")
        self.assertEqual(result["provider_npi"], "1083692859")

    def test_fallback_extractor_zero_guessing_on_missing_fields(self):
        """Verify fallback extractor does not invent values when fields are absent."""
        simulated_pdf_bytes = b"""%PDF-1.4
Patient Name: Arthur Pendelton
Prescription: Wheelchair
%%EOF"""
        result = fallback_extract_from_pdf_text(simulated_pdf_bytes)
        self.assertEqual(result["patient_first_name"], "Arthur")
        self.assertEqual(result["patient_last_name"], "Pendelton")
        # Missing fields MUST be None
        self.assertIsNone(result["patient_dob"])
        self.assertIsNone(result["provider_name"])
        self.assertIsNone(result["provider_npi"])


if __name__ == "__main__":
    unittest.main()
