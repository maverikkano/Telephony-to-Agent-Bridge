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

## Technical Details

### Audio Format
- **Input:** mulaw (μ-law), 8kHz, mono, 8-bit compressed
- **Output:** PCM, 8kHz, mono, 16-bit
- **Conversion:** `audioop.ulaw2lin()`

### WebSocket Messages
- Twilio sends ~50 media messages per second
- Each chunk contains ~20ms of audio
- Messages include sequence numbers for tracking