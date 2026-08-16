import re
from pathlib import Path
from playwright.async_api import Browser, async_playwright

DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def solve_math_captcha(text: str) -> int:
    """Solves simple math expressions from security stamps."""
    match = re.search(r"(\d+)\s*([\+\-\*])\s*(\d+)", text)
    if not match:
        raise ValueError(f"Unable to parse expression from: {text}")

    num1, op, num2 = int(match.group(1)), match.group(2), int(match.group(3))
    ops = {"+": num1 + num2, "-": num1 - num2, "*": num1 * num2}
    return ops[op]


async def get_browser_context(headless: bool = True):
    """Initializes a Playwright browser instance with standard configurations."""
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=headless, args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    context = await browser.new_context(accept_downloads=True)
    page = await context.new_page()
    return p, browser, page