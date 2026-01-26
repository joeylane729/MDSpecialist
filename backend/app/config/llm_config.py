"""
LLM Configuration Module

Supports both OpenAI (GPT) and Google (Gemini) providers.
Configure via environment variables:
- LLM_PROVIDER: "openai" or "gemini" (default: "openai")
- OPENAI_API_KEY: Required if using OpenAI
- GOOGLE_API_KEY: Required if using Gemini
- LLM_MODEL: Override default model (optional)
"""

import os
import logging
from typing import Optional, Any
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

def get_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.1,
    provider: Optional[str] = None
) -> BaseChatModel:
    """
    Factory function to create an LLM instance based on configuration.
    
    Args:
        model_name: Specific model to use (overrides defaults)
        temperature: Temperature setting (default: 0.1)
        provider: Force a specific provider ("openai" or "gemini")
                 If None, uses LLM_PROVIDER env var or defaults to "openai"
    
    Returns:
        LangChain ChatModel instance (ChatOpenAI or ChatGoogleGenerativeAI)
        The instance will have a _provider attribute set to "openai" or "gemini"
    """
    # Determine provider
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    provider = provider.lower()
    
    logger.info(f"🔧 [LLM Config] Creating LLM instance - Provider: {provider.upper()}, Model: {model_name or 'default'}, Temperature: {temperature}")
    
    if provider == "gemini":
        llm = _create_gemini_llm(model_name, temperature)
    else:  # default to openai
        llm = _create_openai_llm(model_name, temperature)
    
    # Add provider attribute for easy identification
    llm._provider = provider
    return llm


def _create_openai_llm(model_name: Optional[str], temperature: float) -> Any:
    """Create OpenAI ChatOpenAI instance."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai is not installed. "
            "Install it with: pip install langchain-openai"
        )
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required when using OpenAI provider"
        )
    
    # Default models for OpenAI
    default_models = {
        "default": "gpt-5.1",
        "medical_analysis": "gpt-5.1",
        "letter_generation": "gpt-4o",
        "matching": "gpt-5"
    }
    
    model = model_name or os.getenv("LLM_MODEL", default_models.get("default", "gpt-5.1"))
    
    logger.info(f"🤖 [LLM] Provider: OpenAI | Model: {model} | Temperature: {temperature}")
    
    llm_instance = ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key
    )
    
    logger.info(f"✅ [LLM] OpenAI LLM instance created successfully")
    return llm_instance


def _create_gemini_llm(model_name: Optional[str], temperature: float) -> Any:
    """Create Google Gemini ChatGoogleGenerativeAI instance."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise ImportError(
            "langchain-google-genai is not installed. "
            "Install it with: pip install langchain-google-genai"
        )
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY environment variable is required when using Gemini provider"
        )
    
    # Default models for Gemini
    default_models = {
        "default": "gemini-1.5-pro",
        "medical_analysis": "gemini-1.5-pro",
        "letter_generation": "gemini-1.5-pro",
        "matching": "gemini-1.5-flash"  # Faster/cheaper for matching tasks
    }
    
    model = model_name or os.getenv("LLM_MODEL", default_models.get("default", "gemini-1.5-pro"))
    
    logger.info(f"🤖 [LLM] Provider: Gemini | Model: {model} | Temperature: {temperature}")
    
    llm_instance = ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key
    )
    
    logger.info(f"✅ [LLM] Gemini LLM instance created successfully")
    return llm_instance
