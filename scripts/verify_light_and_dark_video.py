import asyncio
from playwright.async_api import async_playwright

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        # 1. Dark Mode verification
        await page.goto("http://localhost:8000")
        await page.wait_for_selector("text=Overview")
        await asyncio.sleep(2.0)
        
        dark_info = await page.evaluate("""() => {
            const v = document.querySelector('video');
            const kbd = document.querySelector('header kbd');
            const searchBtn = document.querySelector('header button[aria-label*="search"], header button[aria-label*="Search"]');
            return {
                videoSrc: v ? v.currentSrc : null,
                videoPaused: v ? v.paused : null,
                videoFilter: v ? window.getComputedStyle(v).filter : null,
                videoRect: v ? JSON.stringify(v.getBoundingClientRect()) : null,
                kbdExists: !!kbd,
                searchBtnHTML: searchBtn ? searchBtn.outerHTML : null,
            };
        }""")
        print("DARK MODE INFO:", dark_info)
        await page.screenshot(path="docs/qa/refinement/01_hero_desktop_dark_fixed.png")
        
        # Capture Nav close up
        nav_el = page.locator("header[aria-label='Main navigation']")
        if await nav_el.count() > 0:
            await nav_el.screenshot(path="docs/qa/refinement/03_nav_search_icon_only.png")

        # 2. Switch to Light Mode by clicking the theme toggle button in the navbar
        await page.click("button[aria-label*='mode']")
        await asyncio.sleep(2.0)
        
        light_info = await page.evaluate("""() => {
            const v = document.querySelector('video');
            const theme = document.documentElement.getAttribute('data-theme');
            return {
                themeAttr: theme,
                videoSrc: v ? v.currentSrc : null,
                videoPaused: v ? v.paused : null,
                videoFilter: v ? window.getComputedStyle(v).filter : null,
                videoRect: v ? JSON.stringify(v.getBoundingClientRect()) : null,
            };
        }""")
        print("LIGHT MODE INFO:", light_info)
        await page.screenshot(path="docs/qa/refinement/02_hero_desktop_light_fixed.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
