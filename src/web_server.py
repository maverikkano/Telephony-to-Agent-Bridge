"""FastAPI web server for Twilio webhooks and TwiML generation."""

import logging
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import PlainTextResponse
import uvicorn

from .config import Settings
from .audio_player import AudioPlayer
from .websocket_handler import MediaStreamHandler


logger = logging.getLogger(__name__)


def create_app(settings: Settings, audio_player: AudioPlayer) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Application settings
        audio_player: AudioPlayer instance for WebSocket handler

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Twilio-to-Agent-Bridge",
        description="Bridge Twilio calls to laptop speakers via WebSocket",
        version="1.0.0"
    )

    # Create media stream handler
    media_handler = MediaStreamHandler(audio_player)

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Twilio-to-Agent-Bridge",
            "status": "running",
            "websocket_url": settings.websocket_url
        }

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.post("/twiml")
    async def twiml_handler(request: Request):
        """
        TwiML webhook endpoint for Twilio calls.

        When a call is answered, Twilio requests TwiML instructions from this endpoint.
        We return TwiML that:
        1. Starts a Media Stream to our WebSocket server
        2. Plays a brief message
        3. Keeps the call alive with a long pause

        Returns:
            TwiML XML response
        """
        # Log the incoming request
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "Unknown")
        call_status = form_data.get("CallStatus", "Unknown")
        from_number = form_data.get("From", "Unknown")
        to_number = form_data.get("To", "Unknown")

        logger.info(
            f"TwiML requested - CallSID: {call_sid}, Status: {call_status}, "
            f"From: {from_number}, To: {to_number}"
        )

        # Generate TwiML with Media Stream
        websocket_url = settings.websocket_url

        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="{websocket_url}" />
    </Start>
    <Say>You are now connected to the audio bridge.</Say>
    <Pause length="3600"/>
</Response>'''

        logger.info(f"Returning TwiML with WebSocket URL: {websocket_url}")

        # Return TwiML as XML
        return Response(
            content=twiml,
            media_type="application/xml"
        )

    @app.post("/call/status")
    async def call_status_handler(request: Request):
        """
        Optional endpoint for call status updates.

        Twilio can send status updates (ringing, answered, completed, etc.)
        if configured when creating the call.
        """
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "Unknown")
        call_status = form_data.get("CallStatus", "Unknown")

        logger.info(f"Call status update - CallSID: {call_sid}, Status: {call_status}")

        return {"status": "received"}

    @app.websocket("/media-stream")
    async def websocket_endpoint(websocket: WebSocket):
        """
        WebSocket endpoint for Twilio Media Streams.

        This receives real-time audio data from Twilio and forwards it to the audio player.
        """
        await websocket.accept()
        logger.info(f"WebSocket connection accepted from {websocket.client}")

        try:
            async for message in websocket.iter_text():
                await media_handler.handle_message(message)
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            logger.info("WebSocket connection closed")

    return app


async def start_web_server(
    settings: Settings,
    audio_player: AudioPlayer,
    host: str = None,
    port: int = None
):
    """
    Start the FastAPI web server.

    Args:
        settings: Application settings
        audio_player: AudioPlayer instance for WebSocket handler
        host: Host to bind to (defaults to settings.server_host)
        port: Port to listen on (defaults to settings.server_port)
    """
    host = host or settings.server_host
    port = port or settings.server_port

    app = create_app(settings, audio_player)

    logger.info(f"Starting FastAPI server on {host}:{port}")
    logger.info(f"WebSocket endpoint available at ws://{host}:{port}/media-stream")

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        access_log=True
    )

    server = uvicorn.Server(config)
    await server.serve()
