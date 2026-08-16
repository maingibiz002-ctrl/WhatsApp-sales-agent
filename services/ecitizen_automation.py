import logging
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from services.base_browser import DOWNLOAD_DIR, get_browser_context

logger = logging.getLogger("eCitizen_Service")


async def ecitizen_login_and_fetch_status(
    id_number: str, password: str, service_id: str = None
) -> dict:
    """Logs into eCitizen and fetches application status or profile details."""
    p, browser, page = await get_browser_context(headless=True)

    try:
        logger.info(f"Navigating to eCitizen login portal for ID: {id_number}...")
        await page.goto("https://accounts.ecitizen.go.ke/en/login", wait_until="networkidle")

        # 1. Fill Login Form
        await page.fill("input[type='text'], input[name='email']", id_number)
        await page.fill("input[type='password']", password)
        await page.click("button:has-text('Sign In'), button[type='submit']")
        await page.wait_for_load_state("networkidle")

        # 2. Handle OTP prompt if triggered
        if await page.is_visible("text=Enter OTP"):
            logger.warning("OTP required for eCitizen login.")
            return {
                "status": "OTP_REQUIRED",
                "message": "OTP sent to taxpayer phone. Awaiting verification code.",
            }

        # 3. Check for Dashboard Load
        await page.wait_for_selector(".dashboard-container, text=Services", timeout=15000)
        logger.info("eCitizen Authentication successful.")

        # Optional: Fetch specific service status if provided
        if service_id:
            status_url = f"https://ecitizen.go.ke/applications/{service_id}"
            await page.goto(status_url, wait_until="networkidle")
            status_text = await page.inner_text(".application-status")
            return {"status": "SUCCESS", "application_status": status_text.strip()}

        return {"status": "SUCCESS", "authenticated": True}

    except PlaywrightTimeoutError:
        logger.error(f"Timeout on eCitizen portal for ID: {id_number}")
        await page.screenshot(path=str(DOWNLOAD_DIR / f"ecitizen_error_{id_number}.png"))
        return {"status": "FAILED", "error": "eCitizen portal timeout."}

    except Exception as e:
        logger.error(f"eCitizen automation error: {str(e)}")
        await page.screenshot(path=str(DOWNLOAD_DIR / f"ecitizen_error_{id_number}.png"))
        return {"status": "FAILED", "error": str(e)}

    finally:
        await browser.close()
        await p.stop()