"""Entry point for `python -m vozctl`."""

from __future__ import annotations

import argparse
import sys

from vozctl import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vozctl",
        description="Voice control for developers — offline speech-to-action pipeline.",
    )
    p.add_argument("--version", action="version", version=f"vozctl {__version__}")

    # Mic selection
    p.add_argument("--list-mics", action="store_true", help="List available microphones and exit.")
    p.add_argument("--mic-name", type=str, help="Select microphone by name substring.")
    p.add_argument("--mic-id", type=int, help="Select microphone by device ID.")

    # Runtime
    p.add_argument("--hotkey", type=str, default="ctrl+alt+v", help="Global hotkey to toggle listening (default: ctrl+alt+v).")
    p.add_argument("--model-dir", type=str, default="models", help="Directory containing STT/VAD models (default: models/).")

    # Diagnostics
    p.add_argument("--self-test", action="store_true", help="Run self-test checks and exit.")
    p.add_argument("--replay", type=str, metavar="WAV", help="Replay a .wav file through the pipeline instead of live mic.")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose/debug logging.")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Lazy imports — keep startup fast for --help/--version
    import logging

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("vozctl")

    if args.list_mics:
        from vozctl.audio import list_mics
        list_mics()
        return 0

    if args.self_test:
        from vozctl.self_test import run_self_test
        return run_self_test(args)

    if args.replay:
        from vozctl.engine import Engine
        engine = Engine(args)
        return engine.replay(args.replay)

    # Default: run the live engine
    # Early accessibility check — both pynput (hotkey) and CGEvents (key injection) need it
    from vozctl.actions import check_accessibility
    if not check_accessibility():
        return 1

    from vozctl.engine import Engine

    log.info("vozctl %s starting", __version__)
    engine = Engine(args)
    try:
        engine.run()
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
