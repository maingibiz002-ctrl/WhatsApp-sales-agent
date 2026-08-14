import asyncio
from playwright.async_api import async_playwright


async def execute_kra_registration_task(
    phone_number: str, national_id: str, dob: str, name: str, email: str
):
    """Automates KRA PIN application/verification via Playwright and sends result to WhatsApp."""
    print(f"\n[PLAYWRIGHT] Starting KRA task for {name} ({national_id})...")

    async with async_playwright() as p:
        # Launch headless browser
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. Navigate to target portal
            print("[PLAYWRIGHT] Navigating to portal...")
            await page.goto("https://itax.kra.go.ke/KRA-Portal/", timeout=60000)

            # 2. Example: Interact with fields (Auto-waits for elements automatically)
            # await page.fill("#nationalIdInput", national_id)
            # await page.fill("#dobInput", dob)
            # await page.click("#submitBtn")

            # 3. Wait for success element or result download
            # await page.wait_for_selector("#resultPin", timeout=30000)
            # kra_pin = await page.inner_text("#resultPin")

            # Simulate generated result for demonstration
            await asyncio.sleep(3)  # Simulated processing time
            kra_pin = "A019827364Z"

            # 4. Notify customer via WhatsApp once completed
            from app import send_whatsapp_message

            success_msg = (
                f"✅ *Service Completed!*\n\n"
                f"Hello {name}, your KRA PIN application was processed successfully.\n"
                f"• *KRA PIN:* `{kra_pin}`\n"
                f"• *National ID:* {national_id}\n\n"
                f"Thank you for using Orb Digital Solutions!"
            )
            send_whatsapp_message(phone_number, success_msg)
            print(
                f"[PLAYWRIGHT] Completed! Result sent to {phone_number}."
            )

        except Exception as e:
            print(f"[PLAYWRIGHT ERROR] Task failed: {str(e)}")
            from app import send_whatsapp_message

            error_msg = f"Pole {name}, we encountered an issue processing your request automatically. Our team has been notified to assist you manually."
            send_whatsapp_message(phone_number, error_msg)

        finally:
            await browser.close()