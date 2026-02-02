# Twilio-to-Agent-Bridge

Bridge phone calls from Twilio to your laptop speakers in real-time using WebSocket streaming.

## Overview

This application makes Twilio call a phone number, and when the call is answered, streams the audio in real-time to your laptop speakers using Twilio Media Streams.

## Architecture

```
[You run script] → [Twilio API] → Calls Target Number
                                         ↓
                                   Call Answered
                                         ↓
                    [Twilio] ← [FastAPI TwiML Webhook]
                         ↓
              WebSocket Connection Established
                         ↓
         [Media Stream Handler] ← mulaw audio chunks
                         ↓
              [Audio Player] → mulaw → PCM conversion
                         ↓
                  Laptop Speakers
```

## Features

- Real-time audio streaming via Twilio Media Streams
- Low-latency audio playback (<1 second)
- mulaw to PCM audio conversion
- CLI interface for easy operation
- Comprehensive logging for debugging
- Graceful shutdown handling

## Prerequisites

1. **Python 3.9 or higher**
2. **Twilio Account**
   - Sign up at [twilio.com](https://www.twilio.com)
   - Purchase a phone number
   - Get your Account SID and Auth Token from the console
3. **PortAudio** (for PyAudio on macOS)
   ```bash
   brew install portaudio
   ```
4. **ngrok** (for local development)
   ```bash
   brew install ngrok
   # or download from https://ngrok.com
   ```

## Installation

### 1. Clone or navigate to the project

```bash
cd /Users/maverikkano/Developer/Telephony-to-Agent-Bridge
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp config/.env.example .env
```

Edit `.env` with your Twilio credentials:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
WEBSOCKET_PORT=8001

# Public URL (get from ngrok - see step 5)
PUBLIC_URL=https://your-subdomain.ngrok.io

# Audio Configuration (defaults are fine)
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_BUFFER_SIZE=1024

# Logging
LOG_LEVEL=INFO
```

### 5. Start ngrok

In a **separate terminal**, start ngrok to expose your local server:

```bash
ngrok http 8000
```

Copy the **Forwarding URL** (e.g., `https://abc123.ngrok.io`) and update `PUBLIC_URL` in your `.env` file.

**Important:** Keep this terminal running while using the application.

## Usage

### Basic Usage

Make sure your virtual environment is activated and ngrok is running, then:

```bash
python main.py --target +15551234567
```

Replace `+15551234567` with the phone number you want to call (must include country code).

### What Happens

1. Servers start (FastAPI on port 8000, WebSocket on port 8001)
2. Audio player initializes
3. Twilio places a call to the target number
4. When the call is answered, Twilio streams audio to your server
5. Audio plays through your laptop speakers in real-time

### Command-Line Options

```bash
# Make a call
python main.py --target +15551234567

# Change log level
python main.py --target +15551234567 --log-level DEBUG

# Start servers without making a call (for testing)
python main.py
```

### Stopping the Application

Press `Ctrl+C` to gracefully shut down. The application will:
- Hang up any active calls
- Stop the audio player
- Shut down servers
- Clean up resources

## Project Structure

```
Telephony-to-Agent-Bridge/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── audio_player.py        # Audio conversion and playback
│   ├── websocket_handler.py   # Twilio Media Stream handler
│   ├── web_server.py          # FastAPI server for webhooks
│   └── call_initiator.py      # Twilio API call initiator
├── config/
│   └── .env.example           # Example environment variables
├── tests/
│   └── __init__.py
├── requirements.txt           # Python dependencies
├── main.py                    # Main entry point
└── README.md                  # This file
```

## How It Works

### 1. Configuration ([src/config.py](src/config.py))
- Loads settings from `.env` file using Pydantic
- Validates Twilio credentials and URLs
- Provides configuration to all components

### 2. Call Initiation ([src/call_initiator.py](src/call_initiator.py))
- Uses Twilio SDK to make outbound calls
- Provides webhook URL for TwiML instructions
- Tracks call status

### 3. TwiML Generation ([src/web_server.py](src/web_server.py))
- FastAPI server handles webhook from Twilio
- Returns TwiML with `<Stream>` element
- Points Twilio to WebSocket server

### 4. WebSocket Streaming ([src/websocket_handler.py](src/websocket_handler.py))
- Receives Twilio Media Stream events
- Extracts base64-encoded mulaw audio
- Queues audio for playback

### 5. Audio Playback ([src/audio_player.py](src/audio_player.py))
- Converts mulaw to PCM (16-bit)
- Plays audio through PyAudio
- Manages audio buffer and queue

## Troubleshooting

### PyAudio installation fails on Mac

**Error:** `fatal error: 'portaudio.h' file not found`

**Solution:**
```bash
brew install portaudio
pip install --upgrade pip
pip install pyaudio
```

### No audio output

**Check:**
1. Volume is turned up
2. Correct audio device selected in System Preferences
3. Check logs for PyAudio errors
4. Try: `python -c "import pyaudio; p = pyaudio.PyAudio(); print(p.get_default_output_device_info())"`

### WebSocket connection fails

**Check:**
1. ngrok is running and URL matches `PUBLIC_URL` in `.env`
2. Firewall allows connections on ports 8000 and 8001
3. Check ngrok web interface at http://127.0.0.1:4040 for request logs

### Call not placed

**Check:**
1. Twilio credentials are correct in `.env`
2. Phone number includes `+` and country code (E.164 format)
3. Twilio account has sufficient balance
4. Check Twilio console for error messages

### Choppy audio

**Try:**
1. Check network connection
2. Increase `AUDIO_BUFFER_SIZE` in `.env` (try 2048)
3. Close other applications using audio/network
4. Check system resource usage

## Technical Details

### Audio Format
- **Input:** mulaw (μ-law), 8kHz, mono, 8-bit compressed
- **Output:** PCM, 8kHz, mono, 16-bit
- **Conversion:** `audioop.ulaw2lin()`

### WebSocket Messages
- Twilio sends ~50 media messages per second
- Each chunk contains ~20ms of audio
- Messages include sequence numbers for tracking

### Dependencies
- **twilio:** Twilio SDK for API calls
- **fastapi:** Web server for webhooks
- **websockets:** WebSocket server
- **pyaudio:** Audio playback
- **audioop-lts:** Audio format conversion
- **pydantic:** Configuration management

## Logging

Logs include:
- Server startup/shutdown events
- Twilio API calls and responses
- WebSocket connection events
- Audio playback statistics
- Errors and warnings

Set log level with `--log-level`:
- `DEBUG`: Verbose logging including audio chunks
- `INFO`: Standard operational logging (default)
- `WARNING`: Only warnings and errors
- `ERROR`: Only errors

## Security Notes

1. **Never commit `.env` file** - it contains sensitive credentials
2. **Use HTTPS/WSS in production** - ngrok provides this automatically
3. **Validate webhook signatures in production** - not implemented in this version
4. **Rotate Twilio tokens regularly**
5. **Use environment-specific credentials**

## Limitations

- Single call at a time (not concurrent)
- One-way audio (phone → laptop only)
- Maximum call duration: 1 hour (TwiML `<Pause>` limit)
- Requires public URL (ngrok for local dev)

## Future Enhancements

- Bidirectional audio (laptop mic → phone)
- Multiple concurrent calls
- Call recording to file
- Web UI for call management
- Speech-to-text transcription
- Call transfer functionality

## License

MIT License - feel free to use and modify as needed.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review logs with `--log-level DEBUG`
3. Check Twilio console for API errors
4. Check ngrok web interface for webhook requests

## Development

### Running Tests

```bash
pytest tests/
```

### Code Structure

- Each module is self-contained and testable
- Async/await for concurrent operations
- Type hints for better IDE support
- Comprehensive logging throughout
- Graceful error handling

### Adding Features

1. Add new functionality to appropriate module in `src/`
2. Update configuration in [src/config.py](src/config.py) if needed
3. Update [main.py](main.py) orchestration if needed
4. Add tests in `tests/`
5. Update this README

## Credits

Built with Python, Twilio Media Streams, FastAPI, and PyAudio.
