# Semantic Evaluation Lab - Makefile
.PHONY: help install test lint format clean coverage security docs

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ===============================================================================
# LAB AUTOMATION COMMANDS
# ===============================================================================

lab-start: ## [TEST] Start complete Semantic Evaluation Lab with automation
	@echo "[TEST] Starting Semantic Evaluation Lab with automation..."
	@echo "Configuration from .env file:"
	@echo "  LAB_NAME: $${LAB_NAME:-Semantic-Evaluation-Lab}"
	@echo "  LAB_ENVIRONMENT: $${LAB_ENVIRONMENT:-development}"
	@echo "  AUTO_RUN_TESTS: $${AUTO_RUN_TESTS:-false}"
	@echo "  AUTO_SETUP_MODELS: $${AUTO_SETUP_MODELS:-true}"
	@echo ""
	docker-compose --profile dev --profile auto-tests --profile monitoring up -d

lab-start-full: ## [START] Start lab with all automation enabled
	@echo "[START] Starting full automation lab..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true ENABLE_MONITORING=true docker-compose --profile dev --profile auto-tests --profile monitoring --profile load-test up -d

lab-start-minimal: ## [LIGHT] Start minimal lab (basic functionality only)
	@echo "[LIGHT] Starting minimal lab..."
	AUTO_RUN_TESTS=false ENABLE_MONITORING=false docker-compose --profile dev up -d

lab-start-testing: ## [TEST] Start lab optimized for testing
	@echo "[TEST] Starting testing-optimized lab..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_GENERATE_REPORTS=true docker-compose --profile dev --profile auto-tests up -d

lab-start-load-testing: ## [MEDIUM] Start lab optimized for load testing
	@echo "[MEDIUM] Starting load testing lab..."
	AUTO_RUN_LOAD_TESTS=true ENABLE_MONITORING=true docker-compose --profile dev --profile load-test --profile monitoring up -d

lab-stop: ## [STOP] Stop all lab services
	@echo "[STOP] Stopping Semantic Evaluation Lab..."
	docker-compose --profile all down

lab-restart: ## [RESTART] Restart lab with current configuration
	@echo "[RESTART] Restarting lab..."
	$(MAKE) lab-stop
	sleep 2
	$(MAKE) lab-start

lab-status: ## [MONITOR] Show lab status and configuration
	@echo "[MONITOR] Semantic Evaluation Lab Status"
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

lab-health: ## [HEALTH] Check lab health status
	@echo "[HEALTH] Checking lab health..."
	@if docker-compose ps | grep -q "semantic-evaluation-lab"; then \
		echo "[OK] Lab services are running"; \
	else \
		echo "[ERROR] Lab services are not running"; \
	fi
	@echo ""
	@echo "Service Health Checks:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -f http://localhost:11434/api/tags >/dev/null 2>&1 && echo "[OK] Ollama: Healthy" || echo "[ERROR] Ollama: Unhealthy"; \
		curl -f http://localhost:$${PROMETHEUS_PORT:-8000}/metrics >/dev/null 2>&1 && echo "[OK] Metrics Exporter: Healthy" || echo "[ERROR] Metrics Exporter: Unhealthy"; \
		curl -f http://localhost:9090/-/healthy >/dev/null 2>&1 && echo "[OK] Prometheus: Healthy" || echo "[ERROR] Prometheus: Unhealthy"; \
		curl -f http://localhost:$${GRAFANA_PORT:-3000}/api/health >/dev/null 2>&1 && echo "[OK] Grafana: Healthy" || echo "[ERROR] Grafana: Unhealthy"; \
	else \
		echo "[WARNING] curl not available, cannot check service health"; \
	fi

# ===============================================================================
# AUTO-TEST COMMANDS
# ===============================================================================

auto-test-setup: ## [FUNC] Setup environment for auto-testing
	@echo "[FUNC] Setting up auto-testing environment..."
	@mkdir -p logs test-reports htmlcov .deepeval_cache
	@echo "Checking configuration..."
	@if [ -z "$${OPENAI_API_KEY}" ] && [ "$${AUTO_RUN_LLM_EVAL_TESTS}" = "true" ]; then \
		echo "[WARNING] Warning: OPENAI_API_KEY not set but LLM evaluation tests are enabled"; \
	fi
	@echo "[OK] Auto-test setup completed"

auto-test-run: ## [AUTO] Run automated test suite based on configuration
	@echo "[AUTO] Running automated tests..."
	docker-compose --profile auto-tests up --abort-on-container-exit

