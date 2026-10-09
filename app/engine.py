import asyncio
import base64
import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from app.schemas.chatgpt import ChatGPTQueryRequest, ChatGPTQueryResponse, ReturnType
from app.services.png_trim import trim_trailing_black
import nodriver as nc
from nodriver import cdp

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
# Tried in order — never combine with #thread in one querySelector list:
# ancestors win document-order and #thread is a full-height shell.
_CONVERSATION_SELECTORS = (
    "ol[aria-label='Conversation']",
    "div:has(> [data-testid^='conversation-turn-'])",
    "#thread",
)
_SCREENSHOT_PAD_PX = 8

# Prepare DOM + measure clip in *document* coordinates (same formula Chrome
# DevTools / chromedp use for "Capture node screenshot"). Viewport quads from
# DOM.getContentQuads are wrong when captureBeyondViewport=true.
_PREPARE_AND_MEASURE_JS = r"""
JSON.stringify((() => {
  const contentSel = [
    "[data-message-attribution]",
    "[data-assistant-markdown]",
    "[data-user-message-bubble]",
    "[data-user-message-copy]",
    "[data-assistant-message-actions]",
    "[aria-label='Response actions']",
    "[data-message-author-role]",
  ].join(", ");
  const turnSel =
    "ol[aria-label='Conversation'] > li, [data-testid^='conversation-turn-']";
  const composerSeeds = [
    "#prompt-textarea",
    "#mobile-composer-prompt",
    "textarea[name=prompt]",
    "button[data-testid=send-button]",
    "button[aria-label='Send message']",
    "button[aria-label='Send prompt']",
    "button[aria-label='Dictate button']",
  ].join(", ");

  const marked = [];
  const mark = (el, cssText) => {
    if (!el || el.dataset.annyCapture === "1") return;
    el.dataset.annyCapture = "1";
    el.dataset.annyStyle = el.getAttribute("style") || "";
    el.style.cssText += ";" + cssText;
    marked.push(el);
  };

  // 1) Hide composer / sticky footers so they cannot paint into the clip.
  for (const seed of document.querySelectorAll(composerSeeds)) {
    let target = seed.closest("form") || seed.parentElement;
    let cur = seed;
    for (let i = 0; i < 8 && cur; i++) {
      const st = getComputedStyle(cur);
      if (st.position === "fixed" || st.position === "sticky") {
        target = cur;
        break;
      }
      cur = cur.parentElement;
    }
    mark(target, "visibility:hidden!important;pointer-events:none!important");
  }

  // 2) Collapse stretchy thread shells (min-height:100% / flex-grow filler).
  for (const shell of document.querySelectorAll(
    "#thread, ol[aria-label='Conversation'], ol[aria-label='Conversation'] > li"
  )) {
    mark(
      shell,
      "min-height:0!important;height:auto!important;flex-grow:0!important;flex:0 0 auto!important"
    );
  }

  const turns = Array.from(document.querySelectorAll(turnSel));
  if (turns[0]) turns[0].scrollIntoView({ block: "start", inline: "nearest" });

  let nodes = Array.from(document.querySelectorAll(contentSel));
  if (!nodes.length) nodes = turns;
  if (!nodes.length) {
    return { marked: marked.length, clip: null };
  }

  // Document coordinates: elemRect - documentElementRect (chromedp/DevTools).
  const doc = document.documentElement.getBoundingClientRect();
  let minL = Infinity, minT = Infinity, maxR = -Infinity, maxB = -Infinity;
  for (const el of nodes) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    minL = Math.min(minL, r.left - doc.left);
    minT = Math.min(minT, r.top - doc.top);
    maxR = Math.max(maxR, r.right - doc.left);
    maxB = Math.max(maxB, r.bottom - doc.top);
  }
  if (!Number.isFinite(minL)) {
    return { marked: marked.length, clip: null };
  }
  const pad = 8;
  return {
    marked: marked.length,
    clip: {
      x: minL - pad,
      y: minT - pad,
      width: Math.max(1, maxR - minL + 2 * pad),
      height: Math.max(1, maxB - minT + 2 * pad),
      scale: 1,
    },
  };
})())
"""

_RESTORE_DOM_JS = r"""
(() => {
  for (const el of document.querySelectorAll("[data-anny-capture='1']")) {
    const prev = el.dataset.annyStyle || "";
    if (prev) el.setAttribute("style", prev);
    else el.removeAttribute("style");
    delete el.dataset.annyCapture;
    delete el.dataset.annyStyle;
  }
})()
"""


