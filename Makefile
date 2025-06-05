# Semantic Evaluation Lab - Makefile
.PHONY: help install test lint format clean coverage security docs

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ===============================================================================
# LAB AUTOMATION COMMANDS (NEW!)
# ===============================================================================

lab-start: ## 🧪 Start complete Semantic Evaluation Lab with automation
	@echo "🧪 Starting Semantic Evaluation Lab with automation..."
	@echo "Configuration from .env file:"
	@echo "  LAB_NAME: $${LAB_NAME:-Semantic-Evaluation-Lab}"
	@echo "  LAB_ENVIRONMENT: $${LAB_ENVIRONMENT:-development}"
	@echo "  AUTO_RUN_TESTS: $${AUTO_RUN_TESTS:-false}"
	@echo "  AUTO_SETUP_MODELS: $${AUTO_SETUP_MODELS:-true}"
	@echo ""
	docker-compose --profile dev --profile auto-tests --profile monitoring up -d

lab-start-full: ## 🚀 Start lab with all automation enabled
	@echo "🚀 Starting full automation lab..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true ENABLE_MONITORING=true docker-compose --profile dev --profile auto-tests --profile monitoring --profile load-test up -d

lab-start-minimal: ## ⚡ Start minimal lab (basic functionality only)
	@echo "⚡ Starting minimal lab..."
	AUTO_RUN_TESTS=false ENABLE_MONITORING=false docker-compose --profile dev up -d

lab-start-testing: ## 🧪 Start lab optimized for testing
	@echo "🧪 Starting testing-optimized lab..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_GENERATE_REPORTS=true docker-compose --profile dev --profile auto-tests up -d

lab-start-load-testing: ## 🔥 Start lab optimized for load testing
	@echo "🔥 Starting load testing lab..."
	AUTO_RUN_LOAD_TESTS=true ENABLE_MONITORING=true docker-compose --profile dev --profile load-test --profile monitoring up -d

lab-stop: ## 🛑 Stop all lab services
	@echo "🛑 Stopping Semantic Evaluation Lab..."
	docker-compose --profile all down

lab-restart: ## 🔄 Restart lab with current configuration
	@echo "🔄 Restarting lab..."
	$(MAKE) lab-stop
	sleep 2
	$(MAKE) lab-start

lab-status: ## 📊 Show lab status and configuration
	@echo "📊 Semantic Evaluation Lab Status"
	@echo "================================="
	@echo "Services:"
	@docker-compose ps
	@echo ""
	@echo "Configuration:"
	@echo "  LAB_NAME: $${LAB_NAME:-Semantic-Evaluation-Lab}"
	@echo "  LAB_ENVIRONMENT: $${LAB_ENVIRONMENT:-development}"
	@echo "  AUTO_RUN_TESTS: $${AUTO_RUN_TESTS:-false}"
	@echo "  ENABLE_MONITORING: $${ENABLE_MONITORING:-true}"
	@echo "  USE_OLLAMA: $${USE_OLLAMA:-true}"
	@echo ""
	@echo "Access Points:"
	@echo "  - Grafana Dashboard: http://localhost:$${GRAFANA_PORT:-3000}"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Locust Load Testing: http://localhost:8089"
	@echo "  - Metrics Exporter: http://localhost:$${PROMETHEUS_PORT:-8000}/metrics"

lab-health: ## 🏥 Check lab health status
	@echo "🏥 Checking lab health..."
	@if docker-compose ps | grep -q "semantic-evaluation-lab"; then \
		echo "✅ Lab services are running"; \
	else \
		echo "❌ Lab services are not running"; \
	fi
	@echo ""
	@echo "Service Health Checks:"
	@curl -f http://localhost:$${OLLAMA_HOST#http://localhost:}/api/tags >/dev/null 2>&1 && echo "✅ Ollama: Healthy" || echo "❌ Ollama: Unhealthy"
	@curl -f http://localhost:$${PROMETHEUS_PORT:-8000}/metrics >/dev/null 2>&1 && echo "✅ Metrics Exporter: Healthy" || echo "❌ Metrics Exporter: Unhealthy"
	@curl -f http://localhost:9090/-/healthy >/dev/null 2>&1 && echo "✅ Prometheus: Healthy" || echo "❌ Prometheus: Unhealthy"
	@curl -f http://localhost:$${GRAFANA_PORT:-3000}/api/health >/dev/null 2>&1 && echo "✅ Grafana: Healthy" || echo "❌ Grafana: Unhealthy"

# ===============================================================================
# AUTO-TEST COMMANDS (NEW!)
# ===============================================================================

auto-test-setup: ## ⚙️ Setup environment for auto-testing
	@echo "⚙️ Setting up auto-testing environment..."
	@mkdir -p logs test-reports htmlcov .deepeval_cache
	@echo "Checking configuration..."
	@if [ -z "$${OPENAI_API_KEY}" ] && [ "$${AUTO_RUN_LLM_EVAL_TESTS}" = "true" ]; then \
		echo "⚠️  Warning: OPENAI_API_KEY not set but LLM evaluation tests are enabled"; \
	fi
	@echo "✅ Auto-test setup completed"

auto-test-run: ## 🤖 Run automated test suite based on configuration
	@echo "🤖 Running automated tests..."
	docker-compose --profile auto-tests up --abort-on-container-exit

auto-test-unit: ## 📝 Auto-run unit tests only
	@echo "📝 Running automated unit tests..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=false AUTO_RUN_LLM_EVAL_TESTS=false docker-compose run --rm auto-test-orchestrator

auto-test-functional: ## ⚙️ Auto-run functional tests only
	@echo "⚙️ Running automated functional tests..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=false AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_RUN_LLM_EVAL_TESTS=false docker-compose run --rm auto-test-orchestrator

auto-test-llm-eval: ## 🔬 Auto-run LLM evaluation tests only
	@echo "🔬 Running automated LLM evaluation tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "❌ Error: OPENAI_API_KEY required for LLM evaluation tests"; \
		exit 1; \
	fi
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=false AUTO_RUN_FUNCTIONAL_TESTS=false AUTO_RUN_LLM_EVAL_TESTS=true docker-compose run --rm auto-test-orchestrator

auto-test-conversations: ## 🗣️ Auto-run conversation chain tests
	@echo "🗣️ Running automated conversation tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "❌ Error: OPENAI_API_KEY required for conversation tests"; \
		exit 1; \
	fi
	AUTO_RUN_TESTS=true AUTO_RUN_CONVERSATION_TESTS=true docker-compose run --rm auto-test-orchestrator

auto-test-all: ## 🎯 Auto-run all test suites
	@echo "🎯 Running all automated tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "⚠️  Warning: OPENAI_API_KEY not set, skipping LLM evaluation tests"; \
		AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true docker-compose run --rm auto-test-orchestrator; \
	else \
		AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_RUN_LLM_EVAL_TESTS=true AUTO_RUN_CONVERSATION_TESTS=true docker-compose run --rm auto-test-orchestrator; \
	fi

