import asyncio
import os
import shutil
import subprocess
import sys
import time
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\Prosun\.gemini\antigravity\brain\2de21887-cb54-423b-bb90-81445bbeb444"
QA_DIR = "docs/qa/refinement"

async def run():
    os.makedirs(QA_DIR, exist_ok=True)

    # 1. Start mock portal
    mock_p = subprocess.Popen([sys.executable, "-m", "mock_portal.server"], env={**os.environ, "PORT": "8765"})
    # 2. Start backend API if not already running
    api_p = subprocess.Popen([sys.executable, "-m", "uvicorn", "jovsi.api.main:app", "--port", "8000"], env={**os.environ, "PYTHONPATH": "src"})
    # 3. Start vite dev server
    vite_p = subprocess.Popen(["npm", "run", "dev"], cwd="web", shell=True)

    time.sleep(3)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Desktop Dark Viewport
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        # Pre-seed dark theme & skip intro overlay for instant snapshot
        await page.add_init_script("""() => {
            sessionStorage.setItem('jov-intro-played', 'true');
            localStorage.setItem('jov-theme', 'dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.classList.add('dark');
            document.documentElement.style.colorScheme = 'dark';
        }""")
        await page.goto("http://localhost:5173")
        await page.wait_for_selector("text=Scattered → Clarity")
        # Wait for video and animations to settle
        await asyncio.sleep(2.0)
        
        # Hero Dark
        p1 = f"{QA_DIR}/01_hero_desktop_dark.png"
        await page.screenshot(path=p1)
        shutil.copy(p1, os.path.join(ARTIFACT_DIR, "01_hero_desktop_dark.png"))
        print("Captured 01_hero_desktop_dark.png")

        # Nav Close Up
        p_nav = f"{QA_DIR}/03_nav_close_up.png"
        nav_el = page.locator("header[aria-label='Main navigation']")
        if await nav_el.count() > 0:
            await nav_el.screenshot(path=p_nav)
            shutil.copy(p_nav, os.path.join(ARTIFACT_DIR, "03_nav_close_up.png"))
            print("Captured 03_nav_close_up.png")

        # Settings Dark (Safeguards tab)
        await page.click("button:has-text('Settings')")
        await page.wait_for_selector("text=Settings & Safeguards")
        await page.click("button:has-text('Application Safeguards')")
        await asyncio.sleep(0.6)
        p_set_dark = f"{QA_DIR}/06_settings_safeguards_dark.png"
        await page.screenshot(path=p_set_dark)
        shutil.copy(p_set_dark, os.path.join(ARTIFACT_DIR, "06_settings_safeguards_dark.png"))
        print("Captured 06_settings_safeguards_dark.png")

        # 2. Switch to Light Mode
        await page.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'light');
            document.documentElement.classList.remove('dark');
            document.documentElement.style.colorScheme = 'light';
            localStorage.setItem('jov-theme', 'light');
        }""")
        await asyncio.sleep(0.8)
        
        # Settings Light
        p_set_light = f"{QA_DIR}/07_settings_safeguards_light.png"
        await page.screenshot(path=p_set_light)
        shutil.copy(p_set_light, os.path.join(ARTIFACT_DIR, "07_settings_safeguards_light.png"))
        print("Captured 07_settings_safeguards_light.png")

        # Hero Light
        await page.click("button:has-text('Overview')")
        await asyncio.sleep(1.0)
        p2 = f"{QA_DIR}/02_hero_desktop_light.png"
        await page.screenshot(path=p2)
        shutil.copy(p2, os.path.join(ARTIFACT_DIR, "02_hero_desktop_light.png"))
        print("Captured 02_hero_desktop_light.png")

        await context.close()

        # 3. Mobile Viewport (Dark)
        context_mobile = await browser.new_context(viewport={"width": 390, "height": 844})
        page_mobile = await context_mobile.new_page()
        await page_mobile.add_init_script("""() => {
            sessionStorage.setItem('jov-intro-played', 'true');
            localStorage.setItem('jov-theme', 'dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.classList.add('dark');
            document.documentElement.style.colorScheme = 'dark';
        }""")
        await page_mobile.goto("http://localhost:5173")
        await page_mobile.wait_for_selector("text=Scattered → Clarity")
        await asyncio.sleep(1.5)
        p_mob = f"{QA_DIR}/05_hero_mobile_dark.png"
        await page_mobile.screenshot(path=p_mob)
        shutil.copy(p_mob, os.path.join(ARTIFACT_DIR, "05_hero_mobile_dark.png"))
        print("Captured 05_hero_mobile_dark.png")
        await context_mobile.close()

        # 4. Tablet Viewport (Dark)
        context_tab = await browser.new_context(viewport={"width": 1024, "height": 768})
        page_tab = await context_tab.new_page()
        await page_tab.add_init_script("""() => {
            sessionStorage.setItem('jov-intro-played', 'true');
            localStorage.setItem('jov-theme', 'dark');
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.classList.add('dark');
            document.documentElement.style.colorScheme = 'dark';
        }""")
        await page_tab.goto("http://localhost:5173")
        await page_tab.wait_for_selector("text=Scattered → Clarity")
        await asyncio.sleep(1.5)
        p_tab = f"{QA_DIR}/04_hero_tablet_dark.png"
        await page_tab.screenshot(path=p_tab)
        shutil.copy(p_tab, os.path.join(ARTIFACT_DIR, "04_hero_tablet_dark.png"))
        print("Captured 04_hero_tablet_dark.png")
        await context_tab.close()

        await browser.close()

    # Terminate background processes
    for proc in [vite_p, api_p, mock_p]:
        try:
            proc.terminate()
            proc.kill()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(run())
