"""Tests for local SLM provider — all mocked, no model files or server needed."""

import json
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# Mock actions module to avoid CGEvent import
with patch.dict("sys.modules", {"vozctl.actions": MagicMock()}):
    from vozctl.slm_local import LlamaServer, LocalSLMProvider


class TestLlamaServer(unittest.TestCase):
    """LlamaServer subprocess management."""

    def test_init_defaults(self):
        srv = LlamaServer("/tmp/model.gguf")
        assert srv.model_path == "/tmp/model.gguf"
        assert srv.port == 8372
        assert srv.n_gpu_layers == -1
        assert srv.ctx_size == 2048

    @patch("vozctl.slm_local.shutil.which", return_value=None)
    def test_start_fails_without_binary(self, _which):
        srv = LlamaServer("/tmp/model.gguf")
        assert srv.start() is False

    @patch("vozctl.slm_local.os.path.isfile", return_value=False)
    @patch("vozctl.slm_local.shutil.which", return_value="/usr/local/bin/llama-server")
    def test_start_fails_without_model(self, _which, _isfile):
        srv = LlamaServer("/tmp/nonexistent.gguf")
        assert srv.start() is False

    def test_is_running_false_initially(self):
        srv = LlamaServer("/tmp/model.gguf")
        assert srv.is_running() is False

    def test_stop_idempotent(self):
        srv = LlamaServer("/tmp/model.gguf")
        # Should not raise even with no process
        srv.stop()
        srv.stop()


class TestLocalSLMProvider(unittest.TestCase):
    """LocalSLMProvider HTTP client."""

    def _make_provider(self, running=True):
        server = MagicMock(spec=LlamaServer)
        server.is_running.return_value = running
        server._base_url = "http://127.0.0.1:8372"
        return LocalSLMProvider(server)

    def test_not_available_when_server_down(self):
        provider = self._make_provider(running=False)
        assert provider.is_available() is False

    def test_available_when_server_running(self):
        provider = self._make_provider(running=True)
        assert provider.is_available() is True

    def test_complete_returns_none_when_unavailable(self):
        provider = self._make_provider(running=False)
        result = provider.complete(system_prompt="test", transcript="hello")
        assert result is None

    @patch("vozctl.slm_local.urllib.request.urlopen")
    def test_complete_parses_openai_response(self, mock_urlopen):
        response_body = json.dumps({
            "choices": [{
                "message": {"content": '[{"kind":"command","name":"save"}]'}
            }]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        provider = self._make_provider(running=True)
        result = provider.complete(system_prompt="test", transcript="save the file")
        assert result == '[{"kind":"command","name":"save"}]'

    @patch("vozctl.slm_local.urllib.request.urlopen", side_effect=OSError("connection refused"))
    def test_complete_returns_none_on_error(self, _urlopen):
        provider = self._make_provider(running=True)
        result = provider.complete(system_prompt="test", transcript="hello")
        assert result is None

    def test_name(self):
        provider = self._make_provider()
        assert provider.name == "local_qwen"


class TestCreateSLMProvider(unittest.TestCase):
    """Factory function tests."""

    def test_none_returns_null(self):
        with patch.dict("sys.modules", {"vozctl.actions": MagicMock()}):
            from vozctl.intent import create_slm_provider, NullSLMProvider
            provider = create_slm_provider("none")
            assert isinstance(provider, NullSLMProvider)

    def test_unknown_returns_null(self):
        with patch.dict("sys.modules", {"vozctl.actions": MagicMock()}):
            from vozctl.intent import create_slm_provider, NullSLMProvider
            provider = create_slm_provider("bogus")
            assert isinstance(provider, NullSLMProvider)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False)
    def test_haiku_without_key_returns_provider(self):
        """Haiku provider is returned even without key — it handles availability internally."""
        with patch.dict("sys.modules", {"vozctl.actions": MagicMock()}):
            from vozctl.intent import create_slm_provider, AnthropicSLMProvider
            provider = create_slm_provider("haiku")
            assert isinstance(provider, AnthropicSLMProvider)

    @patch("vozctl.slm_local.LlamaServer.start", return_value=False)
    def test_local_falls_back_on_start_failure(self, _start):
        with patch.dict("sys.modules", {"vozctl.actions": MagicMock()}):
            from vozctl.intent import create_slm_provider, NullSLMProvider
            provider = create_slm_provider("local", model_dir="/tmp")
            assert isinstance(provider, NullSLMProvider)


if __name__ == "__main__":
    unittest.main()
