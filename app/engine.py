import asyncio
import os
import traceback
from datetime import datetime
from typing import TypedDict

from app.schemas.chatgpt import ChatGPTQueryRequest, ChatGPTQueryResponse, ReturnType
import nodriver as nc

PROMPT_SELECTOR = (
    "#prompt-textarea, #mobile-composer-prompt, textarea[name=prompt]"
)
SEND_SELECTOR = (
    "button[data-testid=send-button], "
    "button[aria-label='Send message'], "
    "button[aria-label='Send prompt']"
)
STOP_SELECTOR = (
    "button[data-testid='stop-button'], "
    "button[aria-label='Stop streaming'], "
    "button[aria-label='Stop generating']"
)
CONVERSATION_SELECTOR = (
    "#thread, "
    "div:has(> [data-testid^='conversation-turn-']), "
    "ol[aria-label='Conversation']"
)


class AuditCapture(TypedDict):
    html: str
    screenshot_path: str


async def _wait_for_generation(tab) -> None:
    await tab.sleep(1)
    stop_btn = await tab.select(STOP_SELECTOR, timeout=15)
    if stop_btn:
        loop = asyncio.get_running_loop()
        started = loop.time()
        while await tab.query_selector(STOP_SELECTOR):
            if loop.time() - started > 90:
                break
            await tab.sleep(0.5)


async def _send_prompt(tab, question: str) -> None:
    prompt = await tab.select(PROMPT_SELECTOR, timeout=20)
    if not prompt:
        await tab.save_screenshot()
        raise RuntimeError("Could not find ChatGPT prompt field")

    await prompt.click()
    await prompt.send_keys(question)
    await tab.sleep(1)

    send_btn = await tab.select(SEND_SELECTOR, timeout=5)
    if send_btn:
        await send_btn.click()
    else:
        await prompt.send_keys("\n")

    await _wait_for_generation(tab)


async def _save_conversation(
    tab, return_type: ReturnType, brand_name: str | None
) -> ChatGPTQueryResponse:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = f"tmp/{brand_name or 'chatgpt'}"
    os.makedirs(out_dir, exist_ok=True)

    conversation = await tab.select(CONVERSATION_SELECTOR, timeout=10)

    # Save full-page HTML whenever the conversation element is not found
    if not conversation:
        html = await tab.get_content()
        html_path = f"{out_dir}/{stamp}_chatgpt.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    if return_type == ReturnType.html:
        if conversation:
            html = await conversation.get_html()
            html_path = f"{out_dir}/{stamp}_chatgpt.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
        return ChatGPTQueryResponse(content=html)

    path = f"{out_dir}/{stamp}_chatgpt.png"
    if conversation:
        await conversation.save_screenshot(path, format="png")
    else:
        await tab.save_screenshot(path, format="png")
    return ChatGPTQueryResponse(content=path)


async def _ensure_empty_thread(tab) -> None:
    """Reload so the next buyer prompt lands in an empty ChatGPT thread."""
    await tab.reload()
    await tab
    await tab.sleep(2)


async def capture_audit_answer(brand_name: str, prompt: str) -> AuditCapture:
    """
    Run one buyer prompt in an empty ChatGPT thread and save HTML + PNG
    from that same answer only (evidence pairing, not multi-prompt memory).
    """
    browser = await nc.start()
    try:
        tab = await browser.get("https://chatgpt.com/")
        await tab
        await tab.sleep(2)
        await _ensure_empty_thread(tab)
        await _send_prompt(tab, prompt)

        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_dir = f"tmp/{brand_name or 'chatgpt'}"
        os.makedirs(out_dir, exist_ok=True)

        conversation = await tab.select(CONVERSATION_SELECTOR, timeout=10)
        if conversation:
            html = await conversation.get_html()
        else:
            html = await tab.get_content()

        html_path = f"{out_dir}/{stamp}_chatgpt.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        screenshot_path = f"{out_dir}/{stamp}_chatgpt.png"
        if conversation:
            await conversation.save_screenshot(screenshot_path, format="png")
        else:
            await tab.save_screenshot(screenshot_path, format="png")

        return {"html": html, "screenshot_path": screenshot_path}
    except RuntimeError:
        raise
    except Exception:
        traceback.print_exc()
        raise RuntimeError("Could not capture audit answer") from None
    finally:
        browser.stop()


async def query_chatgpt(request: ChatGPTQueryRequest) -> ChatGPTQueryResponse:
    question = request.question
    returnType = request.returnType
    brandName = request.brandName or None

    # starts a new browser instance
    browser = await nc.start()
    try:
        tab = await browser.get("https://chatgpt.com/")
        await tab
        await tab.sleep(2)

        await _send_prompt(tab, question)

        try:
            return await _save_conversation(tab, returnType, brandName)
        except RuntimeError:
            raise
        except Exception:
            traceback.print_exc()
            raise RuntimeError("Could not find conversation") from None

    finally:
        browser.stop()


if __name__ == "__main__":
    # nodriver manages its own loop; asyncio.run() leaves the browser process hanging
    nc.loop().run_until_complete(
        query_chatgpt(
            ChatGPTQueryRequest(question="Hello", returnType=ReturnType.html)
        )
    )
