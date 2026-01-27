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
    provider: Optional[str] = None,
    use_case: Optional[str] = None
) -> BaseChatModel:
    """
    Factory function to create an LLM instance based on configuration.
    
    Args:
        model_name: Specific model to use (overrides defaults and use_case)
        temperature: Temperature setting (default: 0.1)
        provider: Force a specific provider ("openai" or "gemini")
                 If None, uses LLM_PROVIDER env var or defaults to "openai"
        use_case: Use case identifier that maps to provider-appropriate models:
                 - "medical_analysis" -> gpt-5.1 / gemini-1.5-pro
                 - "letter_generation" -> gpt-4o / gemini-1.5-pro
                 - "matching" -> gpt-5 / gemini-1.5-flash
                 - "default" -> gpt-5.1 / gemini-1.5-pro
    
    Returns:
        LangChain ChatModel instance (ChatOpenAI or ChatGoogleGenerativeAI)
        The instance will have a _provider attribute set to "openai" or "gemini"
    """
    # Determine provider
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    provider = provider.lower()
    
    # If model_name is provided, use it directly (allows explicit override)
    # Otherwise, map use_case to provider-appropriate model, or use default
    if model_name is None:
        if use_case:
            model_name = _get_model_for_use_case(use_case, provider)
        else:
            # No model_name and no use_case - use default for provider
            model_name = _get_model_for_use_case("default", provider)
    
    logger.info(f"🔧 [LLM Config] Creating LLM instance - Provider: {provider.upper()}, Model: {model_name}, Temperature: {temperature}, UseCase: {use_case or 'default'}")
    
    if provider == "gemini":
        llm = _create_gemini_llm(model_name, temperature)
    else:  # default to openai
        llm = _create_openai_llm(model_name, temperature)
    
    # Add provider attribute for easy identification
    llm._provider = provider
    return llm


def _get_model_for_use_case(use_case: str, provider: str) -> Optional[str]:
    """
    Map use case to provider-appropriate model.
    
    Args:
        use_case: Use case identifier
        provider: Provider name ("openai" or "gemini")
    
    Returns:
        Model name appropriate for the provider and use case
    """
    # Model mappings by provider and use case
    model_mappings = {
        "openai": {
            "medical_analysis": "gpt-5.1",
            "letter_generation": "gpt-4o",
            "matching": "gpt-5",
            "default": "gpt-5.1"
        },
        "gemini": {
            "medical_analysis": "gemini-3-pro-preview",
            "letter_generation": "gemini-3-pro-preview",
            "matching": "gemini-3-pro-preview",
            "default": "gemini-3-pro-preview"
        }
    }
    
    provider_mappings = model_mappings.get(provider.lower(), model_mappings["openai"])
    return provider_mappings.get(use_case.lower(), provider_mappings.get("default"))


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
    
    # Use provided model_name, or fall back to env var, or default
    model = model_name or os.getenv("LLM_MODEL", "gpt-5.1")
    
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
    
    # Use provided model_name, or fall back to env var, or default
    model = model_name or os.getenv("LLM_MODEL", "gemini-3-pro-preview")
    
    logger.info(f"🤖 [LLM] Provider: Gemini | Model: {model} | Temperature: {temperature}")
    
    llm_instance = ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key
    )
    
    logger.info(f"✅ [LLM] Gemini LLM instance created successfully")
    return llm_instance