auto-test-unit: ## [UNIT] Auto-run unit tests only
	@echo "[UNIT] Running automated unit tests..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=false AUTO_RUN_LLM_EVAL_TESTS=false docker-compose run --rm auto-test-orchestrator

auto-test-functional: ## [FUNC] Auto-run functional tests only
	@echo "[FUNC] Running automated functional tests..."
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=false AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_RUN_LLM_EVAL_TESTS=false docker-compose run --rm auto-test-orchestrator

auto-test-llm-eval: ## [EVAL] Auto-run LLM evaluation tests only
	@echo "[EVAL] Running automated LLM evaluation tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "[ERROR] Error: OPENAI_API_KEY required for LLM evaluation tests"; \
		exit 1; \
	fi
	AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=false AUTO_RUN_FUNCTIONAL_TESTS=false AUTO_RUN_LLM_EVAL_TESTS=true docker-compose run --rm auto-test-orchestrator

auto-test-conversations: ## [CONV] Auto-run conversation chain tests
	@echo "[CONV] Running automated conversation tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "[ERROR] Error: OPENAI_API_KEY required for conversation tests"; \
		exit 1; \
	fi
	AUTO_RUN_TESTS=true AUTO_RUN_CONVERSATION_TESTS=true docker-compose run --rm auto-test-orchestrator

auto-test-all: ## [ALL] Auto-run all test suites
	@echo "[ALL] Running all automated tests..."
	@if [ -z "$${OPENAI_API_KEY}" ]; then \
		echo "[WARNING] Warning: OPENAI_API_KEY not set, skipping LLM evaluation tests"; \
		AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true docker-compose run --rm auto-test-orchestrator; \
	else \
		AUTO_RUN_TESTS=true AUTO_RUN_UNIT_TESTS=true AUTO_RUN_FUNCTIONAL_TESTS=true AUTO_RUN_LLM_EVAL_TESTS=true AUTO_RUN_CONVERSATION_TESTS=true docker-compose run --rm auto-test-orchestrator; \
	fi

auto-test-reports: ## [MONITOR] Generate comprehensive auto-test reports
	@echo "[MONITOR] Generating auto-test reports..."
	@if [ -f "test-reports/auto-test-summary.json" ]; then \
		echo "Auto-test summary:"; \
		cat test-reports/auto-test-summary.json | python -m json.tool; \
	else \
		echo "No auto-test summary found. Run auto-test-run first."; \
	fi

# ===============================================================================
# AUTO-LOAD TESTING COMMANDS
# ===============================================================================

auto-load-test-light: ## [LIGHT] Auto-run light load test (1 user, 2 min)
	@echo "[LIGHT] Running automated light load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=1 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=120s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-medium: ## [MEDIUM] Auto-run medium load test (3 users, 5 min)
	@echo "[MEDIUM] Running automated medium load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=3 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-heavy: ## [START] Auto-run heavy load test (5 users, 10 min)
	@echo "[START] Running automated heavy load test..."
	AUTO_RUN_LOAD_TESTS=true LOCUST_USERS=5 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=600s docker-compose --profile load-test-headless up --abort-on-container-exit

auto-load-test-conversation: ## [CONV] Auto-run conversation-focused load test
	@echo "[CONV] Running automated conversation load test..."
	AUTO_RUN_LOAD_TESTS=true docker-compose --profile load-test-conversation up --abort-on-container-exit

# ===============================================================================
# CONFIGURATION MANAGEMENT
# ===============================================================================

config-check: ## [CHECK] Check configuration and environment
	@echo "[CHECK] Checking Semantic Evaluation Lab configuration..."
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
		echo "[OK] .env file exists"; \
	else \
		echo "[WARNING] .env file not found (using defaults)"; \
	fi
	@if [ -n "$${OPENAI_API_KEY}" ]; then \
		echo "[OK] OPENAI_API_KEY is set"; \
	else \
		echo "[WARNING] OPENAI_API_KEY not set (LLM evaluation tests will be skipped)"; \
	fi

config-generate: ## [UNIT] Generate configuration files from templates
	@echo "[UNIT] Generating configuration files..."
	@if [ ! -f ".env" ]; then \
		if [ -f "env.example" ]; then \
			cp env.example .env; \
			echo "[OK] Created .env file from env.example"; \
			echo "Please edit .env file with your configuration"; \
		else \
			echo "[ERROR] env.example file not found"; \
			exit 1; \
		fi; \
	else \
		echo "[WARNING] .env file already exists"; \
	fi

