import logging
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from services.base_browser import DOWNLOAD_DIR, get_browser_context

logger = logging.getLogger("NTSA_Service")


async def verify_ntsa_logbook(chassis_number: str) -> dict:
    """Verifies motor vehicle logbook details using NTSA's public verification service."""
    p, browser, page = await get_browser_context(headless=True)

    try:
        logger.info(f"Navigating to NTSA Service Portal for Chassis: {chassis_number}")
        await page.goto("https://serviceportal.ntsa.go.ke/", wait_until="networkidle")

        # Select Logbook Verification
        await page.fill("input[placeholder*='Chassis']", chassis_number)
        await page.click("button:has-text('Verify')")
        await page.wait_for_load_state("networkidle")

        # Extract result details
        result_element = await page.wait_for_selector(".verification-result", timeout=10000)
        result_text = await result_element.inner_text()

        return {
            "status": "SUCCESS",
            "chassis_number": chassis_number,
            "details": result_text.strip(),
        }

    except PlaywrightTimeoutError:
        logger.error(f"Timeout verifying NTSA chassis: {chassis_number}")
        await page.screenshot(path=str(DOWNLOAD_DIR / f"ntsa_error_{chassis_number}.png"))
        return {"status": "FAILED", "error": "NTSA portal timed out."}

    except Exception as e:
        logger.error(f"NTSA automation error: {str(e)}")
        return {"status": "FAILED", "error": str(e)}

    finally:
        await browser.close()
        await p.stop()


async def check_driving_license_status(id_number: str, password: str) -> dict:
    """Logs into NTSA via eCitizen SSO and checks Smart Driving License status."""
    p, browser, page = await get_browser_context(headless=True)

    try:
        logger.info("Accessing NTSA Portal via eCitizen SSO...")
        await page.goto("https://ntsa.ecitizen.go.ke/", wait_until="networkidle")
        await page.click("text=Sign In")

        # eCitizen SSO Login Handoff
        await page.fill("input[name='email']", id_number)
        await page.fill("input[name='password']", password)
        await page.click("button:has-text('Sign In')")
        await page.wait_for_load_state("networkidle")

        # Navigate to Driving License section
        await page.click("text=Driving License")
        await page.click("text=Check Status")
        
        dl_status = await page.inner_text(".dl-status-badge")
        
        return {"status": "SUCCESS", "id_number": id_number, "dl_status": dl_status.strip()}

    except Exception as e:
        logger.error(f"Failed DL status check: {str(e)}")
        await page.screenshot(path=str(DOWNLOAD_DIR / f"ntsa_dl_error_{id_number}.png"))
        return {"status": "FAILED", "error": str(e)}

    finally:
        await browser.close()
        await p.stop()