class AuditCapture(TypedDict):
    html: str
    html_path: str
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


async def _find_conversation(tab, timeout: float = 10):
    """Return the tightest conversation node (list/turns before #thread)."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    while True:
        for selector in _CONVERSATION_SELECTORS:
            el = await tab.query_selector(selector)
            if el:
                return el
        if loop.time() - started > timeout:
            return None
        await tab.sleep(0.5)


async def _eval_json(tab, expression: str) -> Any:
    """Evaluate JS that returns JSON.stringify(...); parse to Python."""
    raw = await tab.evaluate(expression, return_by_value=True)
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    # nodriver deep-serialization fallback
    if raw is not None and hasattr(raw, "value"):
        val = raw.value
        if isinstance(val, str):
            return json.loads(val)
        return val
    return None


async def _screenshot_conversation(tab, path: str, fallback=None) -> None:
    """
    Capture only the conversation content.

    Evidence from failed clips:
    - HTML is already the conversation <ol> (no composer in DOM snapshot)
    - PNG still showed composer + ~300px black because #thread/ol/li shells
      are viewport-tall and CDP clips from getContentQuads use viewport
      coordinates while captureBeyondViewport expects document coordinates.

    Production approach (chromedp / Chrome "Capture node screenshot"):
    1. Hide composer; collapse stretchy min-heights
    2. Measure content bbox in document coordinates
    3. Page.captureScreenshot(clip, captureBeyondViewport, fromSurface)
    4. Trim trailing pure-black rows as a safety net
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prepared = False
    try:
        measured = await _eval_json(tab, _PREPARE_AND_MEASURE_JS)
        prepared = bool(measured)
        # Let collapse / hide / scrollIntoView settle, then re-measure once.
        await tab.sleep(0.35)
        measured = await _eval_json(tab, _PREPARE_AND_MEASURE_JS) or measured
        prepared = prepared or bool(measured)
        clip_data = (measured or {}).get("clip") if isinstance(measured, dict) else None

        png_bytes: bytes | None = None
        if isinstance(clip_data, dict):
            clip = cdp.page.Viewport(
                x=float(clip_data["x"]),
                y=float(clip_data["y"]),
                width=float(clip_data["width"]),
                height=float(clip_data["height"]),
                scale=float(clip_data.get("scale") or 1),
            )
            data = await tab.send(
                cdp.page.capture_screenshot(
                    "png",
                    clip=clip,
                    from_surface=True,
                    capture_beyond_viewport=True,
                )
            )
            if data:
                png_bytes = base64.b64decode(data)

        if png_bytes is None:
            if fallback is not None:
                await fallback.save_screenshot(path, format="png")
            else:
                await tab.save_screenshot(path, format="png")
            png_bytes = Path(path).read_bytes()

        try:
            png_bytes = trim_trailing_black(png_bytes, pad_px=_SCREENSHOT_PAD_PX)
        except Exception:
            pass
        out.write_bytes(png_bytes)
    finally:
        if prepared:
            try:
                await tab.evaluate(_RESTORE_DOM_JS, return_by_value=True)
            except Exception:
                pass


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

    conversation = await _find_conversation(tab)

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
    await _screenshot_conversation(tab, path, fallback=conversation)
    return ChatGPTQueryResponse(content=path)


async def _ensure_empty_thread(tab) -> None:
    """Reload so the next buyer prompt lands in an empty ChatGPT thread."""
    await tab.reload()
    await tab
    await tab.sleep(2)


async def capture_audit_answer(
    brand_name: str,
    prompt: str,
    *,
    save_html: bool = True,
    save_png: bool = True,
) -> AuditCapture:
    """
    Run one buyer prompt in an empty ChatGPT thread and optionally save
    HTML and/or PNG from that same answer only (evidence pairing, not
    multi-prompt memory). HTML is always captured in memory for text extract.
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

        conversation = await _find_conversation(tab)
        if conversation:
            html = await conversation.get_html()
        else:
            html = await tab.get_content()

        html_path = ""
        if save_html:
            html_path = f"{out_dir}/{stamp}_chatgpt.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

        screenshot_path = ""
        if save_png:
            screenshot_path = f"{out_dir}/{stamp}_chatgpt.png"
            await _screenshot_conversation(
                tab, screenshot_path, fallback=conversation
            )

        return {
            "html": html,
            "html_path": html_path,
            "screenshot_path": screenshot_path,
        }
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
