from services.kra_automation import register_kra_pin


# Task Registry
SERVICE_MAP = {
    "KRA_PIN_REGISTRATION": register_kra_pin,

}

async def dispatch_automation_job(job_type: str, payload: dict) -> dict:
    """Routes an incoming background job to its specific Playwright service module."""
    handler = SERVICE_MAP.get(job_type)
    if not handler:
        raise ValueError(f"Unknown automation job type: {job_type}")
    
    return await handler(**payload)