config-validate: ## [OK] Validate current configuration
	@echo "[OK] Validating configuration..."
	docker-compose config > /dev/null && echo "[OK] Docker Compose configuration is valid" || echo "[ERROR] Docker Compose configuration has errors"

config-example-quick-start: ## [START] Generate quick start configuration
	@echo "[START] Generating quick start configuration..."
	@printf '%s\n' \
		'# Quick Start Configuration' \
		'LAB_ENVIRONMENT=development' \
		'AUTO_RUN_TESTS=true' \
		'AUTO_RUN_UNIT_TESTS=true' \
		'AUTO_RUN_FUNCTIONAL_TESTS=true' \
		'AUTO_SETUP_MODELS=true' \
		'ENABLE_MONITORING=true' \
		'LOCUST_USERS=1' \
		'LOCUST_RUN_TIME=120s' \
		> .env.quickstart
	@echo "[OK] Quick start configuration saved to .env.quickstart"
	@echo "To use: mv .env.quickstart .env"

config-example-full-eval: ## [EVAL] Generate full evaluation configuration
	@echo "[EVAL] Generating full evaluation configuration..."
	@printf '%s\n' \
		'# Full Evaluation Configuration' \
		'LAB_ENVIRONMENT=evaluation' \
		'AUTO_RUN_TESTS=true' \
		'AUTO_RUN_UNIT_TESTS=true' \
		'AUTO_RUN_FUNCTIONAL_TESTS=true' \
		'AUTO_RUN_LLM_EVAL_TESTS=true' \
		'AUTO_RUN_CONVERSATION_TESTS=true' \
		'ENABLE_CONVERSATION_STABILITY_TESTS=true' \
		'ENABLE_DYNAMIC_CONVERSATION_TESTS=true' \
		'CONVERSATION_CHAIN_LENGTHS=5,10,15,20' \
		'ENABLE_MONITORING=true' \
		'ENABLE_NOTIFICATIONS=true' \
		'LOCUST_USERS=3' \
		'LOCUST_RUN_TIME=300s' \
		'# Remember to set OPENAI_API_KEY=your-key-here' \
		> .env.fulleval
	@echo "[OK] Full evaluation configuration saved to .env.fulleval"
	@echo "To use: mv .env.fulleval .env and add your OPENAI_API_KEY"

# ===============================================================================
# MONITORING AUTOMATION
# ===============================================================================

monitoring-auto-start: ## [MONITOR] Auto-start monitoring with optimal settings
	@echo "[MONITOR] Starting automated monitoring..."
	ENABLE_MONITORING=true ENABLE_ALERTING=true docker-compose --profile monitoring up -d

monitoring-health-check: ## [HEALTH] Automated monitoring health check
	@echo "[HEALTH] Checking monitoring health..."
	@if command -v curl >/dev/null 2>&1; then \
		curl -f http://localhost:9090/-/healthy >/dev/null 2>&1 && echo "[OK] Prometheus: Healthy" || echo "[ERROR] Prometheus: Unhealthy"; \
		curl -f http://localhost:$${GRAFANA_PORT:-3000}/api/health >/dev/null 2>&1 && echo "[OK] Grafana: Healthy" || echo "[ERROR] Grafana: Unhealthy"; \
		curl -f http://localhost:$${PROMETHEUS_PORT:-8000}/metrics >/dev/null 2>&1 && echo "[OK] Metrics Exporter: Healthy" || echo "[ERROR] Metrics Exporter: Unhealthy"; \
	else \
		echo "[WARNING] curl not available, cannot check health"; \
	fi

# ===============================================================================
# QUICK ALIASES
# ===============================================================================

ls: lab-start ## [TEST] Alias for lab-start
lsf: lab-start-full ## [START] Alias for lab-start-full
lst: lab-start-testing ## [TEST] Alias for lab-start-testing
lsl: lab-start-load-testing ## [MEDIUM] Alias for lab-start-load-testing
lx: lab-stop ## [STOP] Alias for lab-stop
lr: lab-restart ## [RESTART] Alias for lab-restart
lh: lab-health ## [HEALTH] Alias for lab-health
cc: config-check ## [CHECK] Alias for config-check
at: auto-test-run ## [AUTO] Alias for auto-test-run
ata: auto-test-all ## [ALL] Alias for auto-test-all

# ===============================================================================
# DEVELOPMENT ENVIRONMENT MANAGEMENT
# ===============================================================================

lab-logs: ## [LOGS] Show lab service logs
	@echo "[LOGS] Showing lab service logs..."
	docker-compose logs -f --tail=50

