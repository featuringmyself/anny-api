from app.engine import capture_audit_answer
from app.services.html_extract import (
    CaptureQualityError,
    extract_assistant_text,
    validate_capture_text,
)


async def try_capture(brand_name: str, query: str) -> dict:
    """
    Capture once; on failure retry once with a fresh empty thread.
    Returns answer_text, screenshot_path, and optional capture_error.
    """
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            capture = await capture_audit_answer(brand_name, query)
            answer_text = validate_capture_text(
                extract_assistant_text(capture["html"])
            )
            return {
                "answer_text": answer_text,
                "screenshot_path": capture["screenshot_path"],
                "capture_error": None,
            }
        except (CaptureQualityError, RuntimeError) as exc:
            last_exc = exc
    return {
        "answer_text": "",
        "screenshot_path": "",
        "capture_error": str(last_exc) if last_exc else "Could not capture audit answer",
    }
