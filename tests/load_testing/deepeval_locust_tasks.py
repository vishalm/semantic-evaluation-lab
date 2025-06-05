"""
DeepEval Integration for Locust Load Testing

This module provides integration between Locust load testing framework
and DeepEval LLM evaluation metrics, enabling quality assessment under load.
"""

import time
import logging
import json
import traceback
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from locust import events
from locust.exception import InterruptTaskSet

# DeepEval imports
try:
    from deepeval import assert_test, evaluate
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        GEval
    )
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False

# Import conversation generators
try:
    from tests.llm_evaluation.test_conversation_chains import ConversationChainGenerator
    from tests.llm_evaluation.test_dynamic_conversation_chains import DynamicConversationGenerator
    CONVERSATION_GENERATORS_AVAILABLE = True
except ImportError:
    CONVERSATION_GENERATORS_AVAILABLE = False

# Import agent
try:
    from basic_agent import create_agent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class LoadTestResult:
    """Result of a load test with DeepEval metrics."""
    user_id: str
    task_name: str
    start_time: float
    end_time: float
    success: bool
    response_time: float
    test_cases: List[LLMTestCase]
    metric_scores: Dict[str, float]
    error: Optional[str] = None
    conversation_length: Optional[int] = None


class DeepEvalLoadTestMetrics:
    """Manages DeepEval metrics for load testing."""
    
    def __init__(self, enable_detailed_logging: bool = True):
        self.enable_detailed_logging = enable_detailed_logging
        self.results: List[LoadTestResult] = []
        
        # Initialize metrics
        self.answer_relevancy = AnswerRelevancyMetric(threshold=0.7)
        self.faithfulness = ContextualPrecisionMetric(threshold=0.7) if DEEPEVAL_AVAILABLE else None
        
        # Custom G-Eval metrics for load testing
        if DEEPEVAL_AVAILABLE:
            self.response_quality = GEval(
                name="ResponseQualityUnderLoad",
                criteria="""
                Evaluate the response quality considering load testing context:
                1. Response coherence and clarity despite potential system load
                2. Accuracy and relevance to the user's question
                3. Consistency with expected behavior under normal conditions
                4. Absence of errors or degraded responses due to load
                """,
                evaluation_params=["input", "actual_output"],
                threshold=0.75
            )
            
            self.load_resilience = GEval(
                name="LoadResilienceMetric",
                criteria="""
                Assess how well the system maintains quality under load:
                1. Response maintains expected quality standards
                2. No significant degradation in response intelligence
                3. Consistent response structure and formatting
                4. Appropriate handling of complex queries under load
                """,
                evaluation_params=["input", "actual_output"],
                threshold=0.8
            )
        else:
            self.response_quality = None
            self.load_resilience = None
    
    def create_test_case(self, user_input: str, agent_response: str, 
                        context: Optional[List[str]] = None) -> LLMTestCase:
        """Create a DeepEval test case."""
        return LLMTestCase(
            input=user_input,
            actual_output=agent_response,
            retrieval_context=context or [f"Load testing context for: {user_input}"]
        )
    
    def evaluate_response(self, test_case: LLMTestCase) -> Dict[str, float]:
        """Evaluate a single response using DeepEval metrics."""
        scores = {}
        
        if not DEEPEVAL_AVAILABLE:
            logger.warning("DeepEval not available, skipping evaluation")
            return scores
        
        try:
            # Evaluate with answer relevancy
            if self.answer_relevancy:
                self.answer_relevancy.measure(test_case)
                scores['answer_relevancy'] = self.answer_relevancy.score
            
            # Evaluate with response quality
            if self.response_quality:
                self.response_quality.measure(test_case)
                scores['response_quality'] = self.response_quality.score
            
            # Evaluate with load resilience
            if self.load_resilience:
                self.load_resilience.measure(test_case)
                scores['load_resilience'] = self.load_resilience.score
                
        except Exception as e:
            logger.error(f"Error during DeepEval evaluation: {e}")
            scores['evaluation_error'] = 0.0
        
        return scores
    
    def record_result(self, result: LoadTestResult):
        """Record a load test result."""
        self.results.append(result)
        
        if self.enable_detailed_logging:
            self._log_result(result)
    
    def _log_result(self, result: LoadTestResult):
        """Log detailed result information."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": result.user_id,
            "task_name": result.task_name,
            "response_time": result.response_time,
            "success": result.success,
            "metric_scores": result.metric_scores,
            "conversation_length": result.conversation_length,
            "error": result.error
        }
        
        logger.info(f"Load test result: {json.dumps(log_data, indent=2)}")
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all results."""
        if not self.results:
            return {}
        
        successful_results = [r for r in self.results if r.success]
        
        # Calculate response time statistics
        response_times = [r.response_time for r in self.results]
        
        # Calculate metric score statistics
        metric_stats = {}
        if successful_results:
            for metric_name in ['answer_relevancy', 'response_quality', 'load_resilience']:
                scores = [r.metric_scores.get(metric_name, 0) for r in successful_results 
                         if metric_name in r.metric_scores]
                if scores:
                    metric_stats[metric_name] = {
                        'mean': sum(scores) / len(scores),
                        'min': min(scores),
                        'max': max(scores),
                        'count': len(scores)
                    }
        
        return {
            'total_requests': len(self.results),
            'successful_requests': len(successful_results),
            'success_rate': len(successful_results) / len(self.results) if self.results else 0,
            'response_time_stats': {
                'mean': sum(response_times) / len(response_times) if response_times else 0,
                'min': min(response_times) if response_times else 0,
                'max': max(response_times) if response_times else 0,
                'p95': sorted(response_times)[int(0.95 * len(response_times))] if response_times else 0
            },
            'metric_statistics': metric_stats,
            'error_rate': (len(self.results) - len(successful_results)) / len(self.results) if self.results else 0
        }


