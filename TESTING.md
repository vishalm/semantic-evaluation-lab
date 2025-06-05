# Testing Documentation

This document explains the comprehensive testing strategy and automatic test skipping behavior implemented in the Semantic Kernel Demo project.

## Test Categories

### 1. Unit Tests
- **Location**: `tests/unit/`
- **Purpose**: Test individual components in isolation
- **Requirements**: None (always runs)
- **Command**: `make test-unit`

### 2. Functional Tests  
- **Location**: `tests/functional/`
- **Purpose**: Test real integration with AI services
- **Requirements**: Either Ollama running OR OpenAI/Azure API key
- **Command**: `make test-functional`

### 3. LLM Evaluation Tests (DeepEval)
- **Location**: `tests/llm_evaluation/`
- **Purpose**: Evaluate LLM response quality using DeepEval framework
- **Requirements**: `OPENAI_API_KEY` environment variable
- **Command**: `make test-llm-eval`

## Automatic Test Skipping

The test suite automatically detects available services and skips tests when requirements are not met:

### Skip Scenarios

| Scenario | Unit Tests | Functional Tests | DeepEval Tests |
|----------|------------|------------------|----------------|
| No services configured | ✅ Run | ⚠️ Skip | ⚠️ Skip |
| Only Ollama available | ✅ Run | ✅ Run | ⚠️ Skip |
| Only OpenAI available | ✅ Run | ✅ Run | ✅ Run |
| All services available | ✅ Run | ✅ Run | ✅ Run |

### Skip Messages

When tests are skipped, you'll see clear messages:
```
SKIPPED [1] tests/functional/test_agents.py: Functional tests require either Ollama (use_ollama=True) or OpenAI API key
SKIPPED [1] tests/llm_evaluation/test_agent_responses.py: DeepEval tests require OpenAI API key (OPENAI_API_KEY environment variable)
```

## Environment Validation

### Automatic Validation
Every test run displays environment status:
```
============================================================
TEST ENVIRONMENT VALIDATION
============================================================
Ollama enabled: True
OpenAI API key: ✗
Azure OpenAI API key: ✗

⚠️  Note: DeepEval tests will be skipped (no OPENAI_API_KEY)
   - Functional tests will run with available service
   - Set OPENAI_API_KEY to enable DeepEval tests
============================================================
```

### Manual Validation
Check your environment before running tests:
```bash
# Quick environment check
make test-validate

# Detailed environment info
make env-check
```

## Running Tests

### Basic Commands
```bash
# Run all tests (with auto-skipping)
make test

# Run specific test categories
make test-unit           # Unit tests only
make test-functional     # Functional tests (may skip)
make test-llm-eval      # DeepEval tests (may skip)

# Validate environment first
make test-validate      # Check what will run
```

### Advanced Commands
```bash
# Run with coverage
make test-coverage

# Generate comprehensive reports
make test-reports

# CI mode testing
make ci-test
```

## Service Configuration

### Ollama Setup
```bash
# 1. Install and start Ollama
ollama serve

# 2. Pull required model
ollama pull qwen2.5:latest

# 3. Configure environment
export USE_OLLAMA=true
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL_ID=qwen2.5:latest
```

### OpenAI Setup
```bash
# Set API key for DeepEval tests
export OPENAI_API_KEY=your_openai_api_key_here
```

### Azure OpenAI Setup
```bash
# Set Azure credentials
export AZURE_OPENAI_API_KEY=your_azure_key
export AZURE_OPENAI_ENDPOINT=your_azure_endpoint
export AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

## CI/CD Integration

### Pipeline Behavior
The CI pipeline handles test skipping gracefully:

1. **Environment Detection**: Checks available services
2. **Conditional Execution**: Runs only applicable tests
3. **Graceful Failures**: Doesn't fail pipeline for missing optional services
4. **Clear Reporting**: Reports which tests ran vs. skipped

### Secrets Configuration
For full CI testing, configure these secrets:
- `OPENAI_API_KEY`: For DeepEval tests
- `AZURE_OPENAI_API_KEY`: For Azure testing (optional)
- `SONAR_TOKEN`: For code quality analysis (optional)

## Test Development Guidelines

### Adding New Tests

1. **Unit Tests**: Add to `tests/unit/` - no special requirements
2. **Functional Tests**: Add `@pytest.mark.asyncio` and use `skip_if_no_*` fixtures
3. **DeepEval Tests**: Use `if not os.getenv("OPENAI_API_KEY"): pytest.skip()`

### Example Functional Test
```python
import pytest
from config import app_config

@pytest.mark.asyncio
class TestMyFeature:
    async def test_ollama_integration(self):
        if not app_config.use_ollama:
            pytest.skip("Ollama not configured for use")
        
        # Your test code here
```

### Example DeepEval Test
```python
import os
import pytest
from deepeval.metrics import AnswerRelevancyMetric

def test_response_quality():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key required for DeepEval tests")
    
    # Your evaluation code here
```

## Troubleshooting

### Common Issues

**Tests Being Skipped Unexpectedly**
```bash
# Check configuration
make config-check

# Validate environment
make test-validate

# Check specific service
python -c "from config import app_config; print(f'Ollama: {app_config.use_ollama}')"
```

**Functional Tests Failing**
```bash
# Check Ollama is running
curl http://localhost:11434/api/version

# Check model availability
ollama list | grep qwen2.5

# Test basic connectivity
python -c "from semantic_kernel.connectors.ai.ollama import OllamaChatCompletion; print('OK')"
```

**DeepEval Tests Not Running**
```bash
# Check API key
echo $OPENAI_API_KEY

# Test DeepEval import
python -c "from deepeval.metrics import AnswerRelevancyMetric; print('OK')"
```

### Getting Help

1. Run `make test-validate` to see current environment status
2. Check the test output for specific skip reasons
3. Verify service configurations match your setup
4. Ensure required environment variables are set

## Performance Considerations

- **Unit tests**: Fast (< 10 seconds)
- **Functional tests**: Medium (30-60 seconds with Ollama)
- **DeepEval tests**: Slow (2-5 minutes with OpenAI API calls)

The automatic skipping ensures fast feedback when only some services are available. 