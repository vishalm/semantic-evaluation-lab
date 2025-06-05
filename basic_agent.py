# Basic Agent - Python

import asyncio
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion
from config import app_config, azure_config, ollama_config, agent_config


def create_agent():
    """
    Create and return a ChatCompletionAgent instance.
    This function is used by the load testing framework.
    """
    # Initialize AI service based on configuration
    if app_config.use_ollama:
        ai_service = OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
    else:
        ai_service = AzureChatCompletion(
            service_id=azure_config.service_id,
            api_key=azure_config.api_key,
            endpoint=azure_config.endpoint,
            deployment_name=azure_config.deployment_name,
            api_version=azure_config.api_version,
        )
    
    # Initialize a chat agent with configurable instructions
    agent = ChatCompletionAgent(
        service=ai_service,
        name=agent_config.name,
        instructions=agent_config.instructions,
    )
    
    # Add invoke and invoke_async methods for compatibility
    async def invoke_async(message: str):
        """Async invoke method for load testing compatibility."""
        response = await agent.get_response(messages=message)
        return response.content
    
    def invoke(message: str):
        """Sync invoke method for load testing compatibility."""
        return asyncio.run(invoke_async(message))
    
    # Attach methods to agent
    agent.invoke_async = invoke_async
    agent.invoke = invoke
    
    return agent


async def main():
    # Create agent using the factory function
    agent = create_agent()
    
    # Display configuration
    if app_config.use_ollama:
        print(f"🤖 Using Ollama model: {ollama_config.model_id}")
    else:
        print(f"☁️ Using Azure OpenAI deployment: {azure_config.deployment_name}")

    # Get a response to a user message
    print(f"🚀 Starting {agent_config.name}...")
    response = await agent.get_response(messages="Write a haiku about Semantic Kernel.")
    print("\n📝 Response:")
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())

# Example Output:
# Language's essence,
# Semantic threads intertwine,
# Meaning's core revealed.