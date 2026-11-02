"""
Validation and sanitization service for extracted DME order data.

Strict Zero-Guessing Policy:
- Never assume, impute, or guess missing information.
- Ambiguous or placeholder values are strictly converted to None.
- All extracted fields must meet clinical validity constraints before saving.
"""

from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional, Tuple

# Placeholders frequently output by OCR, faxes, or ambiguous form fields
PLACEHOLDER_VALUES = {
    "",
    "-",
    "--",
    "---",
    "/",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not provided",
    "not available",
    "not found",
    "unspecified",
    "pending",
    "missing",
    "undefined",
    "blank",
    "nil",
}

# Common name prefixes/titles to strip from first names
PREFIXES = ["mr.", "mr", "mrs.", "mrs", "ms.", "ms", "miss", "patient:", "name:"]


def is_placeholder(val: Optional[str]) -> bool:
    """Return True if val represents a missing or placeholder value."""
    if val is None:
        return True
    cleaned = str(val).strip().lower()
    return cleaned in PLACEHOLDER_VALUES


def sanitize_name(name: Optional[str], is_first_name: bool = False) -> Optional[str]:
    """Clean and validate a personal name string.

    Returns None if missing, invalid, or placeholder.
    """
    if not name or is_placeholder(name):
        return None

    cleaned = str(name).strip()

    # Remove quotes, brackets, or leading/trailing punctuation
    cleaned = re.sub(r'^[^\w]+|[^\w]+$', "", cleaned)

    if is_first_name:
        # Strip common prefixes like 'Mr.', 'Ms.', 'Patient:'
        parts = cleaned.split()
        if parts and parts[0].lower() in PREFIXES:
            cleaned = " ".join(parts[1:])

    # Clean internal whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned or is_placeholder(cleaned):
        return None

    # Length sanity check: name should be 1 to 80 chars
    if len(cleaned) < 1 or len(cleaned) > 80:
        return None

    # Must contain at least one alphabetic character
    if not any(c.isalpha() for c in cleaned):
        return None

    return cleaned


