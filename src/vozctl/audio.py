"""Microphone enumeration and audio stream management."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_MS = 30  # 30ms blocks for VAD


def list_mics() -> None:
    """Print available input devices and exit."""
    import sounddevice as sd

    print("Available input devices:")
    print("-" * 60)
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = " *" if i == sd.default.device[0] else ""
            print(f"  [{i}] {dev['name']} (ch={dev['max_input_channels']}){marker}")
    print()
    print("  * = system default")


def resolve_mic(mic_name: str | None = None, mic_id: int | None = None) -> int | None:
    """Resolve mic selection to a device ID. Returns None for system default."""
    import sounddevice as sd

    if mic_id is not None:
        dev = sd.query_devices(mic_id)
        if dev["max_input_channels"] == 0:
            raise ValueError(f"Device {mic_id} ({dev['name']}) has no input channels")
        log.info("Selected mic by ID: [%d] %s", mic_id, dev["name"])
        return mic_id

    if mic_name is not None:
        devices = sd.query_devices()
        needle = mic_name.lower()
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0 and needle in dev["name"].lower():
                log.info("Selected mic by name: [%d] %s", i, dev["name"])
                return i
        raise ValueError(f"No input device matching '{mic_name}'")

    return None  # system default


def open_stream(device_id: int | None, callback):
    """Open a sounddevice InputStream for VAD-sized blocks."""
    import sounddevice as sd

    block_size = int(SAMPLE_RATE * BLOCK_MS / 1000)
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=block_size,
        device=device_id,
        callback=callback,
    )
    dev = sd.query_devices(device_id if device_id is not None else sd.default.device[0])
    log.info("Audio stream: %s @ %dHz, %dch, %dms blocks", dev["name"], SAMPLE_RATE, CHANNELS, BLOCK_MS)
    return stream