auto-test-reports: ## 📊 Generate comprehensive auto-test reports
	@echo "📊 Generating auto-test reports..."
	@if [ -f "test-reports/auto-test-summary.json" ]; then \
		echo "Auto-test summary:"; \
		cat test-reports/auto-test-summary.json | python -m json.tool; \
	else \
		echo "No auto-test summary found. Run auto-test-run first."; \
	fi

# ===============================================================================
# AUTO-LOAD TESTING COMMANDS (NEW!)
# ===============================================================================

auto-load-test-light: ## ⚡ Auto-run light load test (1 user, 2 min)
	@echo "⚡ Running automated light load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=1 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=120s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-medium: ## 🔥 Auto-run medium load test (3 users, 5 min)
	@echo "🔥 Running automated medium load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=3 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-heavy: ## 🚀 Auto-run heavy load test (5 users, 10 min)
	@echo "🚀 Running automated heavy load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=5 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=600s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-conversation: ## 🗣️ Auto-run conversation-focused load test
	@echo "🗣️ Running automated conversation load test..."
	AUTO_RUN_LOAD_TESTS=true docker-compose --profile load-test-conversation up --abort-on-container-exit

# ===============================================================================
# CONFIGURATION MANAGEMENT (NEW!)
# ===============================================================================

config-check: ## 🔍 Check configuration and environment
	@echo "🔍 Checking Semantic Evaluation Lab configuration..."
	@echo ""
	@echo "=== Environment Variables ==="
	@echo "Core Configuration:"
	@echo "  LAB_NAME: $${LAB_NAME:-Semantic-Evaluation-Lab}"
	@echo "  LAB_ENVIRONMENT: $${LAB_ENVIRONMENT:-development}"
	@echo "  LAB_VERSION: $${LAB_VERSION:-1.0.0}"
	@echo "  USE_OLLAMA: $${USE_OLLAMA:-true}"
	@echo ""
	@echo "Automation Settings:"
	@echo "  AUTO_RUN_TESTS: $${AUTO_RUN_TESTS:-false}"
	@echo "  AUTO_RUN_UNIT_TESTS: $${AUTO_RUN_UNIT_TESTS:-true}"
	@echo "  AUTO_RUN_FUNCTIONAL_TESTS: $${AUTO_RUN_FUNCTIONAL_TESTS:-false}"
	@echo "  AUTO_RUN_LLM_EVAL_TESTS: $${AUTO_RUN_LLM_EVAL_TESTS:-false}"
	@echo "  AUTO_SETUP_MODELS: $${AUTO_SETUP_MODELS:-true}"
	@echo ""
	@echo "Monitoring Settings:"
	@echo "  ENABLE_MONITORING: $${ENABLE_MONITORING:-true}"
	@echo "  PROMETHEUS_PORT: $${PROMETHEUS_PORT:-8000}"
	@echo "  GRAFANA_PORT: $${GRAFANA_PORT:-3000}"
	@echo ""
	@echo "Load Testing Settings:"
	@echo "  LOCUST_USERS: $${LOCUST_USERS:-1}"
	@echo "  LOCUST_SPAWN_RATE: $${LOCUST_SPAWN_RATE:-1}"
	@echo "  LOCUST_RUN_TIME: $${LOCUST_RUN_TIME:-300s}"
	@echo ""
	@echo "=== Validation ==="
	@if [ -f ".env" ]; then \
		echo "✅ .env file exists"; \
	else \
		echo "⚠️  .env file not found (using defaults)"; \
	fi
	@if [ -n "$${OPENAI_API_KEY}" ]; then \
		echo "✅ OPENAI_API_KEY is set"; \
	else \
		echo "⚠️  OPENAI_API_KEY not set (LLM evaluation tests will be skipped)"; \
	fi

config-generate: ## 📝 Generate configuration files from templates
	@echo "📝 Generating configuration files..."
	@if [ ! -f ".env" ]; then \
		cp env.example .env; \
		echo "✅ Created .env file from env.example"; \
		echo "Please edit .env file with your configuration"; \
	else \
		echo "⚠️  .env file already exists"; \
	fi

config-validate: ## ✅ Validate current configuration
	@echo "✅ Validating configuration..."
	docker-compose config > /dev/null && echo "✅ Docker Compose configuration is valid" || echo "❌ Docker Compose configuration has errors"

config-example-quick-start: ## 🚀 Generate quick start configuration
	@echo "🚀 Generating quick start configuration..."
	@cat > .env.quickstart << 'EOF'
# Quick Start Configuration
LAB_ENVIRONMENT=development
AUTO_RUN_TESTS=true
AUTO_RUN_UNIT_TESTS=true
AUTO_RUN_FUNCTIONAL_TESTS=true
AUTO_SETUP_MODELS=true
ENABLE_MONITORING=true
LOCUST_USERS=1
LOCUST_RUN_TIME=120s
EOF
	@echo "✅ Quick start configuration saved to .env.quickstart"
	@echo "To use: mv .env.quickstart .env"

config-example-full-eval: ## 🔬 Generate full evaluation configuration
	@echo "🔬 Generating full evaluation configuration..."
	@cat > .env.fulleval << 'EOF'
# Full Evaluation Configuration
LAB_ENVIRONMENT=evaluation
AUTO_RUN_TESTS=true
AUTO_RUN_UNIT_TESTS=true
AUTO_RUN_FUNCTIONAL_TESTS=true
AUTO_RUN_LLM_EVAL_TESTS=true
AUTO_RUN_CONVERSATION_TESTS=true
ENABLE_CONVERSATION_STABILITY_TESTS=true
ENABLE_DYNAMIC_CONVERSATION_TESTS=true
CONVERSATION_CHAIN_LENGTHS=5,10,15,20
ENABLE_MONITORING=true
ENABLE_NOTIFICATIONS=true
LOCUST_USERS=3
LOCUST_RUN_TIME=300s
# Remember to set OPENAI_API_KEY=your-key-here
EOF
	@echo "✅ Full evaluation configuration saved to .env.fulleval"
	@echo "To use: mv .env.fulleval .env and add your OPENAI_API_KEY"

# ===============================================================================
# MONITORING AUTOMATION (NEW!)
# ===============================================================================

monitoring-auto-start: ## 📊 Auto-start monitoring with optimal settings
	@echo "📊 Starting automated monitoring..."
	ENABLE_MONITORING=true ENABLE_ALERTING=true docker-compose --profile monitoring up -d

