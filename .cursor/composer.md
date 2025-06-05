# Semantic Kernel Learning Project - Composer Configuration

## 🎯 Project-Specific Guidelines for Cursor Composer

### Core Principles
This is a learning project focused on Microsoft Semantic Kernel with dual AI provider support (Ollama + Azure OpenAI). All code should be educational, well-documented, and production-ready.

### Configuration Management Rules
- **NEVER hardcode** API keys, endpoints, or model names
- **ALWAYS use** the existing config classes: `app_config`, `azure_config`, `ollama_config`, `agent_config`
- **VALIDATE** environment variables before use with helpful error messages
- **SUPPORT both** Ollama (local) and Azure OpenAI (cloud) providers seamlessly

### Code Patterns to Follow

#### Import Structure
```python
# Standard library
import asyncio
import os

# Third-party
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent

# Local configuration
from config import app_config, azure_config, ollama_config, agent_config
```

#### Provider-Agnostic Implementation
```python
if app_config.use_ollama:
    service = OllamaChatCompletion(
        service_id=ollama_config.service_id,
        host=ollama_config.host,
        ai_model_id=ollama_config.model_id,
    )
else:
    service = AzureChatCompletion(
        service_id=azure_config.service_id,
        api_key=azure_config.api_key,
        endpoint=azure_config.endpoint,
        deployment_name=azure_config.deployment_name,
    )
```

#### Error Handling Standard
```python
try:
    result = await service.call()
except Exception as e:
    print(f"❌ Error: {e}")
    print("💡 Solution: Check your configuration")
    return None
```

### File Modification Guidelines

#### When editing `config.py`:
- Add new configuration classes following the existing pattern
- Always provide sensible defaults
- Include validation logic with helpful error messages
- Update global config instances at the bottom

#### When editing `basic_agent.py`:
- Maintain compatibility with both providers
- Add informative console output
- Use proper async/await patterns
- Include error handling

#### When adding new files:
- Follow the snake_case naming convention
- Include proper imports and type hints
- Add docstrings for classes and functions
- Test with both Ollama and Azure OpenAI

#### When updating documentation:
- Update README.md for user-facing changes
- Update env.example for new environment variables
- Include Mermaid diagrams for complex flows
- Add usage examples

### Code Quality Standards

#### Python Style:
- Use type hints for all function parameters and return types
- Maximum line length: 88 characters
- Use f-strings for string formatting
- Prefer descriptive variable names over comments

#### Async Programming:
- All AI operations must be async
- Use `asyncio.run(main())` for script entry points
- Handle async exceptions properly
- Don't mix sync and async code

#### Error Messages:
- Use emojis for visual clarity: ❌ ⚠️ 💡 ✅ 🔧 📝
- Provide actionable solutions
- Include configuration hints
- Reference documentation when helpful

### Security Requirements

#### Environment Variables:
- All sensitive data must use environment variables
- Never commit API keys or credentials
- Validate and sanitize all inputs
- Don't log sensitive information

#### Default Configuration:
- Default to Ollama (local) for security
- Require explicit opt-in for cloud services
- Provide clear security warnings for cloud usage

### Testing Considerations

#### Both Providers:
- Test all features with Ollama and Azure OpenAI
- Validate configuration error handling
- Check environment variable validation
- Verify async operations work correctly

#### Configuration Scenarios:
- Missing environment variables
- Invalid provider settings
- Service connectivity issues
- Mixed sync/async operations

### Documentation Standards

#### Code Comments:
- Explain complex business logic
- Document async operation patterns
- Clarify provider-specific differences
- Include usage examples

#### README Updates:
- Update installation instructions
- Add new configuration options
- Include troubleshooting guides
- Update Mermaid diagrams

### Performance Guidelines

#### Async Operations:
- Use connection pooling when available
- Implement proper timeout handling
- Handle rate limiting gracefully
- Cache expensive operations when appropriate

#### Resource Management:
- Close connections properly
- Handle memory efficiently
- Use appropriate logging levels
- Monitor service health

### Debugging Support

#### Common Issues:
- Configuration validation failures
- Provider service connectivity
- Async/await pattern problems
- Environment variable formatting

#### Helpful Patterns:
- Add debug logging with levels
- Include service health checks
- Provide configuration dump functionality
- Add connectivity test utilities

Remember: This is a learning project, so prioritize code clarity and educational value over performance optimization. Every feature should help developers understand Semantic Kernel concepts and best practices. 