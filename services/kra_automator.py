import os
import re
import asyncio
from playwright.async_api import async_playwright

class KRAAutomator:
    """
    Automates KRA iTax workflows: NIL Returns, Certificate Downloads, and PIN Registration.
    """
    def __init__(self, downloads_dir: str = "downloads"):
        self.downloads_dir = downloads_dir
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.base_url = "https://itax.kra.go.ke/KRA-Portal/"

    async def _solve_captcha(self, page) -> int:
        """Extracts and solves the iTax math arithmetic captcha (e.g., '12 + 4 =')."""
        try:
            captcha_text = await page.inner_text("#captchatext")
            match = re.search(r'(\d+)\s*([\+\-\*])\s*(\d+)', captcha_text)
            if match:
                num1, operator, num2 = match.groups()
                num1, num2 = int(num1), int(num2)
                if operator == '+':
                    return num1 + num2
                elif operator == '-':
                    return num1 - num2
                elif operator == '*':
                    return num1 * num2
            raise ValueError(f"Could not parse captcha expression: {captcha_text}")
        except Exception as e:
            print(f"[Captcha Error] {e}")
            raise

    async def _login(self, page, kra_pin: str, password: str):
        """Handles logging into the iTax Portal."""
        await page.goto(self.base_url, timeout=60000)
        
        # Step 1: Input PIN
        await page.fill("input[name='logId']", kra_pin)
        await page.click("input[id='checkUser']")
        await page.wait_for_timeout(1500)

        # Step 2: Input Password & Captcha
        await page.fill("input[name='dummyPass']", password)
        captcha_solution = await self._solve_captcha(page)
        await page.fill("input[name='captchacode']", str(captcha_solution))

        # Step 3: Submit Login
        await page.click("a[id='loginButton']")
        await page.wait_for_selector("text=Returns", timeout=30000)

    async def file_nil_return(self, kra_pin: str, password: str, year: str = "2025") -> dict:
        """Automates Individual NIL Tax Return filing."""
        receipt_path = os.path.join(self.downloads_dir, f"KRA_NIL_Receipt_{kra_pin}.pdf")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                await self._login(page, kra_pin, password)

                # Navigate to Returns -> File Nil Return
                await page.hover("text=Returns")
                await page.click("text=File Nil Return")

                # Select Tax Obligation
                await page.select_option("select[name='taxObligation']", label="Income Tax - Resident Individual")
                await page.click("input[name='Next']")

                # Set Return Dates
                await page.fill("input[name='returnPeriodFrom']", f"01/01/{year}")
                await page.fill("input[name='returnPeriodTo']", f"31/12/{year}")

                # Handle alert and download on submit
                page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
                async with page.expect_download() as download_info:
                    await page.click("input[name='Submit']")

                download = await download_info.value
                await download.save_as(receipt_path)

                await browser.close()
                return {"success": True, "file_path": receipt_path, "service": "NIL_RETURN"}

            except Exception as e:
                await browser.close()
                return {"success": False, "error": str(e), "service": "NIL_RETURN"}

    async def download_pin_certificate(self, kra_pin: str, password: str) -> dict:
        """Reprints and downloads an existing KRA PIN Certificate PDF."""
        cert_path = os.path.join(self.downloads_dir, f"KRA_PIN_Certificate_{kra_pin}.pdf")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            try:
                await self._login(page, kra_pin, password)

                # Navigate to Registration -> Reprint PIN Certificate
                await page.hover("text=Registration")
                await page.click("text=Reprint PIN Certificate")

                # Select Applicant Type
                await page.select_option("select[name='applicantType']", label="Individual")
                
                async with page.expect_download() as download_info:
                    await page.click("input[name='Submit']")

                download = await download_info.value
                await download.save_as(cert_path)

                await browser.close()
                return {"success": True, "file_path": cert_path, "service": "DOWNLOAD_CERT"}

            except Exception as e:
                await browser.close()
                return {"success": False, "error": str(e), "service": "DOWNLOAD_CERT"}

    async def register_new_individual_pin(self, details: dict) -> dict:
        """
        Initiates Individual New PIN Registration from the public portal landing page.
        `details` requires: national_id, dob (DD/MM/YYYY), full_name, email, phone.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(self.base_url, timeout=60000)

                # Click "New PIN Registration" link
                await page.click("text=New PIN Registration")
                await page.select_option("select[name='taxpayerType']", label="Individual")
                await page.select_option("select[name='modeOfRegistration']", label="Online Form")
                await page.click("input[name='Next']")

                # Form Tab 1: Citizenship & Basic Info
                await page.check("input[value='Citizen']")
                await page.fill("input[name='nationalId']", details["national_id"])
                await page.fill("input[name='dob']", details["dob"])
                await page.fill("input[name='email']", details["email"])
                await page.fill("input[name='mobileNo']", details["phone"])

                # Solve Captcha and Submit Form Tab
                captcha_solution = await self._solve_captcha(page)
                await page.fill("input[name='captchacode']", str(captcha_solution))

                # Note: Full completion submits to KRA for instant PDF generation or email delivery
                await page.click("input[name='Submit']")
                await page.wait_for_timeout(3000)

                await browser.close()
                return {"success": True, "message": "PIN Registration submitted successfully.", "service": "NEW_PIN"}

            except Exception as e:
                await browser.close()
                return {"success": False, "error": str(e), "service": "NEW_PIN"}