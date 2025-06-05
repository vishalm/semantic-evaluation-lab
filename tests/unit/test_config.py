"""Unit tests for configuration module."""

import os
import pytest
from unittest.mock import patch, MagicMock
from config import (
    AppConfig,
    OllamaConfig,
    AzureOpenAIConfig,
    AgentConfig,
    validate_required_env_vars,
    str_to_bool,
)


class TestStrToBool:
    """Test str_to_bool function."""

    def test_true_values(self):
        """Test that various true values are converted correctly."""
        assert str_to_bool("true") is True
        assert str_to_bool("True") is True
        assert str_to_bool("TRUE") is True
        assert str_to_bool("1") is True
        assert str_to_bool("yes") is True
        assert str_to_bool("YES") is True
        assert str_to_bool("on") is True
        assert str_to_bool("ON") is True

    def test_false_values(self):
        """Test that various false values are converted correctly."""
        assert str_to_bool("false") is False
        assert str_to_bool("False") is False
        assert str_to_bool("FALSE") is False
        assert str_to_bool("0") is False
        assert str_to_bool("no") is False
        assert str_to_bool("NO") is False
        assert str_to_bool("off") is False
        assert str_to_bool("OFF") is False
        assert str_to_bool("random") is False


class TestValidateRequiredEnvVars:
    """Test validate_required_env_vars function."""

    @patch("builtins.print")
    def test_missing_variables(self, mock_print):
        """Test validation with missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_required_env_vars(
                ["MISSING_VAR1", "MISSING_VAR2"], "Test Service"
            )
            assert result is False
            mock_print.assert_called()

    @patch("builtins.print")
    def test_all_variables_present(self, mock_print):
        """Test validation when all variables are present."""
        with patch.dict(
            os.environ, {"PRESENT_VAR1": "value1", "PRESENT_VAR2": "value2"}
        ):
            result = validate_required_env_vars(
                ["PRESENT_VAR1", "PRESENT_VAR2"], "Test Service"
            )
            assert result is True
            mock_print.assert_not_called()

    @patch("builtins.print")
    def test_partial_variables_present(self, mock_print):
        """Test validation when some variables are missing."""
        with patch.dict(os.environ, {"PRESENT_VAR": "value"}, clear=True):
            result = validate_required_env_vars(
                ["PRESENT_VAR", "MISSING_VAR"], "Test Service"
            )
            assert result is False
            mock_print.assert_called()


class TestAppConfig:
    """Test AppConfig class."""

    def test_default_ollama_true(self):
        """Test that default configuration uses Ollama."""
        with patch.dict(os.environ, {}, clear=True):
            config = AppConfig()
            assert config.use_ollama is True

    def test_use_ollama_from_env(self):
        """Test that USE_OLLAMA environment variable is respected."""
        with patch.dict(os.environ, {"USE_OLLAMA": "false"}):
            config = AppConfig()
            assert config.use_ollama is False

        with patch.dict(os.environ, {"USE_OLLAMA": "true"}):
            config = AppConfig()
            assert config.use_ollama is True

    def test_from_env_class_method(self):
        """Test from_env class method."""
        with patch.dict(os.environ, {"USE_OLLAMA": "false"}):
            config = AppConfig.from_env()
            assert config.use_ollama is False


class TestOllamaConfig:
    """Test OllamaConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = OllamaConfig()
            assert config.host == "http://localhost:11434"
            assert config.model_id == "qwen2.5:latest"
            assert config.service_id == "ollama"

    def test_custom_values_from_env(self):
        """Test configuration from environment variables."""
        env_vars = {
            "OLLAMA_HOST": "http://custom-host:8080",
            "OLLAMA_MODEL_ID": "custom-model:v1",
            "OLLAMA_SERVICE_ID": "custom-service",
        }
        with patch.dict(os.environ, env_vars):
            config = OllamaConfig()
            assert config.host == "http://custom-host:8080"
            assert config.model_id == "custom-model:v1"
            assert config.service_id == "custom-service"

    def test_from_env_class_method(self):
        """Test from_env class method."""
        config = OllamaConfig.from_env()
        assert isinstance(config, OllamaConfig)


class TestAzureOpenAIConfig:
    """Test AzureOpenAIConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = AzureOpenAIConfig()
            assert config.api_key == ""
            assert config.endpoint == ""
            assert config.deployment_name == "gpt-35-turbo"
            assert config.api_version == "2024-02-01"
            assert config.service_id == "azure_openai"

    def test_custom_values_from_env(self):
        """Test configuration from environment variables."""
        env_vars = {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4",
            "AZURE_OPENAI_API_VERSION": "2024-03-01",
            "AZURE_OPENAI_SERVICE_ID": "custom-azure",
        }
        with patch.dict(os.environ, env_vars):
            config = AzureOpenAIConfig()
            assert config.api_key == "test-key"
            assert config.endpoint == "https://test.openai.azure.com/"
            assert config.deployment_name == "gpt-4"
            assert config.api_version == "2024-03-01"
            assert config.service_id == "custom-azure"

    @patch("builtins.print")
    def test_from_env_with_ollama_true(self, mock_print):
        """Test from_env when using Ollama (no validation needed)."""
        app_config = MagicMock()
        app_config.use_ollama = True
        
        config = AzureOpenAIConfig.from_env(app_config)
        assert isinstance(config, AzureOpenAIConfig)
        mock_print.assert_called_with("ℹ️  Using Ollama - Azure OpenAI configuration not required.\n")

    @patch("builtins.print")
    @patch("config.validate_required_env_vars")
    def test_from_env_with_ollama_false_valid_config(self, mock_validate, mock_print):
        """Test from_env when using Azure OpenAI with valid configuration."""
        app_config = MagicMock()
        app_config.use_ollama = False
        mock_validate.return_value = True
        
        config = AzureOpenAIConfig.from_env(app_config)
        assert isinstance(config, AzureOpenAIConfig)
        mock_validate.assert_called_once_with(
            ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"], "Azure OpenAI"
        )

    @patch("builtins.print")
    @patch("config.validate_required_env_vars")
    def test_from_env_with_ollama_false_invalid_config(self, mock_validate, mock_print):
        """Test from_env when using Azure OpenAI with invalid configuration."""
        app_config = MagicMock()
        app_config.use_ollama = False
        mock_validate.return_value = False
        
        config = AzureOpenAIConfig.from_env(app_config)
        assert isinstance(config, AzureOpenAIConfig)
        mock_validate.assert_called_once()
        mock_print.assert_called()


class TestAgentConfig:
    """Test AgentConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = AgentConfig()
            assert config.name == "SK-Assistant"
            assert config.instructions == "You are a helpful assistant."

    def test_custom_values_from_env(self):
        """Test configuration from environment variables."""
        env_vars = {
            "AGENT_NAME": "Custom-Agent",
            "AGENT_INSTRUCTIONS": "You are a specialized assistant for testing.",
        }
        with patch.dict(os.environ, env_vars):
            config = AgentConfig()
            assert config.name == "Custom-Agent"
            assert config.instructions == "You are a specialized assistant for testing."

    def test_from_env_class_method(self):
        """Test from_env class method."""
        config = AgentConfig.from_env()
        assert isinstance(config, AgentConfig) 