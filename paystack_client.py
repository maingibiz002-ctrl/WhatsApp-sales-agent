import os
import requests

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_key_here")

import os
import requests

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_key_here")

class PaystackManager:
    def __init__(self):
        self.secret_key = PAYSTACK_SECRET_KEY
        self.base_url = "https://api.paystack.co"

    def format_phone_number(self, phone: str) -> str:
        """
        Paystack Mobile Money KES strictly requires 2547XXXXXXXX or 2541XXXXXXXX format (12 digits).
        """
        # Keep digits only
        digits = "".join(filter(str.isdigit, str(phone)))

        # Convert 0712345678 or 012345678 -> 254712345678
        if digits.startswith("0") and len(digits) == 10:
            return f"254{digits[1:]}"
        elif len(digits) == 9 and (digits.startswith("7") or digits.startswith("1")):
            return f"254{digits}"

        return digits

    def trigger_mpesa_stk_push(self, phone_number: str, amount: float, email: str = None):
        """
        Triggers M-Pesa STK Push directly via Paystack's Charge API.
        """
        formatted_phone = self.format_phone_number(phone_number)

        if not email:
            email = f"customer_{formatted_phone}@chatseller.co.ke"

        # Paystack expects amount in subunit/cents (KSh * 100)
        amount_in_cents = int(float(amount) * 100)

        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "amount": amount_in_cents,
            "email": email,
            "currency": "KES",
            "mobile_money": {
                "phone": formatted_phone,
                "provider": "mpesa"
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/charge",
                json=payload,
                headers=headers,
                timeout=20
            )
            print("\n--- PAYSTACK RAW RESPONSE ---")
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            return response.json()
        except Exception as e:
            return {"status": False, "message": str(e)}