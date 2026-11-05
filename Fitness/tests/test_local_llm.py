from types import SimpleNamespace

import pytest

from src import local_llm


@pytest.mark.parametrize(
    "url, ok",
    [
        ("http://localhost:11434", True),
        ("http://127.0.0.1:11434", True),
        ("http://[::1]:11434", True),
        ("http://example.com:11434", False),
        ("https://localhost:11434", False),
        ("http://localhost.evil.com:11434", False),
        ("http://10.0.0.5:11434", False),
    ],
)
def test_only_localhost_urls_allowed(url, ok):
    if ok:
        local_llm.assert_local_url(url)
    else:
        with pytest.raises(local_llm.LocalLLMError):
            local_llm.assert_local_url(url)


def test_client_ignores_ollama_host_and_proxy_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://example.com:11434")
    monkeypatch.setenv("HTTPS_PROXY", "http://example.com:9")
    monkeypatch.setenv("HTTP_PROXY", "http://example.com:9")
    client = local_llm._client()
    assert client._client.base_url.host == "localhost"
    assert client._client.follow_redirects is False


@pytest.mark.parametrize("name", ["gpt-oss:120b-cloud", "qwen3:cloud", "deepseek-v3.1:671b-cloud"])
def test_cloud_models_refused(name):
    assert local_llm.is_cloud_model_name(name)
    with pytest.raises(local_llm.LocalLLMError, match="cloud"):
        local_llm.check_model(name)


def fake_models(monkeypatch, models):
    fake = SimpleNamespace(list=lambda: SimpleNamespace(models=[SimpleNamespace(model=m, size=s) for m, s in models]))
    monkeypatch.setattr(local_llm, "_client", lambda: fake)


def test_list_excludes_cloud_and_stub_models(monkeypatch):
    fake_models(
        monkeypatch,
        [("gpt-oss:20b", 13_000_000_000), ("gpt-oss:120b-cloud", 384), ("mystery:latest", 1_000), ("llama3:8b", 4_700_000_000)],
    )
    assert local_llm.list_local_models() == ["gpt-oss:20b", "llama3:8b"]


def test_missing_model_gives_pull_hint(monkeypatch):
    fake_models(monkeypatch, [("gpt-oss:20b", 13_000_000_000)])
    with pytest.raises(local_llm.LocalLLMError, match="ollama pull llama3:8b"):
        local_llm.check_model("llama3:8b")
