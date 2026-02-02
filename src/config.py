"""Configuration management for Twilio-to-Agent-Bridge."""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Twilio credentials
    twilio_account_sid: str = Field(..., description="Twilio Account SID")
    twilio_auth_token: str = Field(..., description="Twilio Auth Token")
    twilio_phone_number: str = Field(..., description="Twilio phone number to call from")

    # Server configuration
    server_host: str = Field(default="0.0.0.0", description="FastAPI server host")
    server_port: int = Field(default=8000, description="FastAPI server port")
    websocket_port: int = Field(default=8001, description="WebSocket server port")
    public_url: str = Field(..., description="Public URL for webhooks (ngrok URL)")

    # Audio configuration
    audio_sample_rate: int = Field(default=8000, description="Audio sample rate (Hz)")
    audio_channels: int = Field(default=1, description="Audio channels (1=mono)")
    audio_buffer_size: int = Field(default=1024, description="PyAudio buffer size")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("twilio_phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        if not v.startswith("+"):
            raise ValueError("Phone number must start with + and include country code")
        return v

    @field_validator("public_url")
    @classmethod
    def validate_public_url(cls, v: str) -> str:
        """Validate and clean public URL."""
        # Remove trailing slash if present
        return v.rstrip("/")

    @property
    def twiml_url(self) -> str:
        """Get the full TwiML webhook URL."""
        return f"{self.public_url}/twiml"

    @property
    def websocket_url(self) -> str:
        """Get the WebSocket URL for Twilio Media Streams."""
        # Convert http/https to ws/wss
        ws_protocol = "wss" if self.public_url.startswith("https") else "ws"
        # Extract host from public_url
        host = self.public_url.replace("https://", "").replace("http://", "")
        return f"{ws_protocol}://{host}/media-stream"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_settings() -> Settings:
    """Load settings from environment variables and .env file."""
    return get_settings()
