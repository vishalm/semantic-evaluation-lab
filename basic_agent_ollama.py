import asyncio
from semantic_kernel import Kernel
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion
from semantic_kernel.connectors.ai.ollama.ollama_prompt_execution_settings import (
    OllamaChatPromptExecutionSettings,
)
from config import app_config, ollama_config

async def main():
    # Check if Ollama is configured
    if not app_config.use_ollama:
        print("⚠️  This script requires USE_OLLAMA=true in your .env file")
        print("💡 Set USE_OLLAMA=true to use this Ollama-specific implementation")
        return
    
    print(f"🤖 Using Ollama model: {ollama_config.model_id} at {ollama_config.host}")
    
    kernel = Kernel()

    # Use configuration instead of hardcoded values
    kernel.add_service(
        OllamaChatCompletion(
            service_id=ollama_config.service_id,
            host=ollama_config.host,
            ai_model_id=ollama_config.model_id,
        )
    )
    execution_settings = OllamaChatPromptExecutionSettings()

    prompt = """
1) A robot may not injure a human being or, through inaction,
allow a human being to come to harm.

2) A robot must obey orders given it by human beings except where
such orders would conflict with the First Law.

3) A robot must protect its own existence as long as such protection
does not conflict with the First or Second Law.

Give me the TLDR in exactly 5 words."""

    prompt_template_config = PromptTemplateConfig(
        template=prompt, name="tldr", template_format="semantic-kernel"
    )

    function = kernel.add_function(
        function_name="tldr_function",
        plugin_name="tldr_plugin",
        prompt_template_config=prompt_template_config,
        prompt_execution_settings=execution_settings,
    )

    # Run your prompt
    print("🚀 Processing Asimov's Laws of Robotics...")
    result = await kernel.invoke(function)
    print("\n📝 TLDR Response:")
    print(result)  # => Robots must not harm humans.

if __name__ == "__main__":
    asyncio.run(main())