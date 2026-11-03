"""
PDF Extraction Service using Gemini, OpenAI, and a limited text fallback.

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
        logger.error("Failed to parse LLM JSON (%s)", type(e).__name__)
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
    model_name: str = "gemini-3.8-flash",
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
            extracted = parse_json_from_llm_response(raw_text)
            if str(extracted.get("notes", "")).startswith("JSON parse error:"):
                return None
            return extracted

    except urllib.error.HTTPError as he:
        logger.error("Gemini API HTTP error %s", he.code)
        # Try fallback model if 404 or model not found
        if he.code == 404 and model_name == "gemini-3.8-flash":
            logger.info("Retrying with gemini-3.5-flash-lite...")
            return extract_with_gemini_rest(pdf_bytes, api_key, model_name="gemini-3.5-flash-lite")
        return None
    except Exception as e:
        logger.error(f"Error calling Gemini REST API: {e}")
        return None


def extract_with_openai_rest(
    pdf_bytes: bytes,
    api_key: str,
    model_name: str = "gpt-4.1",
) -> Optional[Dict[str, Any]]:
    """Read a PDF with the vision-capable OpenAI Responses API."""
    payload = {
        "model": model_name,
        "temperature": 0,
        "input": [{
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "filename": "dme_order.pdf",
                    "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
                },
                {"type": "input_text", "text": DME_EXTRACTION_PROMPT},
            ],
        }],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("status") != "completed":
            logger.warning("OpenAI response was not completed (status: %s)", result.get("status"))
            return None

        # REST responses contain output messages with output_text content blocks.
        for item in result.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text" and part.get("text"):
                    extracted = parse_json_from_llm_response(part["text"])
                    if isinstance(extracted, dict) and not str(extracted.get("notes", "")).startswith("JSON parse error:"):
                        return extracted
        logger.warning("OpenAI returned no usable JSON output.")
        return None
    except urllib.error.HTTPError as error:
        # Do not log the API key, raw document, or provider response (may contain PHI).
        logger.error("OpenAI API HTTP error %s", error.code)
        return None
    except Exception as error:
        logger.error("OpenAI extraction failed (%s)", type(error).__name__)
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
        logger.warning("Gemini extraction failed. Trying OpenAI if configured.")

    openai_key = settings.OPENAI_API_KEY.strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key and not openai_key.startswith("your-"):
        logger.info("Extracting DME fields via OpenAI PDF fallback...")
        extracted = extract_with_openai_rest(pdf_bytes, openai_key)
        if extracted is not None:
            return extracted
        logger.warning("OpenAI extraction failed. Using local text fallback.")

    logger.info("No working AI provider configured. Using local text fallback.")
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
