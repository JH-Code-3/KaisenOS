"""
The only way this app talks to a language model: Ollama on THIS machine.

Guarantees, enforced in code (not just by convention):
- The Ollama URL must be localhost / 127.0.0.1 / ::1, or startup fails.
  OLLAMA_HOST, proxy environment variables and HTTP redirects are all
  ignored, so nothing can quietly point requests elsewhere.
- Only locally downloaded models are allowed. Ollama "cloud" models
  (e.g. "gpt-oss:120b-cloud") run on ollama.com, so they're refused.
- The model name comes from settings (data/settings.json -> ollama_model).
"""

from urllib.parse import urlparse

import ollama

OLLAMA_URL = "http://localhost:11434"
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}

# A downloaded model is gigabytes; a cloud model's local stub is tiny.
MIN_LOCAL_MODEL_BYTES = 50 * 1024 * 1024


class LocalLLMError(Exception):
    """Ollama is misconfigured, unreachable, or the model isn't local."""


def assert_local_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme != "http" or host not in ALLOWED_HOSTS:
        raise LocalLLMError(
            f"Refusing to use Ollama at {url!r}: only http://localhost, "
            "http://127.0.0.1 or http://[::1] are allowed."
        )


def is_cloud_model_name(name: str) -> bool:
    tag = name.split(":", 1)[1] if ":" in name else ""
    return tag == "cloud" or tag.endswith("-cloud") or name.endswith("-cloud")


def _client() -> ollama.Client:
    assert_local_url(OLLAMA_URL)

    client = ollama.Client(
        host=OLLAMA_URL,          # explicit, so OLLAMA_HOST is never consulted
        trust_env=False,          # ignore HTTP(S)_PROXY / ALL_PROXY
        follow_redirects=False,   # a local server can't bounce us elsewhere
        timeout=300,
    )

    # Belt and braces: check what the HTTP client will actually use.
    assert_local_url(str(client._client.base_url))
    return client


def list_local_models() -> list[str]:
    """Names of models downloaded to this machine (cloud models excluded)."""

    try:
        response = _client().list()
    except ConnectionError as exc:
        raise LocalLLMError(
            "Can't reach Ollama at http://localhost:11434. Is the Ollama app running?"
        ) from exc

    names = []

    for model in response.models:
        name = model.model or ""
        if not name or is_cloud_model_name(name):
            continue
        if (model.size or 0) < MIN_LOCAL_MODEL_BYTES:
            continue
        names.append(name)

    return sorted(names)


def check_model(model_name: str) -> None:
    """Raise LocalLLMError unless `model_name` is downloaded locally."""

    if is_cloud_model_name(model_name):
        raise LocalLLMError(
            f"{model_name!r} is an Ollama cloud model, which runs off this machine. "
            "Choose a locally downloaded model in Settings."
        )

    local = list_local_models()

    if model_name not in local:
        available = ", ".join(local) or "none"
        raise LocalLLMError(
            f"Model {model_name!r} isn't downloaded locally (available: {available}). "
            f"Download it with: ollama pull {model_name}"
        )


def chat(model: str, messages: list, **kwargs):
    """ollama.chat, restricted to localhost and a local model."""

    check_model(model)

    try:
        return _client().chat(model=model, messages=messages, **kwargs)
    except ConnectionError as exc:
        raise LocalLLMError(
            "Can't reach Ollama at http://localhost:11434. Is the Ollama app running?"
        ) from exc
