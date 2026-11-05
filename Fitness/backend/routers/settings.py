from fastapi import APIRouter, HTTPException

from backend.config import load_settings, save_settings
from backend.schemas import SettingsIn
from src import local_llm

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings():
    return load_settings()


@router.put("")
def update_settings(settings: SettingsIn):
    current = load_settings()

    if settings.ollama_model is not None:
        model = settings.ollama_model.strip()
        # Only locally downloaded, non-cloud models can be selected.
        try:
            local_llm.check_model(model)
        except local_llm.LocalLLMError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        current["ollama_model"] = model

    save_settings(current)
    return current
