import asyncio
import logging
import re
from pathlib import Path
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright

# Setup logging & output directories
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KRA_Automation")

DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def solve_kra_math_stamp(text: str) -> int:
    """Extracts and solves KRA's security stamp arithmetic (e.g., 'What is 12 + 5 ?' -> 17)."""
    match = re.search(r"(\d+)\s*([\+\-\*])\s*(\d+)", text)
    if not match:
        raise ValueError(f"Could not parse security stamp expression from: {text}")

    num1, operator, num2 = int(match.group(1)), match.group(2), int(match.group(3))

    if operator == "+":
        return num1 + num2
    elif operator == "-":
        return num1 - num2
    elif operator == "*":
        return num1 * num2
    raise ValueError(f"Unsupported operator: {operator}")


async def execute_kra_registration_task(
    phone_number: str,
    national_id: str,
    dob: str,  # Format: DD/MM/YYYY
    name: str,
    email: str,
) -> dict:
    """Automates KRA PIN registration on iTax portal and saves acknowledgement receipt."""
    logger.info(f"Starting KRA PIN registration task for ID: {national_id}")

    # Split full name into first and last name
    name_parts = name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]

    async with async_playwright() as p:
        # Launch headless browser (set headless=False during testing)
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        try:
            # 1. Navigate to KRA iTax Landing Page
            logger.info("Navigating to KRA iTax Portal...")
            await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="networkidle", timeout=60000)

            # 2. Click "Register New PIN"
            await page.click("text=Register New PIN", timeout=15000)
            await page.wait_for_load_state("networkidle")

            # 3. Select Individual Taxpayer Type & Online Form
            await page.select_option("select[name='vo.taxPayerType']", label="Individual")
            await page.select_option("select[name='vo.modeOfReg']", label="Online Form")
            await page.click("input[value='Next']")
            await page.wait_for_load_state("networkidle")

            # 4. Fill Basic Information (Section A)
            logger.info("Filling applicant details...")
            
            # Select Citizenship (Kenyan)
            await page.check("input[value='KENYAN']")

            # Fill National ID and trigger lookup/validation
            await page.fill("input[name='vo.nationalId']", national_id)
            await page.fill("input[name='vo.dob']", dob)
            
            # Name and Contact details
            await page.fill("input[name='vo.firstName']", first_name)
            await page.fill("input[name='vo.lastName']", last_name)
            await page.fill("input[name='vo.emailId']", email)
            await page.fill("input[name='vo.mobileNo']", phone_number.replace("+", ""))

            # 5. Solve Security Stamp (KRA Arithmetic CAPTCHA)
            logger.info("Solving KRA Security Stamp...")
            captcha_label = await page.inner_text("#captchaText", timeout=5000)
            captcha_answer = solve_kra_math_stamp(captcha_label)
            logger.info(f"Stamp expression: '{captcha_label.strip()}' -> Answer: {captcha_answer}")

            await page.fill("input[name='captchacode']", str(captcha_answer))

            # 6. Submit Form and Capture Confirmation
            logger.info("Submitting registration form...")
            async with page.expect_download(timeout=30000) as download_info:
                await page.click("input[name='btnSubmit']")

            download = await download_info.value
            pdf_path = DOWNLOAD_DIR / f"KRA_PIN_{national_id}.pdf"
            await download.save_as(pdf_path)

            logger.info(f"KRA Registration successful. Certificate saved to {pdf_path}")

            return {
                "status": "SUCCESS",
                "national_id": national_id,
                "pdf_path": str(pdf_path),
                "error": None,
            }

        except PlaywrightTimeoutError:
            logger.error("Timeout occurred during portal navigation or form submission.")
            await page.screenshot(path=str(DOWNLOAD_DIR / f"error_{national_id}.png"))
            return {"status": "FAILED", "error": "Portal timeout or unresponsive element."}

        except Exception as e:
            logger.error(f"Automation error: {str(e)}")
            await page.screenshot(path=str(DOWNLOAD_DIR / f"error_{national_id}.png"))
            return {"status": "FAILED", "error": str(e)}

        finally:
            await browser.close()