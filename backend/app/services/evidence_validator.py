
from dataclasses import dataclass
import re


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]


UNSUPPORTED_PATTERNS = {
    "government ID verification": [
        "government id",
        "government identification",
        "upload an id",
        "identity document",
    ],
    "transaction verification": [
        "last four transaction digits",
        "last 4 transaction digits",
        "transaction verification",
    ],
    "security questions": [
        "security question",
        "answer security questions",
    ],
    "undocumented manual unlock": [
        "manually unlock",
        "manual account unlock",
        "unlock the account immediately",
    ],
    "unsupported browser troubleshooting": [
        "clear browser cache",
        "clear your cache",
        "incognito mode",
    ],
    "unsupported identity verification for account unlock": [
        "proof of identity",
        "identity proof",
        "verify your identity",
        "identity verification to unlock",
        "contact support with proof",
    ],
    "unsupported manual account unlock": [
        "account can be reviewed and unlocked",
        "reviewed and unlocked",
        "unlock your account",
        "unlock the account",
        "account unlock",
        "manually unlock your account",
        "support can unlock",
    ],
    "unsupported phone verification delivery": [
        "verification code will be sent",
        "verification code is sent",
        "code will be sent to the new number",
        "send a verification code",
        "receive a verification code",
        "otp will be sent",
        "otp is sent",
    ],
    "unsupported previous phone number status": [
        "previous number will remain active",
        "old number will remain active",
        "previous number remains active",
        "old number remains active",
        "previous number will remain in use",
        "old number will remain in use",
    ],
}


def _get_value(obj, key, default=""):
    """Read a field from either a dictionary or a Pydantic object."""
    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _normalize_text(value):
    """Normalize text for consistent evidence comparison."""
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def validate_resolution(resolution, evidence):
    errors = []

    if not evidence:
        errors.append("No supporting evidence available.")

    resolution_parts = [
        _get_value(resolution, "root_cause"),
        _get_value(resolution, "summary"),
        _get_value(resolution, "recommended_next_action"),
        " ".join(
            str(step)
            for step in (
                _get_value(resolution, "resolution_steps", []) or []
            )
        ),
        _get_value(resolution, "customer_response"),
    ]

    resolution_text = _normalize_text(
        " ".join(
            str(part)
            for part in resolution_parts
            if part
        )
    )

    evidence_text = _normalize_text(
        " ".join(
            item.get("text", "")
            for item in evidence
        )
    )

    # Reject explicitly unsupported operational instructions.
    for category, patterns in UNSUPPORTED_PATTERNS.items():
        for pattern in patterns:
            normalized_pattern = _normalize_text(pattern)

            if normalized_pattern in resolution_text:
                if normalized_pattern not in evidence_text:
                    errors.append(
                        f"Unsupported instruction detected: {category}"
                    )
                    break

    # Customer-facing response must use support-agent perspective.
    customer_response = _normalize_text(
        _get_value(resolution, "customer_response")
    )

    customer_perspective_patterns = [
        "we will wait",
        "i will wait",
        "we'll wait",
        "i'll wait",
        "we will try again",
        "i will try again",
    ]

    if any(
        pattern in customer_response
        for pattern in customer_perspective_patterns
    ):
        errors.append(
            "Customer response uses customer perspective "
            "instead of support-agent perspective."
        )

    # Documented lockout policy must be supported by evidence.
    if "15 minutes" in resolution_text:
        if "15 minutes" not in evidence_text:
            errors.append(
                "15-minute lockout claim is not supported by evidence."
            )

    if "five consecutive failed login attempts" in resolution_text:
        if "five consecutive failed login attempts" not in evidence_text:
            errors.append(
                "Five-attempt lockout claim is not supported by evidence."
            )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
    )
