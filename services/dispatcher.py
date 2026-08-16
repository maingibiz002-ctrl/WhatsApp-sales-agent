from services.kra_automation import register_kra_pin
from services.ecitizen_automation import ecitizen_login_and_fetch_status
from services.ntsa_automation import verify_ntsa_logbook, check_driving_license_status

# Task Registry
SERVICE_MAP = {
    "KRA_PIN_REGISTRATION": register_kra_pin,
    "ECITIZEN_STATUS": ecitizen_login_and_fetch_status,
    "NTSA_VERIFY_LOGBOOK": verify_ntsa_logbook,
    "NTSA_CHECK_DL": check_driving_license_status,
}

async def dispatch_automation_job(job_type: str, payload: dict) -> dict:
    """Routes an incoming background job to its specific Playwright service module."""
    handler = SERVICE_MAP.get(job_type)
    if not handler:
        raise ValueError(f"Unknown automation job type: {job_type}")
    
    return await handler(**payload)