"""Global pytest configuration and fixtures."""

import pytest
import os
from config import app_config, ollama_config


def pytest_configure(config):
    """Configure pytest markers and global settings."""
    # Check if we have any AI service available
    has_ollama = app_config.use_ollama
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_azure = bool(os.getenv("AZURE_OPENAI_API_KEY"))
    
    # DeepEval can work with either Ollama or OpenAI
    has_deepeval_support = has_ollama or has_openai
    
    # Store in config for use by collection hooks
    config.has_ai_service = has_ollama or has_openai or has_azure
    config.has_openai_key = has_openai
    config.has_ollama = has_ollama
    config.has_deepeval_support = has_deepeval_support


def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip tests when services are unavailable."""
    has_ai_service = getattr(config, 'has_ai_service', False)
    has_deepeval_support = getattr(config, 'has_deepeval_support', False)
    has_ollama = getattr(config, 'has_ollama', False)
    
    # Define skip reasons
    skip_functional = pytest.mark.skip(
        reason="Functional tests require either Ollama (use_ollama=True) or OpenAI API key"
    )
    skip_deepeval = pytest.mark.skip(
        reason="DeepEval tests require either Ollama (use_ollama=True) or OpenAI API key (OPENAI_API_KEY)"
    )
    skip_no_ai = pytest.mark.skip(
        reason="No AI service available - need either Ollama or OpenAI/Azure API key"
    )
    
    for item in items:
        # Skip functional tests if no AI service is available
        if "functional" in item.keywords and not has_ai_service:
            item.add_marker(skip_functional)
        
        # Skip deepeval tests if no DeepEval support (neither Ollama nor OpenAI)
        if ("llm_eval" in item.keywords or "deepeval" in item.keywords) and not has_deepeval_support:
            item.add_marker(skip_deepeval)
        
        # Skip both functional and deepeval if absolutely no services
        if not has_ai_service:
            if ("functional" in item.keywords or 
                "llm_eval" in item.keywords or 
                "deepeval" in item.keywords):
                item.add_marker(skip_no_ai)


@pytest.fixture(scope="session", autouse=True)
def validate_test_environment():
    """Validate test environment and provide warnings."""
    has_ollama = app_config.use_ollama
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_azure = bool(os.getenv("AZURE_OPENAI_API_KEY"))
    has_deepeval_support = has_ollama or has_openai
    
    print("\n" + "="*60)
    print("TEST ENVIRONMENT VALIDATION")
    print("="*60)
    print(f"Ollama enabled: {has_ollama}")
    print(f"OpenAI API key: {'✓' if has_openai else '✗'}")
    print(f"Azure OpenAI API key: {'✓' if has_azure else '✗'}")
    print(f"DeepEval support: {'✓' if has_deepeval_support else '✗'}")
    
    if not has_ollama and not has_openai and not has_azure:
        print("\n⚠️  WARNING: No AI services configured!")
        print("   - Functional tests will be skipped")
        print("   - DeepEval tests will be skipped")
        print("   - Only unit tests will run")
        print("\nTo enable tests:")
        print("   1. For Ollama: Set USE_OLLAMA=true in config and ensure Ollama is running")
        print("   2. For OpenAI: Set OPENAI_API_KEY environment variable")
        print("   3. For Azure: Set AZURE_OPENAI_API_KEY environment variable")
    
    elif has_deepeval_support:
        if has_ollama and has_openai:
            print("\n✓ Both Ollama and OpenAI available")
            print("   - DeepEval tests will use Ollama (preferred for local evaluation)")
            print("   - Functional tests will run with Ollama")
        elif has_ollama:
            print("\n✓ Ollama configured")
            print("   - DeepEval tests will use Ollama for local evaluation")
            print("   - Functional tests will run with Ollama")
        elif has_openai:
            print("\n✓ OpenAI configured")
            print("   - DeepEval tests will use OpenAI")
            print("   - Functional tests will run with OpenAI")
    
    else:
        print("\n⚠️  Note: DeepEval tests will be skipped")
        print("   - Need either Ollama or OpenAI for LLM evaluation")
        print("   - Functional tests may still run if Azure is configured")
    
    print("="*60)


@pytest.fixture(scope="session")
def deepeval_model():
    """Provide the appropriate DeepEval model based on available services."""
    has_ollama = app_config.use_ollama
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    
    if has_ollama:
        # Import inside fixture to avoid collection-time import issues
        from deepeval.models import OllamaModel
        
        print(f"Using Ollama model for DeepEval: {ollama_config.model_id} at {ollama_config.host}")
        return OllamaModel(
            model=ollama_config.model_id,
            base_url=ollama_config.host,
            timeout=120,
            options={
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 512
            }
        )
    elif has_openai:
        # Default DeepEval behavior uses OpenAI
        print("Using OpenAI model for DeepEval")
        return None  # DeepEval uses OpenAI by default when no model is specified
    else:
        pytest.skip("No model available for DeepEval - need either Ollama or OpenAI")


@pytest.fixture
def skip_if_no_ollama():
    """Skip test if Ollama is not configured."""
    if not app_config.use_ollama:
        pytest.skip("Ollama not configured for use")


@pytest.fixture
def skip_if_no_openai():
    """Skip test if OpenAI API key is not available."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key required")


@pytest.fixture
def skip_if_no_deepeval_support():
    """Skip test if no DeepEval support is available."""
    has_ollama = app_config.use_ollama
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    
    if not (has_ollama or has_openai):
        pytest.skip("DeepEval support requires either Ollama or OpenAI API key")


@pytest.fixture 
def skip_if_no_ai_service():
    """Skip test if no AI service is available."""
    has_ollama = app_config.use_ollama
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_azure = bool(os.getenv("AZURE_OPENAI_API_KEY"))
    
    if not (has_ollama or has_openai or has_azure):
        pytest.skip("No AI service available - need Ollama or OpenAI/Azure API key")


@pytest.fixture(scope="session")
def test_environment_info():
    """Provide test environment information."""
    return {
        "has_ollama": app_config.use_ollama,
        "has_openai": bool(os.getenv("OPENAI_API_KEY")),
        "has_azure": bool(os.getenv("AZURE_OPENAI_API_KEY")),
        "ollama_host": ollama_config.host,
        "ollama_model": ollama_config.model_id,
        "has_deepeval_support": app_config.use_ollama or bool(os.getenv("OPENAI_API_KEY"))
    } 