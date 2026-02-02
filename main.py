"""Main entry point for Twilio-to-Agent-Bridge."""

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from src.config import load_settings
from src.audio_player import AudioPlayer
from src.web_server import start_web_server
from src.call_initiator import CallInitiator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class Application:
    """Main application orchestrator."""

    def __init__(self, target_number: Optional[str] = None):
        """
        Initialize the application.

        Args:
            target_number: Phone number to call (optional, can be provided via CLI)
        """
        self.target_number = target_number
        self.settings = load_settings()
        self.audio_player: Optional[AudioPlayer] = None
        self.call_initiator: Optional[CallInitiator] = None
        self.call_sid: Optional[str] = None
        self.shutdown_event = asyncio.Event()

        logger.info("Application initialized")

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start_servers(self):
        """Start all required servers."""
        logger.info("Starting servers...")

        # Initialize audio player
        self.audio_player = AudioPlayer(
            sample_rate=self.settings.audio_sample_rate,
            channels=self.settings.audio_channels,
            buffer_size=self.settings.audio_buffer_size
        )

        # Start audio playback
        await self.audio_player.start_playback()
        logger.info("Audio player started")

        # Start FastAPI server (includes WebSocket endpoint)
        asyncio.create_task(
            start_web_server(self.settings, self.audio_player)
        )

        logger.info("All servers started successfully")

    async def initiate_call(self):
        """Initiate the Twilio call."""
        if not self.target_number:
            logger.error("No target number provided")
            return False

        self.call_initiator = CallInitiator(self.settings)

        logger.info(f"Initiating call to {self.target_number}...")

        self.call_sid = self.call_initiator.start_call(self.target_number)

        if self.call_sid:
            logger.info(f"Call initiated successfully: {self.call_sid}")
            logger.info("Waiting for call to be answered...")
            logger.info("Once answered, speak into the phone and audio will play through your laptop speakers")
            return True
        else:
            logger.error("Failed to initiate call")
            return False

    async def cleanup(self):
        """Clean up resources on shutdown."""
        logger.info("Cleaning up resources...")

        # Hang up active call if any
        if self.call_sid and self.call_initiator:
            logger.info(f"Hanging up call {self.call_sid}")
            self.call_initiator.hangup_call(self.call_sid)

        # Stop audio player
        if self.audio_player:
            await self.audio_player.stop_playback()
            logger.info("Audio player stopped")

        logger.info("Cleanup complete")

    async def run(self):
        """Main application loop."""
        try:
            # Set up signal handlers
            self.setup_signal_handlers()

            # Display configuration
            logger.info("=" * 60)
            logger.info("Twilio-to-Agent-Bridge")
            logger.info("=" * 60)
            logger.info(f"Public URL: {self.settings.public_url}")
            logger.info(f"TwiML URL: {self.settings.twiml_url}")
            logger.info(f"WebSocket URL: {self.settings.websocket_url}")
            logger.info(f"FastAPI Server: {self.settings.server_host}:{self.settings.server_port}")
            logger.info(f"WebSocket Endpoint: /media-stream (integrated with FastAPI)")
            logger.info("=" * 60)

            # Start servers
            await self.start_servers()

            # Give servers time to start
            await asyncio.sleep(2)

            # Initiate call if target number provided
            if self.target_number:
                success = await self.initiate_call()
                if not success:
                    logger.error("Call initiation failed, but servers will continue running")
            else:
                logger.info("No target number provided. Servers running, waiting for manual call...")
                logger.info("To make a call, use: --target +15551234567")

            # Wait for shutdown signal
            logger.info("Press Ctrl+C to stop")
            await self.shutdown_event.wait()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            await self.cleanup()


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Twilio-to-Agent-Bridge: Stream phone call audio to laptop speakers"
    )
    parser.add_argument(
        "--target",
        "-t",
        type=str,
        help="Target phone number to call (E.164 format: +15551234567)"
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(args.log_level)

    # Create and run application
    app = Application(target_number=args.target)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
