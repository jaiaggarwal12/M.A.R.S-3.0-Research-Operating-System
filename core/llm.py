from __future__ import annotations
from langchain_core.language_models import BaseChatModel
from core import config

def get_llm(temperature: float | None = None) -> BaseChatModel:
    t = temperature if temperature is not None else config.TEMPERATURE
    p = config.LLM_PROVIDER.lower()
    if p == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.OPENAI_MODEL, temperature=t, api_key=config.OPENAI_API_KEY)
    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.ANTHROPIC_MODEL, temperature=t, api_key=config.ANTHROPIC_API_KEY)
    if p == "ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL, temperature=t)
    raise ValueError(f"Unknown LLM_PROVIDER='{p}'")
