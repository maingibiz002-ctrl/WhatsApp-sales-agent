import logging
from services.base_browser import DOWNLOAD_DIR, get_browser_context, solve_math_captcha

logger = logging.getLogger("KRA_Service")


async def register_kra_pin(
    phone_number: str, national_id: str, dob: str, name: str, email: str
) -> dict:
    """Handles KRA PIN registration exclusively."""
    p, browser, page = await get_browser_context(headless=True)

    try:
        await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="networkidle")
        await page.click("text=Register New PIN")
        # ... Rest of KRA-specific steps ...

        return {"status": "SUCCESS", "national_id": national_id}

    except Exception as e:
        logger.error(f"KRA Registration Failed: {e}")
        await page.screenshot(path=str(DOWNLOAD_DIR / f"kra_error_{national_id}.png"))
        return {"status": "FAILED", "error": str(e)}

    finally:
        await browser.close()
        await p.stop()