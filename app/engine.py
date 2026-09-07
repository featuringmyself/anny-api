import asyncio
import os
import traceback
from datetime import datetime
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


async def _save_conversation(
    tab, return_type: ReturnType, brand_name: str | None
) -> ChatGPTQueryResponse:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = f"/tmp/{brand_name or 'chatgpt'}"
    os.makedirs(out_dir, exist_ok=True)

    conversation = await tab.select('ol[aria-label="Conversation"]', timeout=10)

    if return_type == ReturnType.html:
        if conversation:
            html = await conversation.get_html()
        else:
            html = await tab.get_content()
        path = f"{out_dir}/{stamp}_chatgpt.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return ChatGPTQueryResponse(content=html)

    path = f"{out_dir}/{stamp}_chatgpt.png"
    if conversation:
        await conversation.save_screenshot(path, format="png")
    else:
        await tab.save_screenshot(path, format="png")
    return ChatGPTQueryResponse(content=path)


async def query_chatgpt(request: ChatGPTQueryRequest) -> ChatGPTQueryResponse:
    question = request.question
    returnType = request.returnType
    brandName = request.brandName

    # starts a new browser instance
    browser = await nc.start()
    try:
        tab = await browser.get("https://chatgpt.com/")
        await tab
        await tab.sleep(2)

        # send prompt to chatgpt
        prompt = await tab.select(PROMPT_SELECTOR, timeout=20)
        if not prompt:
            await tab.save_screenshot()
            raise RuntimeError("Could not find ChatGPT prompt field")

        await prompt.click()
        await prompt.send_keys(question)
        await tab.sleep(1)

        # click the send button
        send_btn = await tab.select(SEND_SELECTOR, timeout=5)
        if send_btn:
            await send_btn.click()
        else:
            await prompt.send_keys("\n")


        # wait until ChatGPT finishes generating, then scrape the thread
        await tab.sleep(1)
        stop_btn = await tab.select(STOP_SELECTOR, timeout=15)
        if stop_btn:
            loop = asyncio.get_running_loop()
            started = loop.time()
            while await tab.query_selector(STOP_SELECTOR):
                if loop.time() - started > 90:
                    break
                await tab.sleep(0.5)

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
