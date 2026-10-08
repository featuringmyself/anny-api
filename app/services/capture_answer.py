from app.engine import capture_audit_answer
from app.schemas.capture import CaptureReturnType
from app.services.html_extract import (
    CaptureQualityError,
    extract_assistant_text,
    validate_capture_text,
)


async def try_capture(
    brand_name: str,
    query: str,
    return_type: CaptureReturnType = CaptureReturnType.all,
) -> dict:
    """
    Capture once; on failure retry once with a fresh empty thread.
    return_type controls which artifact paths are saved/returned:
      - html → answer_text + html_path
      - png  → screenshot_path (HTML still loaded for quality check)
      - all  → answer_text + html_path + screenshot_path
    """
    save_html = return_type in (CaptureReturnType.html, CaptureReturnType.all)
    save_png = return_type in (CaptureReturnType.png, CaptureReturnType.all)

    last_exc: Exception | None = None
    for _ in range(2):
        try:
            capture = await capture_audit_answer(
                brand_name,
                query,
                save_html=save_html,
                save_png=save_png,
            )
            answer_text = validate_capture_text(
                extract_assistant_text(capture["html"])
            )
            return {
                "answer_text": answer_text if save_html else "",
                "html_path": capture["html_path"] if save_html else "",
                "screenshot_path": capture["screenshot_path"] if save_png else "",
                "capture_error": None,
            }
        except (CaptureQualityError, RuntimeError) as exc:
            last_exc = exc
    return {
        "answer_text": "",
        "html_path": "",
        "screenshot_path": "",
        "capture_error": str(last_exc) if last_exc else "Could not capture audit answer",
    }
