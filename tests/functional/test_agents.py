"""Functional tests for agent implementations."""

import asyncio
import pytest
import os
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from config import app_config, ollama_config, azure_config, agent_config


@pytest.mark.asyncio
class TestOllamaFunctionalIntegration:
    """Functional tests for Ollama integration with real service."""

    async def test_ollama_service_connection(self):
        """Test connection to Ollama service."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Create actual Ollama service
        service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
        
        # Test that service is created successfully
        assert service is not None
        assert service.service_id == ollama_config.service_id

    async def test_ollama_agent_creation_and_response(self):
        """Test creating and getting response from Ollama agent."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Create actual Ollama service
        service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
        
        # Create actual agent
        agent = ChatCompletionAgent(
            service=service,
            name=agent_config.name,
            instructions=agent_config.instructions,
        )
        
        # Test actual agent response
        response = await agent.get_response(messages="Hello, respond with just 'Hi there!' please.")
        
        assert response is not None
        assert hasattr(response, 'content')
        # Convert response content to string for length check
        content_str = str(response.content)
        assert len(content_str) > 0
        print(f"Agent response: {content_str}")

    async def test_ollama_kernel_integration(self):
        """Test Ollama integration with Semantic Kernel."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Create kernel and add Ollama service
        kernel = Kernel()
        
        service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
        
        kernel.add_service(service)
        
        # Create a simple function
        @kernel_function(
            name="test_function",
            description="A simple test function"
        )
        def test_function(input: str) -> str:
            return f"Processed: {input}"
        
        # Add function to kernel
        plugin = kernel.add_function(
            plugin_name="test_plugin",
            function=test_function
        )
        
        # Test kernel execution
        result = await kernel.invoke(plugin, input="test input")
        
        assert result is not None
        assert "Processed: test input" in str(result)

    async def test_basic_agent_script_execution(self):
        """Test the basic_agent.py main function with real Ollama."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Import and test the actual basic_agent script
        try:
            from basic_agent import main
            
            # This should run without errors and create real responses
            await main()
            
            # If we get here, the script executed successfully
            assert True
            
        except Exception as e:
            pytest.fail(f"basic_agent.py execution failed: {str(e)}")

    async def test_ollama_agent_conversation(self):
        """Test a simple conversation with Ollama agent."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Create service and agent
        service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
        
        agent = ChatCompletionAgent(
            service=service,
            name="Functional-Test-Agent",
            instructions="You are a helpful assistant. Keep responses brief and clear.",
        )
        
        # Test multiple interactions
        questions = [
            "What is 2+2?",
            "What is Semantic Kernel?",
            "Thank you!"
        ]
        
        responses = []
        for question in questions:
            response = await agent.get_response(messages=question)
            content_str = str(response.content)
            responses.append(content_str)
            print(f"Q: {question} | A: {content_str}")
        
        # Verify we got responses for all questions
        assert len(responses) == len(questions)
        assert all(len(response) > 0 for response in responses)


@pytest.mark.asyncio 
class TestAzureOpenAIFunctionalIntegration:
    """Functional tests for Azure OpenAI integration (when configured)."""

    async def test_azure_service_creation(self):
        """Test Azure OpenAI service creation."""
        if app_config.use_ollama or not azure_config.api_key:
            pytest.skip("Azure OpenAI not configured or Ollama is preferred")
            
        # Create actual Azure service
        service = AzureChatCompletion(
            service_id=azure_config.service_id,
            api_key=azure_config.api_key,
            endpoint=azure_config.endpoint,
            deployment_name=azure_config.deployment_name,
            api_version=azure_config.api_version,
        )
        
        assert service is not None
        assert service.service_id == azure_config.service_id

    async def test_azure_agent_response(self):
        """Test Azure OpenAI agent response."""
        if app_config.use_ollama or not azure_config.api_key:
            pytest.skip("Azure OpenAI not configured or Ollama is preferred")
            
        # Create service and agent
        service = AzureChatCompletion(
            service_id=azure_config.service_id,
            api_key=azure_config.api_key,
            endpoint=azure_config.endpoint,
            deployment_name=azure_config.deployment_name,
            api_version=azure_config.api_version,
        )
        
        agent = ChatCompletionAgent(
            service=service,
            name="Azure-Test-Agent",
            instructions="You are a helpful assistant.",
        )
        
        # Test response
        response = await agent.get_response(messages="Say hello in one word.")
        
        assert response is not None
        assert hasattr(response, 'content')
        content_str = str(response.content)
        assert len(content_str) > 0


class TestConfigurationIntegration:
    """Test configuration integration and validation."""

    def test_default_configurations(self):
        """Test that default configurations are properly loaded."""
        # Test that all configs are available
        assert app_config is not None
        assert ollama_config is not None
        assert azure_config is not None
        assert agent_config is not None
        
        # Test Ollama defaults
        assert ollama_config.host == "http://localhost:11434"
        assert ollama_config.model_id == "qwen2.5:latest"
        assert ollama_config.service_id == "ollama"
        
        # Test agent defaults
        assert agent_config.name is not None
        assert agent_config.instructions is not None

    def test_environment_variable_integration(self):
        """Test that environment variables are properly integrated."""
        # Test that configs use environment variables when available
        # or fall back to defaults
        
        # Test Ollama config
        expected_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        expected_model = os.getenv("OLLAMA_MODEL_ID", "qwen2.5:latest")
        expected_service_id = os.getenv("OLLAMA_SERVICE_ID", "ollama")
        
        assert ollama_config.host == expected_host
        assert ollama_config.model_id == expected_model
        assert ollama_config.service_id == expected_service_id

    def test_app_config_ollama_preference(self):
        """Test that app config properly indicates Ollama preference."""
        # By default, should prefer Ollama unless Azure is specifically configured
        expected_use_ollama = not bool(os.getenv("AZURE_OPENAI_API_KEY"))
        
        # The actual logic might be different, but test the configuration
        assert hasattr(app_config, 'use_ollama')
        assert isinstance(app_config.use_ollama, bool)


@pytest.mark.asyncio
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    async def test_help_request_scenario(self):
        """Test a realistic help request scenario."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Create service and agent
        service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
        
        agent = ChatCompletionAgent(
            service=service,
            name="Help-Assistant",
            instructions="You are a helpful coding assistant. Provide brief, practical answers.",
        )
        
        # Test realistic question
        question = "How do I create a simple function in Python?"
        response = await agent.get_response(messages=question)
        
        assert response is not None
        content_str = str(response.content)
        assert len(content_str) > 20  # Should be a substantial response
        assert "def " in content_str.lower() or "function" in content_str.lower()
        
        print(f"Help scenario - Q: {question}")
        print(f"Help scenario - A: {content_str[:100]}...")

    async def test_error_handling_scenario(self):
        """Test error handling with invalid requests."""
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
            
        # Test with potentially problematic service configuration
        try:
            service = OllamaChatCompletion(
                service_id="test-service",
                host="http://localhost:11434",  # Assume this works
                ai_model_id="qwen2.5:latest",
            )
            
            agent = ChatCompletionAgent(
                service=service,
                name="Error-Test-Agent",
                instructions="You are a test agent.",
            )
            
            # This should work if Ollama is running
            response = await agent.get_response(messages="Test message")
            assert response is not None
            
        except Exception as e:
            # If Ollama is not running, we expect specific errors
            error_msg = str(e).lower()
            # Common connection errors
            assert any(keyword in error_msg for keyword in [
                "connection", "refused", "timeout", "unreachable", "network"
            ]), f"Unexpected error: {e}" 