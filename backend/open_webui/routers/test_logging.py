"""
Test endpoint for validating Datadog and Sentry integration.
This endpoint should only be available in dev environments.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from open_webui.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test-logging")
async def test_logging(user=Depends(get_admin_user)):
    """
    Test endpoint for Datadog and Sentry integration.

    This endpoint:
    1. Logs a warning message
    2. Logs an error message
    3. Raises an exception (caught by Sentry)

    Only accessible to admin users.
    """
    # Log a warning
    log.warning("Test warning log from test-logging endpoint")

    # Log an error (message doesn't contain "ERROR" to verify level detection)
    log.error("Test critical log from test-logging endpoint")

    # Raise an exception to test Sentry integration
    raise HTTPException(
        status_code=500,
        detail="Test exception from test-logging endpoint - this is intentional for testing Datadog and Sentry integration"
    )