lab-logs-app: ## [LOGS] Show application logs only
	docker-compose logs -f app

lab-logs-tests: ## [LOGS] Show test orchestrator logs
	docker-compose logs -f auto-test-orchestrator

lab-logs-monitoring: ## [LOGS] Show monitoring service logs
	docker-compose logs -f prometheus grafana metrics-exporter

lab-shell: ## [SHELL] Open shell in lab container
	docker-compose exec app bash

lab-clean: ## [CLEAN] Clean lab data and reports
	@echo "[CLEAN] Cleaning lab data..."
	rm -rf logs/* test-reports/* htmlcov/* .deepeval_cache/*
	@echo "[OK] Lab data cleaned"

lab-reset: ## [RESTART] Reset lab to initial state
	@echo "[RESTART] Resetting lab..."
	$(MAKE) lab-stop
	$(MAKE) lab-clean
	docker-compose down -v
	docker system prune -f
	@echo "[OK] Lab reset completed"

# ===============================================================================
# INSTALLATION AND TESTING
# ===============================================================================

install: ## Install dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e ".[dev,test]"

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

test-env-check: ## Check test environment and show which tests will run
	@echo "Checking test environment..."
	@python -c "import pytest; pytest.main(['-v', '--collect-only', '--quiet', 'tests/'])" 2>/dev/null | grep -E "(SKIP|collected|session starts)" || echo "Running test environment validation..."
	@python -c "from tests.conftest import *; import pytest; pytest.main(['--version'])" > /dev/null 2>&1 || echo "[OK] Configuration loaded"

test-validate: ## Validate test environment with detailed output
	@echo "=== TEST ENVIRONMENT VALIDATION ==="
	@python -c "from config import app_config; import os; print(f'Ollama enabled: {app_config.use_ollama}'); print(f'OpenAI API key: {\"✓\" if os.getenv(\"OPENAI_API_KEY\") else \"✗\"}'); print(f'Azure API key: {\"✓\" if os.getenv(\"AZURE_OPENAI_API_KEY\") else \"✗\"}')"
	@echo "=== EXPECTED TEST BEHAVIOR ==="
	@python -c "from config import app_config; import os; has_ollama = app_config.use_ollama; has_openai = bool(os.getenv('OPENAI_API_KEY')); has_azure = bool(os.getenv('AZURE_OPENAI_API_KEY')); has_deepeval = has_ollama or has_openai; print(f'Unit tests: ✓ Will run'); print(f'Functional tests: {\"✓ Will run\" if (has_ollama or has_openai or has_azure) else \"[WARNING] Will be SKIPPED (no AI service)\"}'); print(f'DeepEval tests: {\"✓ Will run (\" + (\"Ollama\" if has_ollama else \"OpenAI\") + \")\" if has_deepeval else \"[WARNING] Will be SKIPPED (need Ollama or OPENAI_API_KEY)\"}')"

# ===============================================================================
# CODE QUALITY
# ===============================================================================

lint: ## Run linting checks
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

type-check: ## Run type checking
	mypy . --ignore-missing-imports --exclude venv --exclude .venv

security: ## Run security analysis
	bandit -r . --exclude ./venv,./tests,./.venv

format: ## Format code with black and isort
	black .
	isort .

format-check: ## Check code formatting without modifying files
	black --check --diff .
	isort --check-only --diff .

quality-check: format-check lint type-check security ## Run all quality checks

# ===============================================================================
# PROJECT MANAGEMENT
# ===============================================================================

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

run-ollama: ## Run with Ollama configuration
	USE_OLLAMA=true python basic_agent.py

run-azure: ## Run with Azure OpenAI configuration  
	USE_OLLAMA=false python basic_agent.py

run-ollama-script: ## Run the Ollama-specific script
	python basic_agent_ollama.py

# ===============================================================================
# DEEPEVAL COMMANDS
# ===============================================================================

deepeval-login: ## Login to Confident AI platform
	@echo "Run: deepeval login"
	@echo "Follow the instructions to connect to Confident AI platform"

deepeval-dashboard: ## Open DeepEval dashboard (after login)
	@echo "Run tests with: make test-deepeval"
	@echo "Then check the dashboard link in the output"

deepeval-check: ## Check DeepEval installation and setup
	@echo "Testing DeepEval integration..."
	python -c "from deepeval.test_case import LLMTestCase; from deepeval.metrics import AnswerRelevancyMetric; print('[OK] DeepEval imported successfully')"
	@echo "DeepEval version:"
	python -c "import deepeval; print(f'DeepEval: {deepeval.__version__ if hasattr(deepeval, \"__version__\") else \"version not found\"}')"

# ===============================================================================
# DEVELOPMENT HELPERS
# ===============================================================================

dev-setup: ## Set up development environment
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # Linux/Mac"
	@echo "  venv\\Scripts\\activate     # Windows"
	@echo "Then run: make install-dev"

# ===============================================================================
# CI/CD HELPERS
# ===============================================================================

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

# ===============================================================================
# DOCUMENTATION AND VERSION
# ===============================================================================

docs: ## Generate documentation (placeholder)
	@echo "Documentation generation would go here"
	@echo "Consider adding sphinx or mkdocs for documentation"

version: ## Show current version
	@echo "Semantic Evaluation Lab - End-to-End AI Evaluation & Observability"
	@echo "Repository: https://github.com/vishalm/semantic-evaluation-lab"
	@echo "Python version: $(shell python --version)"
	@echo "Pip version: $(shell pip --version)"
	@echo "DeepEval integration: [OK]"
	@echo "Locust load testing: [OK]"
	@echo "Monitoring stack: [OK]"

# ===============================================================================
# ENVIRONMENT HELPERS
# ===============================================================================

env-copy: ## Copy env.example to .env
	@if [ ! -f "env.example" ]; then \
		echo "[ERROR] env.example file not found"; \
		exit 1; \
	fi
	cp env.example .env
	@echo "[OK] Copied env.example to .env"
	@echo "Please edit .env with your configuration"
	@echo "For DeepEval metrics, set OPENAI_API_KEY"

env-check: ## Check environment variables
	@echo "Current environment configuration:"
	@python -c "import os; print(f'USE_OLLAMA: {os.getenv(\"USE_OLLAMA\", \"not set\")}')"
	@python -c "import os; print(f'OLLAMA_HOST: {os.getenv(\"OLLAMA_HOST\", \"not set\")}')"
	@python -c "import os; print(f'AGENT_NAME: {os.getenv(\"AGENT_NAME\", \"not set\")}')"
	@python -c "import os; print(f'OPENAI_API_KEY: {\"set\" if os.getenv(\"OPENAI_API_KEY\") else \"not set (required for DeepEval)\"}')"

# ===============================================================================
# LLM EVALUATION WORKFLOWS
# ===============================================================================

eval-agent-quality: ## Evaluate agent response quality
	pytest tests/llm_evaluation/test_agent_responses.py::TestAgentResponseQuality -v

eval-agent-workflow: ## Evaluate complete agent workflows
	pytest tests/llm_evaluation/test_agent_responses.py::TestAgentWorkflowEvaluation -v

eval-dataset: ## Evaluate using dataset approach
	pytest tests/llm_evaluation/test_agent_responses.py::TestDatasetEvaluation -v

eval-integration: ## Test DeepEval integration features
	pytest tests/llm_evaluation/test_deepeval_integration.py -v

# ===============================================================================
# CONVERSATION CHAIN TESTING
# ===============================================================================

test-conversation-chains: test-validate
	@echo "[RESTART] Running conversation chain evaluation tests..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short -m "llm_eval and deepeval"

test-conversation-chains-ollama: test-validate
	@echo "[RESTART] Running conversation chain tests with Ollama..."
	@if command -v curl >/dev/null 2>&1 && curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then \
		mkdir -p logs test-reports && \
		PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short -m "llm_eval and deepeval" --json-report --json-report-file=test-reports/conversation_chains_report.json; \
	else \
		echo "[ERROR] Ollama not available. Please start Ollama service."; \
		exit 1; \
	fi

test-conversation-chains-with-metrics: test-validate
	@echo "[RESTART] Running conversation chain tests with metrics collection..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -c "from logging_config import configure_logging; configure_logging()"
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short --json-report --json-report-file=test-reports/conversation_chains_detailed.json
	@echo "[MONITOR] Metrics saved to test-reports/"

# Test specific chain lengths
test-chain-5: test-validate
	@echo "[RESTART] Testing 5-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[5] -v

test-chain-10: test-validate
	@echo "[RESTART] Testing 10-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[10] -v

test-chain-15: test-validate
	@echo "[RESTART] Testing 15-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[15] -v

test-chain-20: test-validate
	@echo "[RESTART] Testing 20-turn conversation chains..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py::TestConversationChainStability::test_conversation_chain_evaluation[20] -v

# Dynamic conversation chain tests
test-dynamic-conversations: test-validate
	@echo "[RESTART] Running dynamic conversation chain tests..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short -m "llm_eval and deepeval"

test-dynamic-conversations-ollama: test-validate
	@echo "[RESTART] Running dynamic conversation tests with Ollama..."
	@if command -v curl >/dev/null 2>&1 && curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then \
		mkdir -p logs test-reports && \
		PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short -m "llm_eval and deepeval" --json-report --json-report-file=test-reports/dynamic_conversations_report.json; \
	else \
		echo "[ERROR] Ollama not available. Please start Ollama service."; \
		exit 1; \
	fi

test-dynamic-5: test-validate
	@echo "[RESTART] Testing 5-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_5_turn_dynamic_conversation -v

test-dynamic-10: test-validate
	@echo "[RESTART] Testing 10-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_10_turn_dynamic_conversation -v

test-dynamic-15: test-validate
	@echo "[RESTART] Testing 15-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_15_turn_dynamic_conversation -v

test-dynamic-20: test-validate
	@echo "[RESTART] Testing 20-turn dynamic conversations..."
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_dynamic_conversation_chains.py::TestDynamicConversationChains::test_20_turn_dynamic_conversation -v

test-conversation-comparison: test-validate
	@echo "[RESTART] Running comparison between original and dynamic conversation approaches..."
	@mkdir -p logs test-reports
	PYTHONPATH=. python -m pytest tests/llm_evaluation/test_conversation_chains.py tests/llm_evaluation/test_dynamic_conversation_chains.py -v --tb=short --json-report --json-report-file=test-reports/conversation_comparison.json
	@echo "[MONITOR] Comparison report saved to test-reports/"

# ===============================================================================
# REPORTING
# ===============================================================================

generate-stability-report:
	@echo "[MONITOR] Generating DeepEval stability report..."
	@mkdir -p test-reports
	PYTHONPATH=. python -c "from tests.llm_evaluation.test_conversation_chains import TestConversationChainReporting; \
	import pytest; \
	from tests.conftest import deepeval_model, skip_if_no_deepeval_support; \
	reporter = TestConversationChainReporting(); \
	reporter.test_generate_evaluation_report(None, None)"

export-metrics:
	@echo "📈 Exporting Prometheus metrics..."
	@mkdir -p test-reports
	PYTHONPATH=. python -c "from logging_config import save_metrics_to_file, export_prometheus_metrics; \
	save_metrics_to_file(); \
	print('Metrics exported to test-reports/prometheus_metrics.txt')"

view-metrics:
	@echo "[MONITOR] Current Prometheus metrics:"
	@if [ -f "test-reports/prometheus_metrics.txt" ]; then cat test-reports/prometheus_metrics.txt; else echo "No metrics file found. Run tests first."; fi

clean-logs:
	@echo "[CLEAN] Cleaning logs and reports..."
	rm -rf logs/ test-reports/ htmlcov/ .coverage coverage.xml test-results.xml test-report.html .pytest_cache/

# ===============================================================================
# MONITORING AND OBSERVABILITY
# ===============================================================================

monitoring-start: ## Start complete monitoring stack (Prometheus + Grafana + Metrics)
	@echo "[MONITOR] Starting complete monitoring stack..."
	docker-compose --profile monitoring up -d
	@echo "[OK] Monitoring stack started!"
	@echo ""
	@echo "[MONITOR] Access points:"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Metrics Exporter: http://localhost:8000/metrics"
	@echo "  Node Exporter: http://localhost:9100/metrics"

monitoring-stop: ## Stop monitoring stack
	@echo "[STOP] Stopping monitoring stack..."
	docker-compose --profile monitoring down

monitoring-logs: ## View monitoring services logs
	@echo "[LOGS] Viewing monitoring logs..."
	docker-compose --profile monitoring logs -f

monitoring-status: ## Check monitoring services status
	@echo "[MONITOR] Monitoring services status:"
	docker-compose --profile monitoring ps

monitoring-restart: ## Restart monitoring services
	@echo "[RESTART] Restarting monitoring services..."
	docker-compose --profile monitoring restart

monitoring-setup: ## Setup monitoring with Ollama and metrics
	@echo "[FUNC] Setting up complete monitoring environment..."
	docker-compose --profile monitoring --profile setup up -d
	@echo "[OK] Monitoring setup complete!"

monitoring-dev: ## Start development environment with monitoring
	@echo "[START] Starting development environment with monitoring..."
	docker-compose --profile dev --profile monitoring up -d
	@echo "[OK] Development + Monitoring ready!"
	@echo ""
	@echo "[MONITOR] Access points:"
	@echo "  Application: Available in development container"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Ollama: http://localhost:11434"
	@echo "  Jupyter: make docker-jupyter"

monitoring-full: ## Start complete environment (dev + monitoring + testing)
	@echo "[START] Starting complete environment..."
	docker-compose --profile all up -d
	@echo "[OK] Complete environment ready!"

monitoring-cleanup: ## Clean monitoring data volumes
	@echo "[CLEAN] Cleaning monitoring data..."
	docker-compose --profile monitoring down -v
	docker volume rm semantic-evaluation-lab_prometheus_data semantic-evaluation-lab_grafana_data 2>/dev/null || true

monitoring-health: ## Check health of all monitoring services
	@echo "[HEALTH] Checking monitoring services health..."
	@echo "Prometheus:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:9090/-/ready > /dev/null && echo "  [OK] Prometheus is ready" || echo "  [ERROR] Prometheus not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi
	@echo "Grafana:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:3000/api/health > /dev/null && echo "  [OK] Grafana is ready" || echo "  [ERROR] Grafana not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi
	@echo "Metrics Exporter:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:8000/health > /dev/null && echo "  [OK] Metrics Exporter is ready" || echo "  [ERROR] Metrics Exporter not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi
	@echo "Node Exporter:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:9100/metrics > /dev/null && echo "  [OK] Node Exporter is ready" || echo "  [ERROR] Node Exporter not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi
	@echo "Ollama:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:11434/api/tags > /dev/null && echo "  [OK] Ollama is ready" || echo "  [ERROR] Ollama not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi

monitoring-validate: ## Validate monitoring configuration
	@echo "[OK] Validating monitoring configuration..."
	@if [ ! -f "prometheus.yml" ]; then echo "[ERROR] prometheus.yml not found"; exit 1; fi
	@if [ ! -d "grafana/provisioning" ]; then echo "[ERROR] grafana/provisioning directory not found"; exit 1; fi
	@docker-compose --profile monitoring config --quiet && echo "[OK] Docker Compose monitoring configuration is valid"

# ===============================================================================
# DOCKER COMMANDS
# ===============================================================================

docker-build: ## Build Docker images
	@echo "🐳 Building Docker images..."
	docker build --target development -t semantic-kernel:dev .
	docker build --target test -t semantic-kernel:test .
	docker build --target production -t semantic-kernel:prod .
	docker build --target ci -t semantic-kernel:ci .

docker-build-dev: ## Build development Docker image
	@echo "🐳 Building development Docker image..."
	docker build --target development -t semantic-kernel:dev .

docker-up: ## Start all services with Docker Compose
	@echo "[START] Starting all services with Docker Compose..."
	docker-compose --profile all up -d

docker-down: ## Stop all Docker Compose services
	@echo "[STOP] Stopping all Docker Compose services..."
	docker-compose down

docker-logs: ## View logs from all services
	@echo "[LOGS] Viewing Docker Compose logs..."
	docker-compose logs -f

docker-shell: ## Open shell in development container
	@echo "💻 Opening shell in development container..."
	docker-compose --profile dev exec app bash

docker-clean: ## Clean Docker images and containers
	@echo "[CLEAN] Cleaning Docker resources..."
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

# ===============================================================================
# LOAD TESTING WITH LOCUST AND DEEPEVAL INTEGRATION
# ===============================================================================

load-test-start: ## Start Locust web UI for interactive load testing
	@echo "[MEDIUM] Starting Locust Load Testing with DeepEval Integration..."
	@echo "Access Locust Web UI at: http://localhost:8089"
	docker-compose --profile load-test up -d
	@echo "[OK] Locust started! Configure and run tests via web interface."

load-test-headless: ## Run headless load test (1 user, 5 minutes)
	@echo "[MEDIUM] Running headless load test with DeepEval metrics..."
	@mkdir -p test-reports logs
	docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless
	@echo "[MONITOR] Load test completed! Check test-reports/ for results."

load-test-stop: ## Stop all load testing services
	@echo "[STOP] Stopping load testing services..."
	docker-compose --profile load-test --profile load-test-headless --profile load-test-conversation down

load-test-light: ## Light load test (1 user, 2 minutes)
	@echo "[MEDIUM] Running light load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=1 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=120s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-medium: ## Medium load test (3 users, 5 minutes)
	@echo "[MEDIUM] Running medium load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=3 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=300s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-heavy: ## Heavy load test (5 users, 10 minutes)
	@echo "[MEDIUM] Running heavy load test..."
	@mkdir -p test-reports logs
	LOCUST_USERS=5 LOCUST_SPAWN_RATE=1 LOCUST_RUN_TIME=600s docker-compose --profile load-test-headless up --abort-on-container-exit locust-headless

load-test-health: ## Check load testing services health
	@echo "[HEALTH] Checking load testing services health..."
	@echo "Ollama (Load Test Target):"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:11434/api/tags > /dev/null && echo "  [OK] Ollama is ready for load testing" || echo "  [ERROR] Ollama not ready"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi
	@echo "Locust Web UI:"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s http://localhost:8089 > /dev/null && echo "  [OK] Locust Web UI is accessible" || echo "  [ERROR] Locust Web UI not running"; \
	else \
		echo "  [WARNING] curl not available, cannot check health"; \
	fi

# ===============================================================================
# WEB UI COMMANDS
# ===============================================================================

web-ui-start: ## 🌐 Start the web UI interface
	@echo "🌐 Starting Semantic Evaluation Lab Web UI..."
	docker-compose --profile web-ui up -d
	@echo "[OK] Web UI started!"
	@echo ""
	@echo "[ALL] Access points:"
	@echo "  Web UI: http://localhost:5000"
	@echo "  API Docs: http://localhost:5000/api/docs"
	@echo "  Health Check: http://localhost:5000/api/health"

web-ui-stop: ## [STOP] Stop the web UI interface
	@echo "[STOP] Stopping Web UI..."
	docker-compose stop web-ui

web-ui-logs: ## [LOGS] Show web UI logs
	@echo "[LOGS] Web UI logs:"
	docker-compose logs -f web-ui

web-ui-health: ## [HEALTH] Check web UI health
	@echo "[HEALTH] Checking Web UI health..."
	@if command -v curl >/dev/null 2>&1; then \
		curl -f http://localhost:5000/api/health 2>/dev/null && echo "[OK] Web UI: Healthy" || echo "[ERROR] Web UI: Unhealthy"; \
	else \
		echo "[WARNING] curl not available, cannot check health"; \
	fi

web-ui-demo: ## 🎪 Start demo environment optimized for showcasing
	@echo "🎪 Starting demo environment..."
	@echo "This will start the complete lab with all features enabled for demonstration"
	AUTO_RUN_TESTS=false ENABLE_MONITORING=true AUTO_SETUP_MODELS=true docker-compose --profile all --profile web-ui up -d
	@echo ""
	@echo "[ALL] Demo Environment Ready!"
	@echo "================================"
	@echo ""
	@echo "🌐 PRIMARY INTERFACE:"
	@echo "  Web UI Dashboard: http://localhost:5000"
	@echo ""
	@echo "[MONITOR] MONITORING & ANALYTICS:"
	@echo "  Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "  Prometheus Metrics: http://localhost:9090"
	@echo "  API Documentation: http://localhost:5000/api/docs"
	@echo ""
	@echo "[MEDIUM] TESTING INTERFACES:"
	@echo "  Locust Load Testing: http://localhost:8089"
	@echo ""
	@echo "[START] Start by visiting: http://localhost:5000"

# ===============================================================================
# ALIASES
# ===============================================================================

# Monitoring aliases
mon: monitoring-start ## [MONITOR] Alias for monitoring-start
mon-stop: monitoring-stop ## [STOP] Alias for monitoring-stop
mon-logs: monitoring-logs ## [LOGS] Alias for monitoring-logs
mon-health: monitoring-health ## [HEALTH] Alias for monitoring-health

# Load test aliases
lt-start: load-test-start ## [MEDIUM] Alias for load-test-start
lt-stop: load-test-stop ## [STOP] Alias for load-test-stop
lt-light: load-test-light ## [LIGHT] Alias for load-test-light
lt-medium: load-test-medium ## [MEDIUM] Alias for load-test-medium
lt-heavy: load-test-heavy ## [HEAVY] Alias for load-test-heavy
lt-health: load-test-health ## [HEALTH] Alias for load-test-health

# Web UI aliases
ui: web-ui-start ## 🌐 Alias for web-ui-start
ui-stop: web-ui-stop ## [STOP] Alias for web-ui-stop
ui-logs: web-ui-logs ## [LOGS] Alias for web-ui-logs
ui-demo: web-ui-demo ## 🎪 Alias for web-ui-demo