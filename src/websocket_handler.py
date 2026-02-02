"""WebSocket handler for Twilio Media Streams."""

import asyncio
import json
import logging
from typing import Optional
import websockets
from websockets.server import WebSocketServerProtocol

from .audio_player import AudioPlayer


logger = logging.getLogger(__name__)


class MediaStreamHandler:
    """Handles Twilio Media Stream WebSocket connections."""

    def __init__(self, audio_player: AudioPlayer):
        """
        Initialize the media stream handler.

        Args:
            audio_player: AudioPlayer instance to send audio to
        """
        self.audio_player = audio_player
        self.stream_sid: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.sequence_number = 0

        logger.info("MediaStreamHandler initialized")

    async def handle_connection(
        self,
        websocket: WebSocketServerProtocol,
        path: str
    ):
        """
        Handle incoming WebSocket connection from Twilio.

        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        logger.info(f"WebSocket connection established from {websocket.remote_address}")

        try:
            async for message in websocket:
                await self.handle_message(message)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        finally:
            logger.info(
                f"WebSocket connection terminated. "
                f"Processed {self.sequence_number} messages"
            )

    async def handle_message(self, message: str):
        """
        Process incoming WebSocket message from Twilio.

        Twilio sends four types of events:
        - connected: Initial connection confirmation
        - start: Stream metadata
        - media: Audio data (most frequent)
        - stop: Stream ended

        Args:
            message: JSON message from Twilio
        """
        try:
            data = json.loads(message)
            event = data.get("event")
            self.sequence_number += 1

            if event == "connected":
                await self.handle_connected(data)
            elif event == "start":
                await self.handle_start(data)
            elif event == "media":
                await self.handle_media(data)
            elif event == "stop":
                await self.handle_stop(data)
            else:
                logger.warning(f"Unknown event type: {event}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def handle_connected(self, data: dict):
        """
        Handle 'connected' event.

        Example:
        {
          "event": "connected",
          "protocol": "Call",
          "version": "1.0.0"
        }
        """
        protocol = data.get("protocol")
        version = data.get("version")

        logger.info(f"Connected to Twilio Media Stream: {protocol} v{version}")

    async def handle_start(self, data: dict):
        """
        Handle 'start' event with stream metadata.

        Example:
        {
          "event": "start",
          "sequenceNumber": "1",
          "start": {
            "streamSid": "MZ...",
            "accountSid": "AC...",
            "callSid": "CA...",
            "tracks": ["inbound"],
            "mediaFormat": {
              "encoding": "audio/x-mulaw",
              "sampleRate": 8000,
              "channels": 1
            }
          },
          "streamSid": "MZ..."
        }
        """
        start_data = data.get("start", {})
        self.stream_sid = start_data.get("streamSid")
        self.call_sid = start_data.get("callSid")

        media_format = start_data.get("mediaFormat", {})
        encoding = media_format.get("encoding")
        sample_rate = media_format.get("sampleRate")
        channels = media_format.get("channels")
        tracks = start_data.get("tracks", [])

        logger.info(
            f"Stream started - StreamSID: {self.stream_sid}, "
            f"CallSID: {self.call_sid}"
        )
        logger.info(
            f"Media format: {encoding}, {sample_rate}Hz, {channels} channel(s), "
            f"tracks: {tracks}"
        )

        # Verify format matches our expectations
        if encoding != "audio/x-mulaw":
            logger.warning(f"Unexpected encoding: {encoding}, expected audio/x-mulaw")
        if sample_rate != 8000:
            logger.warning(f"Unexpected sample rate: {sample_rate}Hz, expected 8000Hz")

    async def handle_media(self, data: dict):
        """
        Handle 'media' event with audio data.

        This is the most frequent event (~50 messages per second).

        Example:
        {
          "event": "media",
          "sequenceNumber": "2",
          "media": {
            "track": "inbound",
            "chunk": "1",
            "timestamp": "5",
            "payload": "base64-encoded-mulaw-audio"
          },
          "streamSid": "MZ..."
        }
        """
        media_data = data.get("media", {})
        payload = media_data.get("payload")
        track = media_data.get("track")
        chunk = media_data.get("chunk")
        timestamp = media_data.get("timestamp")

        if not payload:
            logger.warning("Received media event with no payload")
            return

        # Queue audio for playback
        await self.audio_player.queue_audio(payload)

        # Log periodically (every 50 messages to avoid spam)
        if self.sequence_number % 50 == 0:
            queue_size = self.audio_player.get_queue_size()
            logger.info(
                f"Media: seq={self.sequence_number}, track={track}, "
                f"chunk={chunk}, timestamp={timestamp}ms, "
                f"queue_size={queue_size}"
            )

    async def handle_stop(self, data: dict):
        """
        Handle 'stop' event when stream ends.

        Example:
        {
          "event": "stop",
          "sequenceNumber": "3",
          "stop": {
            "accountSid": "AC...",
            "callSid": "CA..."
          },
          "streamSid": "MZ..."
        }
        """
        stop_data = data.get("stop", {})
        account_sid = stop_data.get("accountSid")
        call_sid = stop_data.get("callSid")

        logger.info(
            f"Stream stopped - CallSID: {call_sid}, "
            f"Total messages processed: {self.sequence_number}"
        )


async def start_websocket_server(
    audio_player: AudioPlayer,
    host: str = "0.0.0.0",
    port: int = 8001
):
    """
    Start the WebSocket server for Twilio Media Streams.

    Args:
        audio_player: AudioPlayer instance to send audio to
        host: Host to bind to
        port: Port to listen on

    Returns:
        The WebSocket server
    """
    handler = MediaStreamHandler(audio_player)

    logger.info(f"Starting WebSocket server on {host}:{port}")

    server = await websockets.serve(
        handler.handle_connection,
        host,
        port
    )

    logger.info(f"WebSocket server listening on ws://{host}:{port}/media-stream")

    return server
