"""Twilio call initiator for making outbound calls."""

import logging
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from .config import Settings


logger = logging.getLogger(__name__)


class CallInitiator:
    """Initiates outbound calls via Twilio API."""

    def __init__(self, settings: Settings):
        """
        Initialize the call initiator.

        Args:
            settings: Application settings with Twilio credentials
        """
        self.settings = settings
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )

        logger.info(
            f"CallInitiator initialized with account: "
            f"{settings.twilio_account_sid[:8]}..."
        )

    def start_call(
        self,
        to_number: str,
        status_callback: bool = True
    ) -> Optional[str]:
        """
        Make an outbound call to the specified number.

        Args:
            to_number: Phone number to call (E.164 format: +15551234567)
            status_callback: Whether to receive call status updates

        Returns:
            Call SID if successful, None if failed
        """
        try:
            # Validate phone number format
            if not to_number.startswith("+"):
                logger.error(
                    f"Invalid phone number format: {to_number}. "
                    "Must start with + and include country code (E.164 format)"
                )
                return None

            # Get webhook URL for TwiML
            url = self.settings.twiml_url

            # Optional status callback URL
            status_callback_url = None
            if status_callback:
                status_callback_url = f"{self.settings.public_url}/call/status"

            logger.info(
                f"Initiating call to {to_number} from {self.settings.twilio_phone_number}"
            )
            logger.info(f"TwiML webhook URL: {url}")

            # Create the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.settings.twilio_phone_number,
                url=url,
                status_callback=status_callback_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST"
            )

            logger.info(
                f"Call initiated successfully - CallSID: {call.sid}, "
                f"Status: {call.status}"
            )

            return call.sid

        except TwilioRestException as e:
            logger.error(
                f"Twilio API error: {e.code} - {e.msg}",
                exc_info=True
            )
            return None
        except Exception as e:
            logger.error(f"Failed to initiate call: {e}", exc_info=True)
            return None

    def get_call_status(self, call_sid: str) -> Optional[str]:
        """
        Get the current status of a call.

        Args:
            call_sid: The call SID to check

        Returns:
            Call status string or None if error
        """
        try:
            call = self.client.calls(call_sid).fetch()
            logger.info(f"Call {call_sid} status: {call.status}")
            return call.status
        except TwilioRestException as e:
            logger.error(f"Failed to get call status: {e.code} - {e.msg}")
            return None
        except Exception as e:
            logger.error(f"Error fetching call status: {e}")
            return None

    def hangup_call(self, call_sid: str) -> bool:
        """
        Hang up an active call.

        Args:
            call_sid: The call SID to hang up

        Returns:
            True if successful, False otherwise
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call {call_sid} hung up successfully")
            return True
        except TwilioRestException as e:
            logger.error(f"Failed to hang up call: {e.code} - {e.msg}")
            return False
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
            return False