def sanitize_provider_name(name: Optional[str]) -> Optional[str]:
    """Clean and validate an ordering provider's name."""
    if not name or is_placeholder(name):
        return None

    cleaned = str(name).strip()
    cleaned = re.sub(r'^[^\w]+|[^\w]+$', "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned or is_placeholder(cleaned):
        return None

    if len(cleaned) < 2 or len(cleaned) > 120:
        return None

    if not any(c.isalpha() for c in cleaned):
        return None

    return cleaned


def parse_and_validate_dob(dob_raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """Parse a date of birth into ISO YYYY-MM-DD.

    Returns:
        (iso_date_string, error_message)
        If valid: ("YYYY-MM-DD", None)
        If invalid/missing: (None, "error description")
    """
    if dob_raw is None or is_placeholder(str(dob_raw)):
        return None, "Date of birth is missing."

    dob_str = str(dob_raw).strip()

    # Remove extra labels like 'DOB:', 'DOB', 'Birth Date:'
    dob_str = re.sub(r"(?i)^(dob|date of birth|birth date)[:\s]*", "", dob_str).strip()

    # Supported candidate date patterns
    candidate_formats = [
        "%Y-%m-%d",      # 1980-05-14
        "%m/%d/%Y",      # 05/14/1980
        "%m-%d-%Y",      # 05-14-1980
        "%d/%m/%Y",      # 14/05/1980 (international)
        "%d-%m-%Y",      # 14-05-1980
        "%Y/%m/%d",      # 1980/05/14
        "%B %d, %Y",     # May 14, 1980
        "%b %d, %Y",     # May 14, 1980
        "%d %B %Y",      # 14 May 1980
        "%d %b %Y",      # 14 May 1980
        "%m/%d/%y",      # 05/14/80 (two-digit year)
        "%m-%d-%y",      # 05-14-80
    ]

    parsed_date: Optional[date] = None

    for fmt in candidate_formats:
        try:
            dt = datetime.strptime(dob_str, fmt)
            parsed_date = dt.date()
            break
        except ValueError:
            continue

    if parsed_date is None:
        return None, f"Could not parse date of birth '{dob_str}'."

    # Clinical sanity checks:
    today = date.today()
    if parsed_date > today:
        return None, f"Date of birth cannot be in the future ({parsed_date.isoformat()})."

    # Year must be reasonable (e.g. >= 1900)
    if parsed_date.year < 1900:
        return None, f"Year of birth {parsed_date.year} is outside valid clinical range (>= 1900)."

    return parsed_date.isoformat(), None


def validate_npi_luhn(npi_str: str) -> bool:
    """Validate 10-digit NPI using the CMS Luhn-10 algorithm.

    CMS prepends '80840' to the 9-digit base of the 10-digit NPI, then verifies
    the 10th check digit using the standard Luhn algorithm.
    """
    if not (isinstance(npi_str, str) and len(npi_str) == 10 and npi_str.isdigit()):
        return False

    # Prefix 80840 precomputed sum:
    # 8, 0, 8, 4, 0 with Luhn doubling from right: 8 + 0 + 8 + 8 + 0 = 24
    total = 24
    for i in range(9):
        d = int(npi_str[8 - i])
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d

    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(npi_str[9])


def sanitize_npi(npi_raw: Any, strict_luhn: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """Clean and validate an Ordering Provider NPI.

    Must be strictly 10 numeric digits.
    Returns:
        (cleaned_npi, error_message)
    """
    if npi_raw is None or is_placeholder(str(npi_raw)):
        return None, "Provider NPI is missing."

    # Extract all digits
    raw_str = str(npi_raw).strip()
    digits = re.sub(r"\D", "", raw_str)

    if not digits:
        return None, "Provider NPI contains no digits."

    if len(digits) != 10:
        return None, f"Provider NPI must be exactly 10 digits (found {len(digits)} in '{raw_str}')."

    if digits == "0000000000":
        return None, "Provider NPI cannot be all zeroes."

    # Verify Luhn checksum if strict mode enabled
    if strict_luhn and not validate_npi_luhn(digits):
        return None, f"Provider NPI '{digits}' failed the Luhn checksum check."

    return digits, None


def validate_and_sanitize_order(extracted_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Strictly validates all extracted fields for a DME order.

    Zero-Guessing Policy:
    - Missing or malformed fields are strictly set to None.
    - If all 5 required clinical fields are present & valid, status is 'verified'.
    - If any of the 5 fields is missing or invalid, status is 'needs_review'.

    Required 5 clinical fields:
    1. patient_first_name
    2. patient_last_name
    3. patient_dob
    4. provider_name
    5. provider_npi

    Returns:
        (sanitized_order_dict, list_of_validation_issues)
    """
    issues: List[str] = []

    # 1. Patient First Name
    raw_first = extracted_data.get("patient_first_name")
    clean_first = sanitize_name(raw_first, is_first_name=True)
    if not clean_first:
        issues.append("Patient first name is missing or invalid.")

    # 2. Patient Last Name
    raw_last = extracted_data.get("patient_last_name")
    clean_last = sanitize_name(raw_last, is_first_name=False)
    if not clean_last:
        issues.append("Patient last name is missing or invalid.")

    # 3. Patient Date of Birth
    raw_dob = extracted_data.get("patient_dob")
    clean_dob, dob_err = parse_and_validate_dob(raw_dob)
    if dob_err:
        issues.append(dob_err)

    # 4. Provider Name
    raw_provider = extracted_data.get("provider_name")
    clean_provider = sanitize_provider_name(raw_provider)
    if not clean_provider:
        issues.append("Ordering provider name is missing or invalid.")

    # 5. Provider NPI
    raw_npi = extracted_data.get("provider_npi")
    clean_npi, npi_err = sanitize_npi(raw_npi)
    if npi_err:
        issues.append(npi_err)

    # Determine status: verified if ALL 5 are clean, otherwise needs_review
    is_fully_verified = bool(
        clean_first and clean_last and clean_dob and clean_provider and clean_npi
    )
    status = "verified" if is_fully_verified else "needs_review"

    sanitized = {
        "patient_first_name": clean_first,
        "patient_last_name": clean_last,
        "patient_dob": clean_dob,
        "provider_name": clean_provider,
        "provider_npi": clean_npi,
        "status": status,
    }

    return sanitized, issues
