#!/usr/bin/env python3
"""email_validate.py — Validate AIBP email address

Usage:
    python email_validate.py --address "aibot-alice@gmail.com"

Validation rules:
    1. RFC 5322 format validity (email-validator library)
    2. DNS MX record exists
    3. Whether it follows the AIBP aibot- prefix convention
"""

from __future__ import annotations

import argparse
import json
import sys

from _config import get_logger
from _schemas import ValidateResult, ErrorResult, ErrorCode

log = get_logger("email_validate")


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def validate_address(address: str) -> dict:
    """Validate email address and return structured result"""
    from email_validator import validate_email, EmailNotValidError

    try:
        result = validate_email(address, check_deliverability=True)
        normalized = result.normalized

        # Check AIBP prefix convention
        local_part = normalized.split("@")[0]
        is_aibp = local_part.startswith("aibot-")

        # MX records
        mx_records = []
        if hasattr(result, "mx") and result.mx:
            mx_records = [str(mx[1]) for mx in result.mx]

        output = ValidateResult(
            address=normalized,
            valid=True,
            is_aibp=is_aibp,
            mx_records=mx_records,
            suggestion=None if is_aibp else "AIBP convention: bot address should start with aibot- (e.g. aibot-mybot@gmail.com)",
        )
        return json.loads(output.model_dump_json())

    except EmailNotValidError as e:
        output = ValidateResult(
            address=address,
            valid=False,
            is_aibp=False,
            suggestion=str(e),
        )
        return json.loads(output.model_dump_json())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="AIBP email address validation")
    parser.add_argument("--address", required=True, type=str, help="Email address to validate")
    args = parser.parse_args()

    try:
        result = validate_address(args.address)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        error = ErrorResult(
            error_code=ErrorCode.RUNTIME_ERROR,
            error=str(e),
        )
        print(error.model_dump_json())
        log.error("validate_error", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
