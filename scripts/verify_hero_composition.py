import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Desktop Dark Mode (1440 x 900)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        # Bypass intro splash
        await page.add_init_script("sessionStorage.setItem('jov-intro-played', 'true');")
        await page.goto("http://localhost:8000")
        await page.wait_for_selector("h1")
        
        # Ensure dark mode
        theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        if theme != "dark":
            await page.click("button[aria-label*='mode']")
            await asyncio.sleep(0.5)
            
        await page.wait_for_selector("video")
        await asyncio.sleep(2.0)
        await page.screenshot(path="docs/qa/refinement/01_hero_desktop_dark_fixed.png")
        print("Captured 01_hero_desktop_dark_fixed.png")
        
        # Capture Nav close up
        nav_el = page.locator("header[aria-label='Main navigation']")
        if await nav_el.count() > 0:
            await nav_el.screenshot(path="docs/qa/refinement/03_nav_search_icon_only.png")
            print("Captured 03_nav_search_icon_only.png")
        
        # 2. Desktop Light Mode (1440 x 900)
        await page.click("button[aria-label*='mode']")
        await asyncio.sleep(2.0)
        await page.screenshot(path="docs/qa/refinement/02_hero_desktop_light_fixed.png")
        print("Captured 02_hero_desktop_light_fixed.png")
        
        # 3. Tablet Dark Mode (768 x 1024)
        tablet_ctx = await browser.new_context(viewport={"width": 768, "height": 1024})
        tablet_page = await tablet_ctx.new_page()
        await tablet_page.add_init_script("sessionStorage.setItem('jov-intro-played', 'true');")
        await tablet_page.goto("http://localhost:8000")
        await tablet_page.wait_for_selector("h1")
        theme = await tablet_page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        if theme != "dark":
            await tablet_page.click("button[aria-label*='mode']")
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.5)
        await tablet_page.screenshot(path="docs/qa/refinement/04_hero_tablet_dark_fixed.png")
        print("Captured 04_hero_tablet_dark_fixed.png")
        
        # 4. Mobile Dark Mode (375 x 812)
        mobile_ctx = await browser.new_context(viewport={"width": 375, "height": 812})
        mobile_page = await mobile_ctx.new_page()
        await mobile_page.add_init_script("sessionStorage.setItem('jov-intro-played', 'true');")
        await mobile_page.goto("http://localhost:8000")
        await mobile_page.wait_for_selector("h1")
        theme = await mobile_page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        if theme != "dark":
            await mobile_page.click("button[aria-label*='mode']")
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.5)
        await mobile_page.screenshot(path="docs/qa/refinement/05_hero_mobile_dark_fixed.png")
        print("Captured 05_hero_mobile_dark_fixed.png")
        
        await browser.close()
        print("All screenshots successfully captured.")

if __name__ == "__main__":
    asyncio.run(run())
