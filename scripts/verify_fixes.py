import asyncio
from playwright.async_api import async_playwright

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:8000")
        await asyncio.sleep(2.5)
        
        info = await page.evaluate("""() => {
            const v = document.querySelector('video');
            const kbd = document.querySelector('header kbd');
            const searchBtn = document.querySelector('header button[aria-label*="search"], header button[aria-label*="command"]');
            return {
                videoTag: v ? v.outerHTML : 'NO VIDEO',
                videoReadyState: v ? v.readyState : null,
                videoPaused: v ? v.paused : null,
                videoRect: v ? JSON.stringify(v.getBoundingClientRect()) : null,
                kbdText: kbd ? kbd.innerText : null,
                searchBtnLabel: searchBtn ? searchBtn.getAttribute('aria-label') : null,
            };
        }""")
        print("VERIFICATION INFO:", info)
        await page.screenshot(path="docs/qa/refinement/verified_hero_fixed.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