monitoring-health-check: ## 🏥 Automated monitoring health check
	@echo "🏥 Checking monitoring health..."
	@curl -f http://localhost:9090/-/healthy >/dev/null 2>&1 && echo "✅ Prometheus: Healthy" || echo "❌ Prometheus: Unhealthy"
	@curl -f http://localhost:$${GRAFANA_PORT:-3000}/api/health >/dev/null 2>&1 && echo "✅ Grafana: Healthy" || echo "❌ Grafana: Unhealthy"
	@curl -f http://localhost:$${PROMETHEUS_PORT:-8000}/metrics >/dev/null 2>&1 && echo "✅ Metrics Exporter: Healthy" || echo "❌ Metrics Exporter: Unhealthy"

# ===============================================================================
# QUICK ALIASES (NEW!)
# ===============================================================================

ls: lab-start ## 🧪 Alias for lab-start
lsf: lab-start-full ## 🚀 Alias for lab-start-full
lst: lab-start-testing ## 🧪 Alias for lab-start-testing
lsl: lab-start-load-testing ## 🔥 Alias for lab-start-load-testing
lx: lab-stop ## 🛑 Alias for lab-stop
lr: lab-restart ## 🔄 Alias for lab-restart
lh: lab-health ## 🏥 Alias for lab-health
cc: config-check ## 🔍 Alias for config-check
at: auto-test-run ## 🤖 Alias for auto-test-run
ata: auto-test-all ## 🎯 Alias for auto-test-all

# ===============================================================================
# DEVELOPMENT ENVIRONMENT MANAGEMENT
# ===============================================================================

lab-logs: ## 📋 Show lab service logs
	@echo "📋 Showing lab service logs..."
	docker-compose logs -f --tail=50

lab-logs-app: ## 📋 Show application logs only
	docker-compose logs -f app

lab-logs-tests: ## 📋 Show test orchestrator logs
	docker-compose logs -f auto-test-orchestrator

lab-logs-monitoring: ## 📋 Show monitoring service logs
	docker-compose logs -f prometheus grafana metrics-exporter

lab-shell: ## 🖥️ Open shell in lab container
	docker-compose exec app bash

