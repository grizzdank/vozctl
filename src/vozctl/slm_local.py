"""Local SLM provider: Qwen3.5-0.8B via llama-server (llama.cpp).

Manages the llama-server subprocess lifecycle and provides an SLMProvider
that talks to its OpenAI-compatible HTTP endpoint using stdlib only.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request

from vozctl.intent import SLMProvider

log = logging.getLogger(__name__)

_DEFAULT_PORT = 8372


class LlamaServer:
    """Manages a llama-server subprocess."""

    def __init__(
        self,
        model_path: str,
        port: int = _DEFAULT_PORT,
        n_gpu_layers: int = -1,
        ctx_size: int = 2048,
    ):
        self.model_path = model_path
        self.port = port
        self.n_gpu_layers = n_gpu_layers
        self.ctx_size = ctx_size
        self._process: subprocess.Popen | None = None
        self._base_url = f"http://127.0.0.1:{port}"

    def start(self) -> bool:
        """Start llama-server. Returns True if healthy within timeout."""
        binary = shutil.which("llama-server")
        if not binary:
            log.warning("llama-server not found in PATH (brew install llama.cpp)")
            return False

        if not os.path.isfile(self.model_path):
            log.warning("SLM model not found: %s", self.model_path)
            return False

        cmd = [
            binary,
            "--model", self.model_path,
            "--port", str(self.port),
            "--n-gpu-layers", str(self.n_gpu_layers),
            "--ctx-size", str(self.ctx_size),
            "--log-disable",
        ]
        log.info("Starting llama-server: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as e:
            log.warning("Failed to launch llama-server: %s", e)
            return False

        atexit.register(self.stop)

        # Poll /health until ready (15 retries × 200ms = 3s max)
        for i in range(15):
            time.sleep(0.2)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode(errors="replace") if self._process.stderr else ""
                log.warning("llama-server exited early (code %d): %s", self._process.returncode, stderr[:500])
                self._process = None
                return False
            try:
                req = urllib.request.Request(f"{self._base_url}/health")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    if resp.status == 200:
                        log.info("llama-server healthy after %.1fs", (i + 1) * 0.2)
                        return True
            except (urllib.error.URLError, OSError):
                pass

        log.warning("llama-server failed to become healthy within 3s")
        self.stop()
        return False

    def stop(self) -> None:
        """Stop the server. Idempotent."""
        if self._process is None:
            return
        if self._process.poll() is not None:
            self._process = None
            return

        log.info("Stopping llama-server (pid %d)", self._process.pid)
        self._process.send_signal(signal.SIGTERM)
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.warning("llama-server didn't exit, sending SIGKILL")
            self._process.kill()
            self._process.wait(timeout=2)
        self._process = None

    def is_running(self) -> bool:
        """Check if the server process is still alive."""
        return self._process is not None and self._process.poll() is None


class LocalSLMProvider(SLMProvider):
    """SLM provider backed by a local llama-server instance."""

    name = "local_qwen"

    def __init__(self, server: LlamaServer):
        self._server = server
        self._base_url = server._base_url

    def is_available(self) -> bool:
        return self._server.is_running()

    def complete(self, *, system_prompt: str, transcript: str) -> str | None:
        if not self.is_available():
            return None

        payload = json.dumps({
            "model": "local",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            "temperature": 0.0,
            "max_tokens": 256,
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, OSError, KeyError, IndexError, json.JSONDecodeError) as e:
            log.warning("Local SLM request failed: %s", e)
            return None