class ConversationLoadTestMixin:
    """Mixin class providing conversation-based load testing capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deepeval_metrics = DeepEvalLoadTestMetrics()
        self.agent = None
        self.static_generator = None
        self.dynamic_generator = None
        
        # Initialize generators if available
        if CONVERSATION_GENERATORS_AVAILABLE:
            try:
                self.static_generator = ConversationChainGenerator()
                self.dynamic_generator = DynamicConversationGenerator()
            except Exception as e:
                logger.warning(f"Failed to initialize conversation generators: {e}")
        
        # Initialize agent if available
        if AGENT_AVAILABLE:
            try:
                self.agent = create_agent()
            except Exception as e:
                logger.warning(f"Failed to initialize agent: {e}")
    
    async def execute_conversation_chain(self, chain_length: int, 
                                       conversation_type: str = "static") -> LoadTestResult:
        """Execute a conversation chain and evaluate with DeepEval."""
        start_time = time.time()
        user_id = getattr(self, 'user_id', 'load_test_user')
        task_name = f"{conversation_type}_conversation_{chain_length}"
        
        try:
            # Generate conversation
            if conversation_type == "static" and self.static_generator:
                conversation = self.static_generator.generate_conversation_chain(chain_length)
            elif conversation_type == "dynamic" and self.dynamic_generator:
                conversation = await self.dynamic_generator.generate_dynamic_conversation_chain(
                    chain_length, self.agent
                )
            else:
                raise ValueError(f"Unsupported conversation type: {conversation_type}")
            
            # Process conversation and collect responses
            test_cases = []
            metric_scores = {}
            
            for i, (question, expected_context) in enumerate(conversation):
                # Get agent response
                if self.agent:
                    response = await self.agent.invoke_async(question)
                    response_text = str(response)
                else:
                    # Fallback for testing without agent
                    response_text = f"Mock response for load testing: {question[:50]}..."
                
                # Create test case
                test_case = self.deepeval_metrics.create_test_case(
                    question, response_text, [expected_context] if expected_context else None
                )
                test_cases.append(test_case)
                
                # Evaluate with DeepEval
                if DEEPEVAL_AVAILABLE:
                    scores = self.deepeval_metrics.evaluate_response(test_case)
                    for metric, score in scores.items():
                        if metric not in metric_scores:
                            metric_scores[metric] = []
                        metric_scores[metric].append(score)
            
            # Calculate average scores
            avg_scores = {
                metric: sum(scores) / len(scores) if scores else 0
                for metric, scores in metric_scores.items()
            }
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            result = LoadTestResult(
                user_id=user_id,
                task_name=task_name,
                start_time=start_time,
                end_time=end_time,
                success=True,
                response_time=response_time,
                test_cases=test_cases,
                metric_scores=avg_scores,
                conversation_length=chain_length
            )
            
            self.deepeval_metrics.record_result(result)
            return result
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            error_msg = f"Conversation chain failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            result = LoadTestResult(
                user_id=user_id,
                task_name=task_name,
                start_time=start_time,
                end_time=end_time,
                success=False,
                response_time=response_time,
                test_cases=[],
                metric_scores={},
                error=error_msg,
                conversation_length=chain_length
            )
            
            self.deepeval_metrics.record_result(result)
            raise InterruptTaskSet(reschedule=False)
    
    def execute_single_query(self, question: str) -> LoadTestResult:
        """Execute a single query and evaluate with DeepEval."""
        start_time = time.time()
        user_id = getattr(self, 'user_id', 'load_test_user')
        task_name = "single_query"
        
        try:
            # Get agent response
            if self.agent:
                response = self.agent.invoke(question)
                response_text = str(response)
            else:
                response_text = f"Mock response for load testing: {question[:50]}..."
            
            # Create test case and evaluate
            test_case = self.deepeval_metrics.create_test_case(question, response_text)
            metric_scores = {}
            
            if DEEPEVAL_AVAILABLE:
                metric_scores = self.deepeval_metrics.evaluate_response(test_case)
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            result = LoadTestResult(
                user_id=user_id,
                task_name=task_name,
                start_time=start_time,
                end_time=end_time,
                success=True,
                response_time=response_time,
                test_cases=[test_case],
                metric_scores=metric_scores,
                conversation_length=1
            )
            
            self.deepeval_metrics.record_result(result)
            return result
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            error_msg = f"Single query failed: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            result = LoadTestResult(
                user_id=user_id,
                task_name=task_name,
                start_time=start_time,
                end_time=end_time,
                success=False,
                response_time=response_time,
                test_cases=[],
                metric_scores={},
                error=error_msg,
                conversation_length=1
            )
            
            self.deepeval_metrics.record_result(result)
            return result


# Event handlers for Locust integration
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Event handler for test stop - generate final report."""
    logger.info("Load test completed, generating DeepEval metrics report...")
    
    # Collect all DeepEval metrics from all users
    all_results = []
    for user in environment.runner.user_classes:
        if hasattr(user, 'deepeval_metrics'):
            all_results.extend(user.deepeval_metrics.results)
    
    if all_results:
        # Create aggregated metrics
        deepeval_metrics = DeepEvalLoadTestMetrics()
        deepeval_metrics.results = all_results
        aggregated = deepeval_metrics.get_aggregated_metrics()
        
        # Log final report
        report = {
            "load_test_summary": {
                "total_duration": environment.stats.total.avg_response_time,
                "total_requests": environment.stats.total.num_requests,
                "total_failures": environment.stats.total.num_failures,
                "requests_per_second": environment.stats.total.current_rps,
            },
            "deepeval_metrics": aggregated
        }
        
        logger.info(f"Final Load Test Report with DeepEval Metrics:\n{json.dumps(report, indent=2)}")
        
        # Save report to file
        with open('load_test_deepeval_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n{'='*50}")
        print("LOAD TEST WITH DEEPEVAL METRICS COMPLETED")
        print(f"{'='*50}")
        print(f"Total Requests: {report['load_test_summary']['total_requests']}")
        print(f"Success Rate: {aggregated.get('success_rate', 0):.2%}")
        print(f"Average Response Time: {report['load_test_summary']['total_duration']:.2f}ms")
        print(f"Requests/Second: {report['load_test_summary']['requests_per_second']:.2f}")
        
        metric_stats = aggregated.get('metric_statistics', {})
        if metric_stats:
            print(f"\nDeepEval Metric Averages:")
            for metric, stats in metric_stats.items():
                print(f"  {metric}: {stats['mean']:.3f} (min: {stats['min']:.3f}, max: {stats['max']:.3f})")
        
        print(f"Detailed report saved to: load_test_deepeval_report.json")
        print(f"{'='*50}\n") 