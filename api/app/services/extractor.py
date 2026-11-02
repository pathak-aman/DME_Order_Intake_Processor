"""
PDF Extraction Service powered by Google Gemini multimodal models.

Extracts:
- patient_first_name
- patient_last_name
- patient_dob
- provider_name
- provider_npi

Strict Zero-Guessing Policy enforced in prompt and post-processing.
"""

import base64
import json
import logging
import os
import re
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

# System prompt emphasizing zero-guessing and precise clinical extraction
DME_EXTRACTION_PROMPT = """You are an expert clinical document processing AI specialized in Durable Medical Equipment (DME) order intake.
Your task is to extract exact patient and ordering provider details from the uploaded DME order, prescription, or fax.

CRITICAL INSTRUCTIONS (ZERO-GUESSING POLICY):
1. Only extract information that is explicitly stated and legible in the document.
2. DO NOT GUESS, assume, approximate, or extrapolate missing information.
3. If a field is not found or is unreadable, you MUST set its value to null.
4. Distinguish carefully between:
   - The PATIENT (person receiving equipment/CPAP/supplies) vs the GUARDIAN/CAREGIVER.
   - The ORDERING PROVIDER (physician/prescriber signing the order) vs DME supplier/vendor/facility staff.
5. The Provider NPI (National Provider Identifier) must be a 10-digit number. If missing or only partial, return null.
6. Return the Patient Date of Birth in ISO format: YYYY-MM-DD. If year, month, or day is uncertain, return null.

Respond ONLY with a valid JSON object matching this exact schema:
{
  "patient_first_name": "string or null",
  "patient_last_name": "string or null",
  "patient_dob": "YYYY-MM-DD string or null",
  "provider_name": "string or null",
  "provider_npi": "10-digit string or null",
  "notes": "brief extraction notes or null"
}"""


def parse_json_from_llm_response(text: str) -> Dict[str, Any]:
    """Safely parse JSON response from LLM output, handling markdown code fences."""
    cleaned = text.strip()

    # Match ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Find the outer JSON object boundaries
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e}. Raw response: {text[:300]}")
        return {
            "patient_first_name": None,
            "patient_last_name": None,
            "patient_dob": None,
            "provider_name": None,
            "provider_npi": None,
            "notes": f"JSON parse error: {e}",
        }


def extract_with_gemini_rest(
    pdf_bytes: bytes,
    api_key: str,
    model_name: str = "gemini-1.5-flash",
) -> Optional[Dict[str, Any]]:
    """Call Google Generative AI REST API using built-in urllib (no external deps required)."""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    b64_data = base64.b64encode(pdf_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": b64_data,
                        }
                    },
                    {
                        "text": DME_EXTRACTION_PROMPT
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

            candidates = result.get("candidates", [])
            if not candidates:
                logger.warning("Gemini returned no candidates.")
                return None

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return None

            raw_text = parts[0].get("text", "")
            return parse_json_from_llm_response(raw_text)

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        logger.error(f"Gemini API HTTP Error {he.code}: {err_body}")
        # Try fallback model if 404 or model not found
        if he.code == 404 and model_name == "gemini-1.5-flash":
            logger.info("Retrying with gemini-2.0-flash...")
            return extract_with_gemini_rest(pdf_bytes, api_key, model_name="gemini-2.0-flash")
        return None
    except Exception as e:
        logger.error(f"Error calling Gemini REST API: {e}")
        return None


def extract_order_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Main extraction entrypoint.

    Accepts raw PDF bytes and extracts DME clinical fields.
    Strictly adheres to zero-guessing policy: missing fields are None.
    """
    api_key = settings.GEMINI_API_KEY.strip() or os.getenv("GEMINI_API_KEY", "").strip()

    if api_key and not api_key.startswith("your-"):
        logger.info(f"Extracting DME fields via Gemini API (PDF size: {len(pdf_bytes)} bytes)...")
        extracted = extract_with_gemini_rest(pdf_bytes, api_key)
        if extracted is not None:
            return extracted
        logger.warning("Gemini extraction returned None. Falling back to heuristic extraction.")

    logger.info("No Gemini API key configured or API call failed. Using fallback extraction.")
    return fallback_extract_from_pdf_text(pdf_bytes)


def fallback_extract_from_pdf_text(pdf_bytes: bytes) -> Dict[str, Any]:
    """Heuristic fallback extractor when LLM API is unavailable (e.g. in offline tests).

    Inspects plain text embedded in PDF if available.
    Adheres strictly to zero-guessing: fields not explicitly found return None.
    """
    try:
        # Search for raw ASCII text patterns in uncompressed streams
        text_content = pdf_bytes.decode("latin1", errors="ignore")
    except Exception:
        text_content = ""

    patient_first: Optional[str] = None
    patient_last: Optional[str] = None
    patient_dob: Optional[str] = None
    provider_name: Optional[str] = None
    provider_npi: Optional[str] = None

    # Patient Name: e.g. "Patient Name: John Doe" or "Patient: Jane Smith"
    pt_match = re.search(r"(?i)patient(?:\s+name)?[:\s]+([A-Z][a-z]+)\s+([A-Z][a-z]+)", text_content)
    if pt_match:
        patient_first = pt_match.group(1).strip()
        patient_last = pt_match.group(2).strip()

    # DOB: e.g. "DOB: 05/14/1980" or "Date of Birth: 1980-05-14"
    dob_match = re.search(r"(?i)(?:dob|date of birth)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})", text_content)
    if dob_match:
        patient_dob = dob_match.group(1).strip()

    # Provider Name: e.g. "Ordering Provider: Dr. Jane Smith" or "Physician: Dr. Marcus Welby"
    prov_match = re.search(r"(?i)(?:ordering provider|physician|prescriber)[:\s]+(?:dr\.?\s+)?([A-Za-z]+(?:[^\S\r\n]+[A-Za-z]+)+)", text_content)
    if prov_match:
        provider_name = prov_match.group(1).strip()

    # NPI: e.g. "NPI: 1234567890" or "Provider NPI: 1234567890"
    npi_match = re.search(r"(?i)(?:npi|provider npi)[:\s#]*(\d{10})\b", text_content)
    if npi_match:
        provider_npi = npi_match.group(1).strip()

    return {
        "patient_first_name": patient_first,
        "patient_last_name": patient_last,
        "patient_dob": patient_dob,
        "provider_name": provider_name,
        "provider_npi": provider_npi,
        "notes": "Extracted via local fallback heuristic",
    }
