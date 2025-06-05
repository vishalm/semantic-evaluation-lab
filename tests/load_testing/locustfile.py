"""
Locust Load Testing with DeepEval Integration - Semantic Evaluation Lab

This file provides comprehensive load testing for the Semantic Evaluation Lab
with integrated DeepEval metrics for quality assessment under load.

Features:
- Static conversation chain load tests
- Dynamic conversation chain load tests  
- Single query load tests
- Real-time DeepEval metrics evaluation
- Configurable user behavior patterns
- Comprehensive reporting and analytics

Usage:
    # Run with default settings (1 user)
    locust -f tests/load_testing/locustfile.py --host http://localhost:8000

    # Run with specific user count and spawn rate
    locust -f tests/load_testing/locustfile.py --users 5 --spawn-rate 1 --host http://localhost:8000

    # Run headless mode with automatic stop
    locust -f tests/load_testing/locustfile.py --headless --users 3 --spawn-rate 1 --run-time 300s --host http://localhost:8000
"""

import asyncio
import random
import time
import logging
import os
from typing import List, Dict, Any

from locust import HttpUser, TaskSet, task, between, User, events
from locust.exception import StopUser, InterruptTaskSet

from deepeval_locust_tasks import ConversationLoadTestMixin, LoadTestResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConversationChainTaskSet(TaskSet):
    """Task set for conversation chain load testing."""
    
    def on_start(self):
        """Initialize user session."""
        self.user_id = f"load_user_{random.randint(1000, 9999)}"
        logger.info(f"Starting load test session for user: {self.user_id}")
    
    @task(3)
    def static_conversation_short(self):
        """Execute short static conversation chains (5 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(5, "static")
                )
                self._record_locust_response("static_conversation_5", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Static conversation short failed: {e}")
            self._record_failure("static_conversation_5", str(e))
    
    @task(2)
    def static_conversation_medium(self):
        """Execute medium static conversation chains (10 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(10, "static")
                )
                self._record_locust_response("static_conversation_10", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Static conversation medium failed: {e}")
            self._record_failure("static_conversation_10", str(e))
    
    @task(1)
    def static_conversation_long(self):
        """Execute long static conversation chains (15 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(15, "static")
                )
                self._record_locust_response("static_conversation_15", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Static conversation long failed: {e}")
            self._record_failure("static_conversation_15", str(e))
    
    @task(3)
    def dynamic_conversation_short(self):
        """Execute short dynamic conversation chains (5 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(5, "dynamic")
                )
                self._record_locust_response("dynamic_conversation_5", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Dynamic conversation short failed: {e}")
            self._record_failure("dynamic_conversation_5", str(e))
    
    @task(2)
    def dynamic_conversation_medium(self):
        """Execute medium dynamic conversation chains (10 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(10, "dynamic")
                )
                self._record_locust_response("dynamic_conversation_10", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Dynamic conversation medium failed: {e}")
            self._record_failure("dynamic_conversation_10", str(e))
    
    @task(1)
    def dynamic_conversation_long(self):
        """Execute long dynamic conversation chains (15 turns)."""
        try:
            if hasattr(self.user, 'execute_conversation_chain'):
                result = asyncio.run(
                    self.user.execute_conversation_chain(15, "dynamic")
                )
                self._record_locust_response("dynamic_conversation_15", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Dynamic conversation long failed: {e}")
            self._record_failure("dynamic_conversation_15", str(e))
    
    def _record_locust_response(self, task_name: str, result: LoadTestResult):
        """Record response in Locust statistics."""
        if result.success:
            events.request_success.fire(
                request_type="LLM",
                name=task_name,
                response_time=result.response_time,
                response_length=result.conversation_length or 0
            )
        else:
            events.request_failure.fire(
                request_type="LLM",
                name=task_name,
                response_time=result.response_time,
                response_length=0,
                exception=Exception(result.error or "Unknown error")
            )
    
    def _record_failure(self, task_name: str, error_msg: str):
        """Record a task failure in Locust statistics."""
        events.request_failure.fire(
            request_type="LLM",
            name=task_name,
            response_time=0,
            response_length=0,
            exception=Exception(error_msg)
        )


class SingleQueryTaskSet(TaskSet):
    """Task set for single query load testing."""
    
    # Sample questions for load testing
    SAMPLE_QUESTIONS = [
        "What is Semantic Kernel and how does it work?",
        "Explain the concept of plugins in Semantic Kernel.",
        "How do you create a semantic function in Semantic Kernel?",
        "What are the benefits of using AI orchestration frameworks?",
        "Compare Semantic Kernel with LangChain framework.",
        "How does Semantic Kernel handle memory and context?",
        "What is the role of planners in Semantic Kernel?",
        "Explain the difference between semantic and native functions.",
        "How do you integrate external APIs with Semantic Kernel?",
        "What are the best practices for prompt engineering in SK?",
        "How does Semantic Kernel support different AI models?",
        "Explain the concept of skills in Semantic Kernel architecture.",
        "What is the purpose of connectors in Semantic Kernel?",
        "How do you handle errors and retries in Semantic Kernel?",
        "What are the deployment options for Semantic Kernel applications?"
    ]
    
    def on_start(self):
        """Initialize user session."""
        self.user_id = f"query_user_{random.randint(1000, 9999)}"
        logger.info(f"Starting single query session for user: {self.user_id}")
    
    @task(5)
    def execute_single_query(self):
        """Execute a single query with DeepEval evaluation."""
        question = random.choice(self.SAMPLE_QUESTIONS)
        
        try:
            if hasattr(self.user, 'execute_single_query'):
                result = self.user.execute_single_query(question)
                self._record_locust_response("single_query", result)
            else:
                logger.warning("ConversationLoadTestMixin not available")
        except Exception as e:
            logger.error(f"Single query failed: {e}")
            self._record_failure("single_query", str(e))
    
    def _record_locust_response(self, task_name: str, result: LoadTestResult):
        """Record response in Locust statistics."""
        if result.success:
            events.request_success.fire(
                request_type="LLM",
                name=task_name,
                response_time=result.response_time,
                response_length=len(result.test_cases[0].actual_output) if result.test_cases else 0
            )
        else:
            events.request_failure.fire(
                request_type="LLM",
                name=task_name,
                response_time=result.response_time,
                response_length=0,
                exception=Exception(result.error or "Unknown error")
            )
    
    def _record_failure(self, task_name: str, error_msg: str):
        """Record a task failure in Locust statistics."""
        events.request_failure.fire(
            request_type="LLM",
            name=task_name,
            response_time=0,
            response_length=0,
            exception=Exception(error_msg)
        )


class SemanticKernelLoadTestUser(ConversationLoadTestMixin, User):
    """
    Main load test user class with DeepEval integration.
    
    This class combines Locust's User with ConversationLoadTestMixin
    to provide comprehensive load testing with quality evaluation.
    """
    
    # Default wait time between tasks (1-3 seconds)
    wait_time = between(1, 3)
    
    # Weight distribution for different task sets
    tasks = [
        ConversationChainTaskSet,  # 70% conversation chains
        SingleQueryTaskSet,       # 30% single queries
    ]
    
    def __init__(self, environment):
        """Initialize the load test user."""
        super().__init__(environment)
        self.user_id = f"semantic_kernel_user_{random.randint(10000, 99999)}"
        
        # Log initialization
        logger.info(f"Initializing SemanticKernelLoadTestUser: {self.user_id}")
        
        # Environment configuration
        self.setup_environment()
    
    def setup_environment(self):
        """Setup environment configuration for load testing."""
        # Set environment variables for agent configuration
        os.environ.setdefault('USE_OLLAMA', 'true')
        os.environ.setdefault('OLLAMA_HOST', 'http://ollama:11434')
        os.environ.setdefault('OLLAMA_MODEL_ID', 'qwen2.5:latest')
        os.environ.setdefault('AGENT_NAME', f'LoadTest-Agent-{self.user_id}')
        
        logger.info(f"Environment setup complete for user: {self.user_id}")
    
    def on_start(self):
        """Called when the user starts."""
        logger.info(f"Load test user {self.user_id} starting...")
        
        # Validate initialization
        if not hasattr(self, 'deepeval_metrics'):
            logger.error(f"DeepEval metrics not initialized for user {self.user_id}")
        
        if not self.agent:
            logger.warning(f"Agent not available for user {self.user_id}, using mock responses")
    
    def on_stop(self):
        """Called when the user stops."""
        logger.info(f"Load test user {self.user_id} stopping...")
        
        # Log final metrics for this user
        if hasattr(self, 'deepeval_metrics') and self.deepeval_metrics.results:
            aggregated = self.deepeval_metrics.get_aggregated_metrics()
            logger.info(f"User {self.user_id} final metrics: {aggregated}")


# Alternative user classes for different load patterns

class ConversationFocusedUser(ConversationLoadTestMixin, User):
    """User focused primarily on conversation chains."""
    
    wait_time = between(2, 5)  # Longer wait time for complex conversations
    tasks = [ConversationChainTaskSet]  # Only conversation chains
    weight = 1


class QueryFocusedUser(ConversationLoadTestMixin, User):
    """User focused primarily on single queries."""
    
    wait_time = between(0.5, 1.5)  # Shorter wait time for quick queries
    tasks = [SingleQueryTaskSet]  # Only single queries
    weight = 2


class BalancedUser(ConversationLoadTestMixin, User):
    """Balanced user with mixed workload."""
    
    wait_time = between(1, 3)
    tasks = [ConversationChainTaskSet, SingleQueryTaskSet]
    weight = 3


# Configuration variables that can be overridden via environment
DEFAULT_USERS = int(os.getenv('LOCUST_USERS', '1'))
DEFAULT_SPAWN_RATE = float(os.getenv('LOCUST_SPAWN_RATE', '1'))
DEFAULT_RUN_TIME = os.getenv('LOCUST_RUN_TIME', '300s')

# Event handlers for enhanced reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Event handler for test start."""
    logger.info("Starting Semantic Evaluation Lab Load Test with DeepEval Integration")
    logger.info(f"Configuration: Users={environment.parsed_options.num_users}, "
                f"Spawn Rate={environment.parsed_options.spawn_rate}")
    
    print(f"\n{'='*60}")
    print("SEMANTIC EVALUATION LAB - LOAD TEST WITH DEEPEVAL")
    print(f"{'='*60}")
    print(f"Target Users: {environment.parsed_options.num_users}")
    print(f"Spawn Rate: {environment.parsed_options.spawn_rate}/sec")
    print(f"Host: {environment.host}")
    print(f"Features: Static & Dynamic Conversations, DeepEval Metrics")
    print(f"{'='*60}\n")


@events.request_success.add_listener  
def on_request_success(request_type, name, response_time, response_length, **kwargs):
    """Event handler for successful requests."""
    if request_type == "LLM":
        logger.debug(f"LLM request succeeded: {name} - {response_time:.2f}ms")


@events.request_failure.add_listener
def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    """Event handler for failed requests."""
    if request_type == "LLM":
        logger.warning(f"LLM request failed: {name} - {exception}")


if __name__ == "__main__":
    # This section is for running the load test directly
    import subprocess
    import sys
    
    print("Starting Semantic Evaluation Lab Load Test with DeepEval Integration")
    print("Use Ctrl+C to stop the test")
    
    cmd = [
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--users", str(DEFAULT_USERS),
        "--spawn-rate", str(DEFAULT_SPAWN_RATE),
        "--run-time", DEFAULT_RUN_TIME,
        "--host", "http://localhost:8000",
        "--headless"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")
    except subprocess.CalledProcessError as e:
        print(f"Load test failed: {e}")
        sys.exit(1) 