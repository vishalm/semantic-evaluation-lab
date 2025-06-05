import os
import sys
from typing import Optional, List

def validate_required_env_vars(required_vars: List[str], config_type: str) -> bool:
    """Validate that required environment variables are set"""
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables for {config_type}:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please create a .env file or set these environment variables.")
        print("   You can copy env.example to .env and fill in the values.")
        return False
    return True

def str_to_bool(value: str) -> bool:
    """Convert string to boolean"""
    return value.lower() in ('true', '1', 'yes', 'on')

class AppConfig:
    """Main application configuration"""
    
    def __init__(self):
        self.use_ollama = str_to_bool(os.getenv("USE_OLLAMA", "true"))
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create config from environment variables"""
        return cls()

class OllamaConfig:
    """Configuration class for Ollama settings"""
    
    def __init__(self):
        self.host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model_id: str = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:latest")
        self.service_id: str = os.getenv("OLLAMA_SERVICE_ID", "ollama")
    
    @classmethod
    def from_env(cls) -> "OllamaConfig":
        """Create config from environment variables"""
        # Ollama has sensible defaults, so no required vars to check
        return cls()

class AzureOpenAIConfig:
    """Configuration class for Azure OpenAI settings"""
    
    def __init__(self):
        self.api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.deployment_name: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-35-turbo")
        self.api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        self.service_id: str = os.getenv("AZURE_OPENAI_SERVICE_ID", "azure_openai")
    
    @classmethod
    def from_env(cls, app_config: AppConfig) -> "AzureOpenAIConfig":
        """Create config from environment variables"""
        # Only check required environment variables if not using Ollama
        if not app_config.use_ollama:
            required_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
            if not validate_required_env_vars(required_vars, "Azure OpenAI"):
                print("⚠️  Azure OpenAI configuration incomplete. The service may not work properly.")
                print("💡 Set USE_OLLAMA=true to use Ollama instead, or provide Azure OpenAI credentials.\n")
        else:
            print("ℹ️  Using Ollama - Azure OpenAI configuration not required.\n")
        
        return cls()

class AgentConfig:
    """Configuration class for Agent settings"""
    
    def __init__(self):
        self.name: str = os.getenv("AGENT_NAME", "SK-Assistant")
        self.instructions: str = os.getenv("AGENT_INSTRUCTIONS", "You are a helpful assistant.")
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables"""
        return cls()

# Global config instances
app_config = AppConfig.from_env()
ollama_config = OllamaConfig.from_env()
azure_config = AzureOpenAIConfig.from_env(app_config)
agent_config = AgentConfig.from_env()

# Maintain backward compatibility
config = ollama_config 