"""Audio player for converting mulaw to PCM and playing through speakers."""

import asyncio
import base64
import logging
from typing import Optional
import pyaudio
try:
    import audioop
except ImportError:
    # Python 3.13+ moved audioop to a separate package
    import audioop_lts as audioop


logger = logging.getLogger(__name__)


class AudioPlayer:
    """Plays audio from Twilio Media Streams through laptop speakers."""

    def __init__(
        self,
        sample_rate: int = 8000,
        channels: int = 1,
        buffer_size: int = 1024
    ):
        """
        Initialize the audio player.

        Args:
            sample_rate: Audio sample rate in Hz (Twilio uses 8kHz)
            channels: Number of audio channels (1=mono, 2=stereo)
            buffer_size: PyAudio buffer size in frames
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size

        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self.is_playing = False
        self._play_task: Optional[asyncio.Task] = None

        logger.info(
            f"AudioPlayer initialized: {sample_rate}Hz, {channels} channel(s), "
            f"buffer size {buffer_size}"
        )

    def start(self):
        """Initialize PyAudio and open output stream."""
        try:
            self.audio = pyaudio.PyAudio()

            # Open audio output stream
            self.stream = self.audio.open(
                format=pyaudio.paInt16,  # 16-bit PCM
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.buffer_size
            )

            self.is_playing = True
            logger.info("Audio stream opened successfully")

            # Log available audio devices for debugging
            self._log_audio_devices()

        except Exception as e:
            logger.error(f"Failed to initialize audio stream: {e}")
            raise

    def _log_audio_devices(self):
        """Log available audio output devices."""
        if not self.audio:
            return

        try:
            device_count = self.audio.get_device_count()
            default_output = self.audio.get_default_output_device_info()

            logger.info(f"Available audio devices: {device_count}")
            logger.info(f"Using default output: {default_output['name']}")

            # Log all output devices
            for i in range(device_count):
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxOutputChannels'] > 0:
                    logger.debug(
                        f"Output device {i}: {device_info['name']} "
                        f"({device_info['maxOutputChannels']} channels)"
                    )

        except Exception as e:
            logger.warning(f"Could not log audio devices: {e}")

    def stop(self):
        """Stop playback and close audio stream."""
        self.is_playing = False

        if self._play_task and not self._play_task.done():
            self._play_task.cancel()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.info("Audio stream closed")

        if self.audio:
            self.audio.terminate()
            self.audio = None
            logger.info("PyAudio terminated")

    def decode_mulaw(self, mulaw_data: bytes) -> bytes:
        """
        Convert mulaw (μ-law) encoded audio to PCM.

        Args:
            mulaw_data: Raw mulaw encoded audio bytes

        Returns:
            PCM audio data as bytes (16-bit signed integers)
        """
        try:
            # Convert mulaw to PCM (16-bit)
            # audioop.ulaw2lin(fragment, width)
            # width=2 means 16-bit (2 bytes per sample)
            pcm_data = audioop.ulaw2lin(mulaw_data, 2)
            return pcm_data
        except Exception as e:
            logger.error(f"Failed to decode mulaw audio: {e}")
            return b""

    async def queue_audio(self, payload: str):
        """
        Queue base64-encoded mulaw audio for playback.

        Args:
            payload: Base64-encoded mulaw audio data from Twilio
        """
        try:
            # Decode base64 to raw mulaw bytes
            mulaw_data = base64.b64decode(payload)

            # Add to queue for playback
            await self.audio_queue.put(mulaw_data)

            logger.debug(
                f"Queued {len(mulaw_data)} bytes of mulaw audio "
                f"(queue size: {self.audio_queue.qsize()})"
            )

        except Exception as e:
            logger.error(f"Failed to queue audio: {e}")

    async def play_loop(self):
        """
        Main playback loop - consumes audio from queue and plays it.

        This should be run as an asyncio task.
        """
        logger.info("Starting audio playback loop")

        try:
            while self.is_playing:
                try:
                    # Get mulaw data from queue with timeout
                    mulaw_data = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=1.0
                    )

                    # Convert mulaw to PCM
                    pcm_data = self.decode_mulaw(mulaw_data)

                    if pcm_data and self.stream:
                        # Play audio through speakers
                        self.stream.write(pcm_data)

                        logger.debug(
                            f"Played {len(pcm_data)} bytes of PCM audio "
                            f"(from {len(mulaw_data)} mulaw bytes)"
                        )

                except asyncio.TimeoutError:
                    # No audio in queue, continue waiting
                    continue
                except Exception as e:
                    logger.error(f"Error in playback loop: {e}")
                    # Continue playing despite errors

        except asyncio.CancelledError:
            logger.info("Playback loop cancelled")
        finally:
            logger.info("Playback loop stopped")

    async def start_playback(self) -> asyncio.Task:
        """
        Start the playback loop as an asyncio task.

        Returns:
            The playback task
        """
        self.start()
        self._play_task = asyncio.create_task(self.play_loop())
        return self._play_task

    async def stop_playback(self):
        """Stop the playback loop and clean up resources."""
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
            try:
                await self._play_task
            except asyncio.CancelledError:
                pass

        self.stop()

    def get_queue_size(self) -> int:
        """Get the current size of the audio queue."""
        return self.audio_queue.qsize()