lab-clean: ## 🧹 Clean lab data and reports
	@echo "🧹 Cleaning lab data..."
	rm -rf logs/* test-reports/* htmlcov/* .deepeval_cache/*
	@echo "✅ Lab data cleaned"

lab-reset: ## 🔄 Reset lab to initial state
	@echo "🔄 Resetting lab..."
	$(MAKE) lab-stop
	$(MAKE) lab-clean
	docker-compose down -v
	docker system prune -f
	@echo "✅ Lab reset completed"

# ===============================================================================
# EXISTING COMMANDS (Updated)
# ===============================================================================

# Installation and setup
install: ## Install dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e ".[dev,test]"

# Testing
test: ## Run all tests (auto-skips if services unavailable)
	@echo "Running all tests with automatic service detection..."
	@echo "Tests will be automatically skipped if required services are unavailable."
	pytest

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-functional: ## Run functional tests only (skipped if no Ollama/OpenAI)
	@echo "Running functional tests..."
	@echo "These tests require either Ollama (use_ollama=True) or OpenAI API key."
	pytest tests/functional/ -v

test-llm-eval: ## Run LLM evaluation tests using DeepEval (Ollama or OpenAI)
	@echo "Running LLM evaluation tests..."
	@echo "These tests will use Ollama if available, or OpenAI API key as fallback."
	pytest tests/llm_evaluation/ -v -m "llm_eval or deepeval"

test-llm-eval-ollama: ## Run LLM evaluation tests specifically with Ollama
	@echo "Running LLM evaluation tests with Ollama..."
	@echo "This requires Ollama to be running with qwen2.5:latest model."
	USE_OLLAMA=true pytest tests/llm_evaluation/ -v -m "llm_eval or deepeval"

test-llm-eval-openai: ## Run LLM evaluation tests specifically with OpenAI
	@echo "Running LLM evaluation tests with OpenAI..."
	@echo "This requires OPENAI_API_KEY environment variable."
	USE_OLLAMA=false pytest tests/llm_evaluation/ -v -m "llm_eval or deepeval"

test-deepeval: ## Run DeepEval tests with CLI (Ollama or OpenAI)
	@echo "Running DeepEval CLI tests..."
	@echo "This will use Ollama if available, or OpenAI API key as fallback."
	deepeval test run tests/llm_evaluation/test_agent_responses.py --verbose

test-deepeval-ollama: ## Run DeepEval tests specifically with Ollama CLI
	@echo "Running DeepEval CLI tests with Ollama..."
	@echo "This requires Ollama to be running with qwen2.5:latest model."
	USE_OLLAMA=true deepeval test run tests/llm_evaluation/test_agent_responses.py --verbose

test-coverage: ## Run tests with coverage report
	pytest --cov=. --cov-report=html --cov-report=term-missing

test-coverage-xml: ## Run tests with XML coverage report (for CI)
	pytest --cov=. --cov-report=xml --cov-report=term-missing

test-reports: ## Generate comprehensive test reports
	pytest --cov=. --cov-report=html --cov-report=term-missing --junitxml=test-results.xml --html=test-report.html --self-contained-html

# Test environment validation
test-env-check: ## Check test environment and show which tests will run
	@echo "Checking test environment..."
	@python -c "import pytest; pytest.main(['-v', '--collect-only', '--quiet', 'tests/'])" 2>/dev/null | grep -E "(SKIP|collected|session starts)" || echo "Running test environment validation..."
	@python -c "from tests.conftest import *; import pytest; pytest.main(['--version'])" > /dev/null 2>&1 || echo "✅ Configuration loaded"

test-validate: ## Validate test environment with detailed output
	@echo "=== TEST ENVIRONMENT VALIDATION ==="
	@python -c "from config import app_config; import os; print(f'Ollama enabled: {app_config.use_ollama}'); print(f'OpenAI API key: {\"✓\" if os.getenv(\"OPENAI_API_KEY\") else \"✗\"}'); print(f'Azure API key: {\"✓\" if os.getenv(\"AZURE_OPENAI_API_KEY\") else \"✗\"}')"
	@echo "=== EXPECTED TEST BEHAVIOR ==="
	@python -c "from config import app_config; import os; has_ollama = app_config.use_ollama; has_openai = bool(os.getenv('OPENAI_API_KEY')); has_azure = bool(os.getenv('AZURE_OPENAI_API_KEY')); has_deepeval = has_ollama or has_openai; print(f'Unit tests: ✓ Will run'); print(f'Functional tests: {\"✓ Will run\" if (has_ollama or has_openai or has_azure) else \"⚠️  Will be SKIPPED (no AI service)\"}'); print(f'DeepEval tests: {\"✓ Will run (\" + (\"Ollama\" if has_ollama else \"OpenAI\") + \")\" if has_deepeval else \"⚠️  Will be SKIPPED (need Ollama or OPENAI_API_KEY)\"}')"

# Code quality
lint: ## Run linting checks
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

type-check: ## Run type checking
	mypy . --ignore-missing-imports --exclude venv --exclude .venv

security: ## Run security analysis
	bandit -r . --exclude ./venv,./tests,./.venv

# Code formatting
format: ## Format code with black and isort
	black .
	isort .

format-check: ## Check code formatting without modifying files
	black --check --diff .
	isort --check-only --diff .

# Quality gates (used in CI)
quality-check: format-check lint type-check security ## Run all quality checks

# Project management
clean: ## Clean up generated files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf test-results.xml
	rm -rf *-test-results.xml
	rm -rf test-report.html
	rm -rf *-test-report.html
	rm -rf bandit-report.json
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Running the application
run-ollama: ## Run with Ollama configuration
	USE_OLLAMA=true python basic_agent.py

run-azure: ## Run with Azure OpenAI configuration  
	USE_OLLAMA=false python basic_agent.py

run-ollama-script: ## Run the Ollama-specific script
	python basic_agent_ollama.py

# DeepEval specific commands
deepeval-login: ## Login to Confident AI platform
	@echo "Run: deepeval login"
	@echo "Follow the instructions to connect to Confident AI platform"

deepeval-dashboard: ## Open DeepEval dashboard (after login)
	@echo "Run tests with: make test-deepeval"
	@echo "Then check the dashboard link in the output"

# Development helpers
dev-setup: ## Set up development environment
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # Linux/Mac"
	@echo "  venv\\Scripts\\activate     # Windows"
	@echo "Then run: make install-dev"

config-check: ## Check configuration loading
	@echo "Testing configuration..."
	python -c "from config import app_config, ollama_config, azure_config; print(f'✅ Config loaded: Ollama={app_config.use_ollama}')"

deepeval-check: ## Check DeepEval installation and setup
	@echo "Testing DeepEval integration..."
	python -c "from deepeval.test_case import LLMTestCase; from deepeval.metrics import AnswerRelevancyMetric; print('✅ DeepEval imported successfully')"
	@echo "DeepEval version:"
	python -c "import deepeval; print(f'DeepEval: {deepeval.__version__ if hasattr(deepeval, \"__version__\") else \"version not found\"}')"

# CI/CD helpers
ci-install: ## Install dependencies for CI
	pip install --upgrade pip
	pip install -r requirements.txt

ci-test: ## Run tests in CI mode (with environment validation)
	@echo "CI Test Mode - Validating environment first..."
	@make test-validate
	pytest tests/ -v --cov=. --cov-report=xml --cov-report=term-missing --junitxml=test-results.xml

ci-test-llm: ## Run LLM evaluation tests in CI mode
	@echo "CI LLM Evaluation Mode..."
	pytest tests/llm_evaluation/ -v -m "llm_eval or deepeval" --junitxml=llm-eval-results.xml --html=llm-eval-report.html --self-contained-html

ci-quality: ## Run quality checks for CI
	black --check .
	isort --check-only .
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	mypy . --ignore-missing-imports --exclude venv --exclude .venv
	bandit -r . -f json -o bandit-report.json --exclude ./venv,./tests,./.venv || true

# Documentation
docs: ## Generate documentation (placeholder)
	@echo "Documentation generation would go here"
	@echo "Consider adding sphinx or mkdocs for documentation"

# Version management
version: ## Show current version
	@echo "Semantic Evaluation Lab - End-to-End AI Evaluation & Observability"
	@echo "Repository: https://github.com/vishalm/semantic-evaluation-lab"
	@echo "Python version: $(shell python --version)"
	@echo "Pip version: $(shell pip --version)"
	@echo "DeepEval integration: ✅"
	@echo "Locust load testing: ✅"
	@echo "Monitoring stack: ✅"

# Environment helpers
env-copy: ## Copy env.example to .env
	cp env.example .env
	@echo "✅ Copied env.example to .env"
	@echo "Please edit .env with your configuration"
	@echo "For DeepEval metrics, set OPENAI_API_KEY"

env-check: ## Check environment variables
	@echo "Current environment configuration:"
	@python -c "import os; print(f'USE_OLLAMA: {os.getenv(\"USE_OLLAMA\", \"not set\")}')"
	@python -c "import os; print(f'OLLAMA_HOST: {os.getenv(\"OLLAMA_HOST\", \"not set\")}')"
	@python -c "import os; print(f'AGENT_NAME: {os.getenv(\"AGENT_NAME\", \"not set\")}')"
	@python -c "import os; print(f'OPENAI_API_KEY: {\"set\" if os.getenv(\"OPENAI_API_KEY\") else \"not set (required for DeepEval)\"}')"

# LLM Evaluation workflows
eval-agent-quality: ## Evaluate agent response quality
	pytest tests/llm_evaluation/test_agent_responses.py::TestAgentResponseQuality -v

eval-agent-workflow: ## Evaluate complete agent workflows
	pytest tests/llm_evaluation/test_agent_responses.py::TestAgentWorkflowEvaluation -v

eval-dataset: ## Evaluate using dataset approach
	pytest tests/llm_evaluation/test_agent_responses.py::TestDatasetEvaluation -v

eval-integration: ## Test DeepEval integration features
	pytest tests/llm_evaluation/test_deepeval_integration.py -v

# Test conversation chains with different lengths
test-conversation-chains: test-validate
	@echo "🔄 Running conversation chain evaluation tests..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short -m "llm_eval and deepeval"

test-conversation-chains-ollama: test-validate
	@echo "🔄 Running conversation chain tests with Ollama..."
	@if [ "$(shell python -c 'import requests; print(requests.get("http://localhost:11434/api/tags").status_code)' 2>/dev/null)" = "200" ]; then \
		mkdir -p logs test-reports && \
		PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short -m "llm_eval and deepeval" --json-report --json-report-file=test-reports/conversation_chains_report.json; \
	else \
		echo "❌ Ollama not available. Please start Ollama service."; \
		exit 1; \
	fi

test-conversation-chains-with-metrics: test-validate
	@echo "🔄 Running conversation chain tests with metrics collection..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -c "from logging_config import configure_logging; configure_logging()"
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short --json-report --json-report-file=test-reports/conversation_chains_detailed.json
	@echo "📊 Metrics saved to test-reports/"

# Test specific chain lengths
test-chain-5: test-validate
	@echo "🔄 Testing 5-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[5] -v

test-chain-10: test-validate
	@echo "🔄 Testing 10-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[10] -v

test-chain-15: test-validate
	@echo "🔄 Testing 15-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[15] -v

test-chain-20: test-validate
	@echo "🔄 Testing 20-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[20] -v

# Dynamic conversation chain tests (NEW!)
test-dynamic-conversations: test-validate
	@echo "🔄 Running dynamic conversation chain tests..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short -m "llm_eval and deepeval"

test-dynamic-conversations-ollama: test-validate
	@echo "🔄 Running dynamic conversation tests with Ollama..."
	@if [ "$(shell python -c 'import requests; print(requests.get("http://localhost:11434/api/tags").status_code)' 2>/dev/null)" = "200" ]; then \
		mkdir -p logs test-reports && \
		PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short -m "llm_eval and deepeval" --json-report --json-report-file=test-reports/dynamic_conversations_report.json; \
	else \
		echo "❌ Ollama not available. Please start Ollama service."; \
		exit 1; \
	fi

# Test specific dynamic conversation lengths (separate tests for each)
test-dynamic-5: test-validate
	@echo "🔄 Testing 5-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_5_turn_dynamic_conversation -v

test-dynamic-10: test-validate
	@echo "🔄 Testing 10-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_10_turn_dynamic_conversation -v

test-dynamic-15: test-validate
	@echo "🔄 Testing 15-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_15_turn_dynamic_conversation -v

test-dynamic-20: test-validate
	@echo "🔄 Testing 20-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_20_turn_dynamic_conversation -v

# Compare original vs dynamic conversation approaches
test-conversation-comparison: test-validate
	@echo "🔄 Running comparison between original and dynamic conversation approaches..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short --json-report --json-report-file=test-reports/conversation_comparison.json
	@echo "📊 Comparison report saved to test-reports/"

# Generate comprehensive reports
generate-stability-report:
	@echo "📊 Generating DeepEval stability report..."
	@mkdir -p test-reports
	PYTHONPATH=. python -c "from tests.llm_evaluation.test_conversation_chains import TestConversationChainReporting; \
	import pytest; \
	from tests.conftest import deepeval_model, skip_if_no_deepeval_support; \
	reporter = TestConversationChainReporting(); \
	reporter.test_generate_evaluation_report(None, None)"

# Export Prometheus metrics
export-metrics:
	@echo "📈 Exporting Prometheus metrics..."
	@mkdir -p test-reports
	PYTHONPATH=. python -c "from logging_config import save_metrics_to_file, export_prometheus_metrics; \
	save_metrics_to_file(); \
	print('Metrics exported to test-reports/prometheus_metrics.txt')"

# Monitoring and Observability commands (NEW!)
monitoring-start: ## Start complete monitoring stack (Prometheus + Grafana + Metrics)
	@echo "📊 Starting complete monitoring stack..."
	docker-compose --profile monitoring up -d
	@echo "✅ Monitoring stack started!"
	@echo ""
	@echo "📊 Access points:"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Metrics Exporter: http://localhost:8000/metrics"
	@echo "  Node Exporter: http://localhost:9100/metrics"

monitoring-stop: ## Stop monitoring stack
	@echo "🛑 Stopping monitoring stack..."
	docker-compose --profile monitoring down

monitoring-logs: ## View monitoring services logs
	@echo "📋 Viewing monitoring logs..."
	docker-compose --profile monitoring logs -f

monitoring-status: ## Check monitoring services status
	@echo "📊 Monitoring services status:"
	docker-compose --profile monitoring ps

monitoring-restart: ## Restart monitoring services
	@echo "🔄 Restarting monitoring services..."
	docker-compose --profile monitoring restart

monitoring-setup: ## Setup monitoring with Ollama and metrics
	@echo "⚙️ Setting up complete monitoring environment..."
	docker-compose --profile monitoring --profile setup up -d
	@echo "✅ Monitoring setup complete!"

monitoring-dev: ## Start development environment with monitoring
	@echo "🚀 Starting development environment with monitoring..."
	docker-compose --profile dev --profile monitoring up -d
	@echo "✅ Development + Monitoring ready!"
	@echo ""
	@echo "📊 Access points:"
	@echo "  Application: Available in development container"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Ollama: http://localhost:11434"
	@echo "  Jupyter: make docker-jupyter"

monitoring-full: ## Start complete environment (dev + monitoring + testing)
	@echo "🚀 Starting complete environment..."
	docker-compose --profile all up -d
	@echo "✅ Complete environment ready!"

monitoring-cleanup: ## Clean monitoring data volumes
	@echo "🧹 Cleaning monitoring data..."
	docker-compose --profile monitoring down -v
	docker volume rm semantic-evaluation-lab_prometheus_data semantic-evaluation-lab_grafana_data 2>/dev/null || true

# Monitoring utilities
monitoring-import-dashboard: ## Import Grafana dashboard
	@echo "📊 Dashboard available at: http://localhost:3000"
	@echo "Login: admin/admin"
	@echo "Dashboard: Semantic Kernel - LLM Evaluation Dashboard"

monitoring-test-with-metrics: ## Run tests with monitoring enabled
	@echo "🧪 Running tests with metrics collection..."
	docker-compose --profile monitoring --profile test up -d
	docker-compose --profile test up --abort-on-container-exit all-tests
	@echo "📊 Check metrics at: http://localhost:3000"

monitoring-health: ## Check health of all monitoring services
	@echo "🏥 Checking monitoring services health..."
	@echo "Prometheus:"
	@curl -s http://localhost:9090/-/ready > /dev/null && echo "  ✅ Prometheus is ready" || echo "  ❌ Prometheus not ready"
	@echo "Grafana:"
	@curl -s http://localhost:3000/api/health > /dev/null && echo "  ✅ Grafana is ready" || echo "  ❌ Grafana not ready"
	@echo "Metrics Exporter:"
	@curl -s http://localhost:8000/health > /dev/null && echo "  ✅ Metrics Exporter is ready" || echo "  ❌ Metrics Exporter not ready"
	@echo "Node Exporter:"
	@curl -s http://localhost:9100/metrics > /dev/null && echo "  ✅ Node Exporter is ready" || echo "  ❌ Node Exporter not ready"
	@echo "Ollama:"
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "  ✅ Ollama is ready" || echo "  ❌ Ollama not ready"

monitoring-validate: ## Validate monitoring configuration
	@echo "✅ Validating monitoring configuration..."
	@if [ ! -f "prometheus.yml" ]; then echo "❌ prometheus.yml not found"; exit 1; fi
	@if [ ! -d "grafana/provisioning" ]; then echo "❌ grafana/provisioning directory not found"; exit 1; fi
	@docker-compose --profile monitoring config --quiet && echo "✅ Docker Compose monitoring configuration is valid"

# Quick monitoring commands
mon: monitoring-start ## Alias for monitoring-start
mon-stop: monitoring-stop ## Alias for monitoring-stop
mon-logs: monitoring-logs ## Alias for monitoring-logs
mon-health: monitoring-health ## Alias for monitoring-health

# View metrics in terminal
view-metrics:
	@echo "📊 Current Prometheus metrics:"
	@if [ -f "test-reports/prometheus_metrics.txt" ]; then cat test-reports/prometheus_metrics.txt; else echo "No metrics file found. Run tests first."; fi

# Clean logs and reports
clean-logs:
	@echo "🧹 Cleaning logs and reports..."
	rm -rf logs/ test-reports/ htmlcov/ .coverage coverage.xml test-results.xml test-report.html .pytest_cache/

# Docker commands
docker-build: ## Build Docker images
	@echo "🐳 Building Docker images..."
	docker build --target development -t semantic-kernel:dev .
	docker build --target test -t semantic-kernel:test .
	docker build --target production -t semantic-kernel:prod .
	docker build --target ci -t semantic-kernel:ci .

docker-build-dev: ## Build development Docker image
	@echo "🐳 Building development Docker image..."
	docker build --target development -t semantic-kernel:dev .

docker-build-test: ## Build test Docker image
	@echo "🐳 Building test Docker image..."
	docker build --target test -t semantic-kernel:test .

docker-build-prod: ## Build production Docker image
	@echo "🐳 Building production Docker image..."
	docker build --target production -t semantic-kernel:prod .

docker-build-ci: ## Build CI Docker image
	@echo "🐳 Building CI Docker image..."
	docker build --target ci -t semantic-kernel:ci .

# Docker Compose commands
docker-up: ## Start all services with Docker Compose
	@echo "🚀 Starting all services with Docker Compose..."
	docker-compose --profile all up -d

docker-up-dev: ## Start development services
	@echo "🚀 Starting development services..."
	docker-compose --profile dev up -d

docker-up-app: ## Start just the application
	@echo "🚀 Starting application..."
	docker-compose --profile app up -d

docker-up-prod: ## Start production services
	@echo "🚀 Starting production services..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

docker-down: ## Stop all Docker Compose services
	@echo "🛑 Stopping all Docker Compose services..."
	docker-compose down

docker-logs: ## View logs from all services
	@echo "📋 Viewing Docker Compose logs..."
	docker-compose logs -f

docker-setup: ## Setup Ollama models for Docker
	@echo "⚙️ Setting up Ollama models..."
	docker-compose --profile setup up ollama-setup

# Docker testing commands
docker-test-unit: ## Run unit tests in Docker
	@echo "🧪 Running unit tests in Docker..."
	docker-compose --profile unit up --abort-on-container-exit unit-tests

docker-test-functional: ## Run functional tests in Docker
	@echo "🧪 Running functional tests in Docker..."
	docker-compose --profile functional up --abort-on-container-exit functional-tests

docker-test-llm-eval: ## Run LLM evaluation tests in Docker
	@echo "🧪 Running LLM evaluation tests in Docker..."
	docker-compose --profile llm-eval up --abort-on-container-exit llm-eval-tests

docker-test-conversation: ## Run conversation chain tests in Docker
	@echo "🧪 Running conversation chain tests in Docker..."
	docker-compose --profile conversation up --abort-on-container-exit conversation-chain-tests

docker-test-dynamic: ## Run dynamic conversation tests in Docker
	@echo "🧪 Running dynamic conversation tests in Docker..."
	docker-compose --profile dynamic up --abort-on-container-exit dynamic-conversation-tests

docker-test-all: ## Run all tests in Docker
	@echo "🧪 Running all tests in Docker..."
	docker-compose --profile test-all up --abort-on-container-exit all-tests

docker-test-quality: ## Run code quality checks in Docker
	@echo "🧪 Running code quality checks in Docker..."
	docker-compose --profile quality up --abort-on-container-exit quality-checks

# CI/CD Docker commands
docker-ci: ## Run complete CI pipeline in Docker
	@echo "🔄 Running CI pipeline in Docker..."
	docker-compose -f docker-compose.ci.yml up --abort-on-container-exit ci-tests

docker-ci-parallel: ## Run CI tests in parallel
	@echo "🔄 Running parallel CI tests with Docker..."
	docker-compose -f docker-compose.ci.yml up --abort-on-container-exit unit-tests-parallel functional-tests-parallel

docker-ci-setup: ## Setup CI environment
	@echo "⚙️ Setting up CI environment..."
	docker-compose -f docker-compose.ci.yml up -d ollama
	docker-compose -f docker-compose.ci.yml up --abort-on-container-exit ollama-ci-setup

# Docker development commands
docker-shell: ## Open shell in development container
	@echo "💻 Opening shell in development container..."
	docker-compose --profile dev exec app bash

docker-jupyter: ## Start Jupyter notebook server
	@echo "📓 Starting Jupyter notebook server..."
	docker-compose --profile jupyter up -d jupyter
	@echo "Jupyter available at: http://localhost:8888"

# Docker maintenance commands
docker-clean: ## Clean Docker images and containers
	@echo "🧹 Cleaning Docker resources..."
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

docker-clean-all: ## Clean all Docker resources (including images)
	@echo "🧹 Cleaning all Docker resources..."
	docker-compose down -v
	docker system prune -af
	docker volume prune -f

docker-reset: ## Reset Docker environment completely
	@echo "🔄 Resetting Docker environment..."
	docker-compose down -v
	docker system prune -af
	docker volume prune -f
	docker-compose --profile all build --no-cache

# Docker monitoring commands
docker-ps: ## Show running containers
	@echo "📋 Docker containers status:"
	docker-compose ps

docker-stats: ## Show container resource usage
	@echo "📊 Container resource usage:"
	docker stats

docker-health: ## Check health of all services
	@echo "🏥 Health check of all services:"
	docker-compose ps --format table

# Docker environment commands
docker-env-check: ## Check Docker environment
	@echo "🔍 Checking Docker environment..."
	@docker --version
	@docker-compose --version
	@echo "Docker daemon status:"
	@docker info --format "{{.ServerVersion}}" 2>/dev/null && echo "✅ Docker daemon running" || echo "❌ Docker daemon not running"

docker-validate: ## Validate Docker configuration
	@echo "✅ Validating Docker Compose files..."
	docker-compose config --quiet && echo "✅ docker-compose.yml is valid"
	docker-compose -f docker-compose.prod.yml config --quiet && echo "✅ docker-compose.prod.yml is valid"
	docker-compose -f docker-compose.ci.yml config --quiet && echo "✅ docker-compose.ci.yml is valid"

# Docker quick commands for development
docker-quick-test: docker-test-unit docker-test-functional ## Quick test run (unit + functional)

docker-quick-eval: docker-test-llm-eval docker-test-conversation ## Quick LLM evaluation run

docker-dev: ## Start development environment
	@echo "🚀 Starting complete development environment..."
	docker-compose --profile dev up -d
	@echo "✅ Development environment ready!"
	@echo "Application: http://localhost:5000 (if exposed)"
	@echo "Ollama: http://localhost:11434"
	@echo "Jupyter: docker-compose --profile jupyter up -d jupyter"

# Integration with existing CI commands
ci-docker: ## Run CI tests using Docker
	@echo "🔄 Running CI tests with Docker..."
	make docker-ci

ci-docker-parallel: ## Run CI tests in parallel using Docker
	@echo "🔄 Running parallel CI tests with Docker..."
	make docker-ci-parallel

# Quick monitoring commands
mon: monitoring-start ## Alias for monitoring-start
mon-stop: monitoring-stop ## Alias for monitoring-stop
mon-logs: monitoring-logs ## Alias for monitoring-logs
mon-health: monitoring-health ## Alias for monitoring-health

# 🔥 Load Testing with Locust and DeepEval Integration (NEW!)

# Core load testing commands
load-test-start: ## Start Locust web UI for interactive load testing
	@echo "🔥 Starting Locust Load Testing with DeepEval Integration..."
	@echo "Access Locust Web UI at: http://localhost:8089"
	docker-compose --profile load-test up -d
	@echo "✅ Locust started! Configure and run tests via web interface."

load-test-headless: ## Run headless load test (1 user, 5 minutes)
	@echo "🔥 Running headless load test with DeepEval metrics..."
	@mkdir -p test-reports logs
	docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless
	@echo "📊 Load test completed! Check test-reports/ for results."

load-test-stop: ## Stop all load testing services
	@echo "🛑 Stopping load testing services..."
	docker-compose --profile load-test --profile load-test-headless --profile load-test-conversation down

load-test-logs: ## View load testing logs
	@echo "📋 Viewing load testing logs..."
	docker-compose --profile load-test --profile load-test-headless logs -f

# Load test configurations
load-test-light: ## Light load test (1 user, 2 minutes)
	@echo "🔥 Running light load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=1 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=120s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-medium: ## Medium load test (3 users, 5 minutes)
	@echo "🔥 Running medium load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=3 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-heavy: ## Heavy load test (5 users, 10 minutes)
	@echo "🔥 Running heavy load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=5 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=600s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-stress: ## Stress test (10 users, 15 minutes)
	@echo "🔥 Running stress test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=10 LOCUST_SPAWN_RATE=2 LOCUST_RUN_TIME=900s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

# Conversation-focused load tests
load-test-conversations: ## Conversation-focused load test (2 users, 10 minutes)
	@echo "🗣️ Running conversation-focused load test..."
	@mkdir -p test-reports logs
	docker-compose --profile load-test-conversation up --abort-on-container-exit locust-conversation-focused

# Load test with monitoring
load-test-with-monitoring: ## Start load test with full monitoring stack
	@echo "🔥📊 Starting load test with complete monitoring..."
	docker-compose --profile monitoring --profile load-test up -d
	@echo ""
	@echo "📊 Access points:"
	@echo "  Locust Web UI: http://localhost:8089"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Metrics Exporter: http://localhost:8000/metrics"

# Local load testing (without Docker)
load-test-local: ## Run load test locally (requires local setup)
	@echo "🔥 Running local load test..."
	@mkdir -p test-reports logs
	@if [ -f "tests/load_testing/locustfile.py" ]; then \
		locust -f tests/load_testing/locustfile.py --host http://localhost:8000 --headless --users 1 --spawn-rate 1 --run-time 60s --html test-reports/locust_local_report.html; \
	else \
		echo "❌ Locust files not found. Use Docker-based commands instead."; \
		exit 1; \
	fi

# Load testing validation and setup
load-test-validate: ## Validate load testing setup
	@echo "✅ Validating load testing setup..."
	@if ! command -v docker-compose > /dev/null; then echo "❌ Docker Compose not found"; exit 1; fi
	@docker-compose --profile load-test config --quiet && echo "✅ Load test Docker configuration is valid"
	@if [ ! -f "tests/load_testing/locustfile.py" ]; then echo "❌ Locust files not found"; exit 1; fi
	@echo "✅ Load testing setup is valid"

load-test-setup: ## Setup load test environment
	@echo "⚙️ Setting up load test environment..."
	docker-compose --profile monitoring --profile setup up -d
	@echo "✅ Load test environment ready!"

# Load test reporting and analysis
load-test-reports: ## Generate comprehensive load test reports
	@echo "📊 Generating load test reports..."
	@if [ -f "test-reports/locust_report.html" ]; then \
		echo "📋 Locust HTML Report: test-reports/locust_report.html"; \
	fi
	@if [ -f "load_test_deepeval_report.json" ]; then \
		echo "📋 DeepEval Metrics Report: load_test_deepeval_report.json"; \
		python -c "import json; data=json.load(open('load_test_deepeval_report.json')); print('Summary:'); print(f'  Total Requests: {data[\"load_test_summary\"][\"total_requests\"]}'); print(f'  Success Rate: {data[\"deepeval_metrics\"].get(\"success_rate\", 0):.2%}'); print(f'  Avg Response Time: {data[\"load_test_summary\"][\"total_duration\"]:.2f}ms')"; \
	fi
	@if [ -d "test-reports" ]; then \
		echo "📁 All reports available in: test-reports/"; \
		ls -la test-reports/ | grep -E "(locust|deepeval)"; \
	fi

load-test-cleanup: ## Clean load test data and reports
	@echo "🧹 Cleaning load test data..."
	docker-compose --profile load-test --profile load-test-headless --profile load-test-conversation down -v
	rm -f load_test_deepeval_report.json
	rm -f test-reports/locust_*.html test-reports/locust_*.csv
	@echo "✅ Load test cleanup completed"

# Load test health and status
load-test-health: ## Check load testing services health
	@echo "🏥 Checking load testing services health..."
	@echo "Ollama (Load Test Target):"
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "  ✅ Ollama is ready for load testing" || echo "  ❌ Ollama not ready"
	@echo "Metrics Exporter (Load Test Target):"
	@curl -s http://localhost:8000/health > /dev/null && echo "  ✅ Metrics Exporter is ready" || echo "  ❌ Metrics Exporter not ready"
	@echo "Locust Web UI:"
	@curl -s http://localhost:8089 > /dev/null && echo "  ✅ Locust Web UI is accessible" || echo "  ❌ Locust Web UI not running"

load-test-status: ## Show load testing services status
	@echo "📊 Load testing services status:"
	docker-compose --profile load-test --profile load-test-headless --profile load-test-conversation ps

# Specialized load tests
load-test-static-conversations: ## Load test focused on static conversation chains
	@echo "🔄 Running static conversation load test..."
	@mkdir -p test-reports logs
	@# Run custom Locust command focusing on static conversations
	LOCUST_USERS=2 LOCUST_SPAWN_RATE=0.5 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-dynamic-conversations: ## Load test focused on dynamic conversation chains
	@echo "🔄 Running dynamic conversation load test..."
	@mkdir -p test-reports logs
	@# Run custom Locust command focusing on dynamic conversations
	LOCUST_USERS=2 LOCUST_SPAWN_RATE=0.5 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-mixed-workload: ## Load test with mixed static/dynamic workload
	@echo "🔄 Running mixed workload load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=3 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=600s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

# Load test with DeepEval analysis
load-test-deepeval-analysis: load-test-medium ## Run medium load test and analyze DeepEval metrics
	@echo "📊 Analyzing DeepEval metrics from load test..."
	@if [ -f "load_test_deepeval_report.json" ]; then \
		echo ""; \
		echo "=== DEEPEVAL LOAD TEST ANALYSIS ==="; \
		python -c " \
		import json; \
		data = json.load(open('load_test_deepeval_report.json')); \
		lt = data['load_test_summary']; \
		de = data['deepeval_metrics']; \
		print(f'Load Test Summary:'); \
		print(f'  Total Requests: {lt[\"total_requests\"]}'); \
		print(f'  Total Failures: {lt[\"total_failures\"]}'); \
		print(f'  Avg Response Time: {lt[\"total_duration\"]:.2f}ms'); \
		print(f'  Requests/Second: {lt[\"requests_per_second\"]:.2f}'); \
		print(f''); \
		print(f'DeepEval Quality Metrics:'); \
		print(f'  Success Rate: {de.get(\"success_rate\", 0):.2%}'); \
		print(f'  Error Rate: {de.get(\"error_rate\", 0):.2%}'); \
		metrics = de.get('metric_statistics', {}); \
		for metric, stats in metrics.items(): \
			print(f'  {metric}: {stats[\"mean\"]:.3f} (±{stats[\"max\"]-stats[\"min\"]:.3f})'); \
		"; \
		echo ""; \
		echo "Detailed report: load_test_deepeval_report.json"; \
	else \
		echo "❌ DeepEval report not found. Run a load test first."; \
	fi

# Quick load test aliases
lt-start: load-test-start ## Alias for load-test-start
lt-stop: load-test-stop ## Alias for load-test-stop
lt-light: load-test-light ## Alias for load-test-light
lt-medium: load-test-medium ## Alias for load-test-medium
lt-heavy: load-test-heavy ## Alias for load-test-heavy
lt-health: load-test-health ## Alias for load-test-health 

# ===============================================================================
# WEB UI COMMANDS (NEW!)
# ===============================================================================

web-ui-start: ## 🌐 Start the web UI interface
	@echo "🌐 Starting Semantic Evaluation Lab Web UI..."
	docker-compose --profile web-ui up -d
	@echo "✅ Web UI started!"
	@echo ""
	@echo "🎯 Access points:"
	@echo "  Web UI: http://localhost:5000"
	@echo "  API Docs: http://localhost:5000/api/docs"
	@echo "  Health Check: http://localhost:5000/api/health"

web-ui-stop: ## 🛑 Stop the web UI interface
	@echo "🛑 Stopping Web UI..."
	docker-compose stop web-ui

web-ui-restart: ## 🔄 Restart the web UI interface
	@echo "🔄 Restarting Web UI..."
	docker-compose restart web-ui

web-ui-logs: ## 📋 Show web UI logs
	@echo "📋 Web UI logs:"
	docker-compose logs -f web-ui

web-ui-dev: ## 🚀 Start complete development environment with Web UI
	@echo "🚀 Starting development environment with Web UI..."
	docker-compose --profile dev --profile web-ui --profile monitoring up -d
	@echo "✅ Development environment with Web UI ready!"
	@echo ""
	@echo "🎯 Access points:"
	@echo "  Web UI: http://localhost:5000"
	@echo "  Grafana: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Jupyter: make docker-jupyter"

web-ui-full: ## 🌐 Start complete lab with Web UI and all services
	@echo "🌐 Starting complete lab with Web UI..."
	docker-compose --profile all --profile web-ui up -d
	@echo "✅ Complete lab with Web UI ready!"
	@echo ""
	@echo "🎯 Access points:"
	@echo "  Web UI Dashboard: http://localhost:5000"
	@echo "  API Documentation: http://localhost:5000/api/docs"
	@echo "  Grafana Monitoring: http://localhost:3000"
	@echo "  Prometheus Metrics: http://localhost:9090"
	@echo "  Locust Load Testing: http://localhost:8089"

web-ui-health: ## 🏥 Check web UI health
	@echo "🏥 Checking Web UI health..."
	@curl -f http://localhost:5000/api/health 2>/dev/null && echo "✅ Web UI: Healthy" || echo "❌ Web UI: Unhealthy"

web-ui-demo: ## 🎪 Start demo environment optimized for showcasing
	@echo "🎪 Starting demo environment..."
	@echo "This will start the complete lab with all features enabled for demonstration"
	AUTO_RUN_TESTS=false ENABLE_MONITORING=true AUTO_SETUP_MODELS=true docker-compose --profile all --profile web-ui up -d
	@echo ""
	@echo "🎯 Demo Environment Ready!"
	@echo "================================"
	@echo ""
	@echo "🌐 PRIMARY INTERFACE:"
	@echo "  Web UI Dashboard: http://localhost:5000"
	@echo ""
	@echo "📊 MONITORING & ANALYTICS:"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus Metrics: http://localhost:9090"
	@echo "  API Documentation: http://localhost:5000/api/docs"
	@echo ""
	@echo "🔥 TESTING INTERFACES:"
	@echo "  Locust Load Testing: http://localhost:8089"
	@echo "  Jupyter Notebooks: make docker-jupyter (http://localhost:8888)"
	@echo ""
	@echo "🎛️ FEATURES TO DEMONSTRATE:"
	@echo "  ✅ One-click lab management (start/stop different profiles)"
	@echo "  ✅ Real-time service monitoring and health checks"
	@echo "  ✅ Automated test execution (unit, functional, LLM eval)"
	@echo "  ✅ Load testing with quality monitoring"
	@echo "  ✅ Live configuration management"
	@echo "  ✅ Real-time log streaming"
	@echo "  ✅ Comprehensive observability with Grafana dashboards"
	@echo ""
	@echo "🚀 Start by visiting: http://localhost:5000"

# Quick web UI aliases
ui: web-ui-start ## 🌐 Alias for web-ui-start
ui-dev: web-ui-dev ## 🚀 Alias for web-ui-dev
ui-full: web-ui-full ## 🌐 Alias for web-ui-full
ui-demo: web-ui-demo ## 🎪 Alias for web-ui-demo
ui-stop: web-ui-stop ## 🛑 Alias for web-ui-stop
ui-logs: web-ui-logs ## 📋 Alias for web-ui-logs 