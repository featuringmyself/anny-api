import nodriver as nc

PROMPT_SELECTOR = (
    "#prompt-textarea, #mobile-composer-prompt, textarea[name=prompt]"
)
SEND_SELECTOR = (
    "button[data-testid=send-button], "
    "button[aria-label='Send message'], "
    "button[aria-label='Send prompt']"
)


async def query_chatgpt(question: str):
    browser = await nc.start()
    tab = await browser.get("https://chatgpt.com/")
    await tab
    await tab.sleep(2)

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
    
    await tab.sleep(1)
    await tab.wait_for(SEND_SELECTOR, timeout=10)
    
    await tab.save_screenshot()
     
    html = await tab.get_content()
    with open('chatgpt.html', 'w', encoding='utf-8') as f:
        f.write(html)
     
    browser.stop()


if __name__ == "__main__":
    # nodriver manages its own loop; asyncio.run() leaves the browser process hanging
    nc.loop().run_until_complete(query_chatgpt())
