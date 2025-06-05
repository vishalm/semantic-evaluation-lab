"""
Comprehensive logging configuration for DeepEval testing.

This module provides structured logging with Prometheus metrics integration,
JSON output for log aggregation systems, and performance monitoring.
"""

import logging
import structlog
import time
import os
from typing import Dict, Any, Optional
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from datetime import datetime
import json


# Prometheus metrics
METRICS_REGISTRY = CollectorRegistry()

# Test execution metrics
TEST_COUNTER = Counter(
    'deepeval_tests_total',
    'Total number of DeepEval tests executed',
    ['test_type', 'chain_length', 'status'],
    registry=METRICS_REGISTRY
)

TEST_DURATION = Histogram(
    'deepeval_test_duration_seconds',
    'Duration of DeepEval test execution',
    ['test_type', 'chain_length'],
    registry=METRICS_REGISTRY
)

METRIC_EVALUATION_DURATION = Histogram(
    'deepeval_metric_evaluation_seconds',
    'Duration of individual metric evaluation',
    ['metric_name', 'test_type'],
    registry=METRICS_REGISTRY
)

CONVERSATION_TURN_COUNTER = Counter(
    'deepeval_conversation_turns_total',
    'Total number of conversation turns evaluated',
    ['chain_length'],
    registry=METRICS_REGISTRY
)

METRIC_SCORES = Histogram(
    'deepeval_metric_scores',
    'Distribution of metric scores',
    ['metric_name', 'test_type', 'chain_length'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=METRICS_REGISTRY
)

FRAMEWORK_STABILITY_GAUGE = Gauge(
    'deepeval_framework_stability_coefficient',
    'Framework stability coefficient of variation',
    ['metric_name', 'chain_length'],
    registry=METRICS_REGISTRY
)

ERROR_COUNTER = Counter(
    'deepeval_errors_total',
    'Total number of errors in DeepEval testing',
    ['error_type', 'component'],
    registry=METRICS_REGISTRY
)


class PrometheusLoggingHandler(logging.Handler):
    """Custom logging handler that updates Prometheus metrics."""
    
    def emit(self, record):
        """Process log record and update metrics."""
        try:
            if hasattr(record, 'test_type') and hasattr(record, 'status'):
                chain_length = getattr(record, 'chain_length', 'unknown')
                TEST_COUNTER.labels(
                    test_type=record.test_type,
                    chain_length=str(chain_length),
                    status=record.status
                ).inc()
                
            if hasattr(record, 'duration_seconds'):
                test_type = getattr(record, 'test_type', 'unknown')
                chain_length = getattr(record, 'chain_length', 'unknown')
                TEST_DURATION.labels(
                    test_type=test_type,
                    chain_length=str(chain_length)
                ).observe(record.duration_seconds)
                
            if record.levelno >= logging.ERROR:
                error_type = getattr(record, 'error_type', 'unknown')
                component = getattr(record, 'component', 'unknown')
                ERROR_COUNTER.labels(
                    error_type=error_type,
                    component=component
                ).inc()
                
        except Exception as e:
            # Don't let logging errors break the application
            pass


class StructuredFormatter(structlog.processors.JSONRenderer):
    """Custom JSON formatter for structured logs."""
    
    def __call__(self, logger, method_name, event_dict):
        """Format log entry as structured JSON."""
        # Add standard fields
        event_dict.update({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': method_name.upper(),
            'logger': logger.name,
            'service': 'deepeval-testing',
            'version': '1.0.0'
        })
        
        # Add environment info
        if 'PYTEST_CURRENT_TEST' in os.environ:
            event_dict['test_context'] = os.environ['PYTEST_CURRENT_TEST']
            
        return super().__call__(logger, method_name, event_dict)


def configure_logging(
    log_level: str = "INFO",
    enable_prometheus: bool = True,
    enable_json: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Configure comprehensive logging system.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_prometheus: Whether to enable Prometheus metrics
        enable_json: Whether to use JSON formatting
        log_file: Optional log file path
    """
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if enable_json:
        processors.append(StructuredFormatter())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    if enable_json:
        console_handler.setFormatter(logging.Formatter('%(message)s'))
    else:
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root_logger.addHandler(file_handler)
    
    # Prometheus handler
    if enable_prometheus:
        prometheus_handler = PrometheusLoggingHandler()
        prometheus_handler.setLevel(logging.INFO)
        root_logger.addHandler(prometheus_handler)


@contextmanager
def log_test_execution(
    test_name: str,
    test_type: str = "deepeval",
    chain_length: Optional[int] = None,
    logger: Optional[structlog.BoundLogger] = None
):
    """
    Context manager for logging test execution with metrics.
    
    Args:
        test_name: Name of the test
        test_type: Type of test (deepeval, conversation_chain, etc.)
        chain_length: Length of conversation chain if applicable
        logger: Optional bound logger instance
    """
    if logger is None:
        logger = structlog.get_logger(test_name)
    
    start_time = time.time()
    
    logger.info(
        "test_execution_started",
        test_name=test_name,
        test_type=test_type,
        chain_length=chain_length
    )
    
    try:
        yield logger
        
        # Test succeeded
        duration = time.time() - start_time
        
        logger.info(
            "test_execution_completed",
            test_name=test_name,
            test_type=test_type,
            chain_length=chain_length,
            duration_seconds=round(duration, 3),
            status="success"
        )
        
        # Update Prometheus metrics
        TEST_COUNTER.labels(
            test_type=test_type,
            chain_length=str(chain_length) if chain_length else "none",
            status="success"
        ).inc()
        
        TEST_DURATION.labels(
            test_type=test_type,
            chain_length=str(chain_length) if chain_length else "none"
        ).observe(duration)
        
    except Exception as e:
        # Test failed
        duration = time.time() - start_time
        
        logger.error(
            "test_execution_failed",
            test_name=test_name,
            test_type=test_type,
            chain_length=chain_length,
            duration_seconds=round(duration, 3),
            status="failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Update Prometheus metrics
        TEST_COUNTER.labels(
            test_type=test_type,
            chain_length=str(chain_length) if chain_length else "none",
            status="failed"
        ).inc()
        
        ERROR_COUNTER.labels(
            error_type=type(e).__name__,
            component="test_execution"
        ).inc()
        
        raise


@contextmanager
def log_metric_evaluation(
    metric_name: str,
    test_type: str = "deepeval",
    logger: Optional[structlog.BoundLogger] = None
):
    """
    Context manager for logging metric evaluation.
    
    Args:
        metric_name: Name of the metric being evaluated
        test_type: Type of test
        logger: Optional bound logger instance
    """
    if logger is None:
        logger = structlog.get_logger("metric_evaluation")
    
    start_time = time.time()
    
    logger.debug(
        "metric_evaluation_started",
        metric_name=metric_name,
        test_type=test_type
    )
    
    try:
        yield logger
        
        duration = time.time() - start_time
        
        logger.debug(
            "metric_evaluation_completed",
            metric_name=metric_name,
            test_type=test_type,
            duration_ms=round(duration * 1000, 2)
        )
        
        # Update Prometheus metrics
        METRIC_EVALUATION_DURATION.labels(
            metric_name=metric_name,
            test_type=test_type
        ).observe(duration)
        
    except Exception as e:
        duration = time.time() - start_time
        
        logger.error(
            "metric_evaluation_failed",
            metric_name=metric_name,
            test_type=test_type,
            duration_ms=round(duration * 1000, 2),
            error=str(e),
            error_type=type(e).__name__
        )
        
        ERROR_COUNTER.labels(
            error_type=type(e).__name__,
            component="metric_evaluation"
        ).inc()
        
        raise


def log_metric_score(
    metric_name: str,
    score: float,
    test_type: str = "deepeval",
    chain_length: Optional[int] = None,
    logger: Optional[structlog.BoundLogger] = None
):
    """
    Log a metric score with Prometheus metrics.
    
    Args:
        metric_name: Name of the metric
        score: Score value (0.0 to 1.0)
        test_type: Type of test
        chain_length: Length of conversation chain if applicable
        logger: Optional bound logger instance
    """
    if logger is None:
        logger = structlog.get_logger("metric_scores")
    
    logger.info(
        "metric_score_recorded",
        metric_name=metric_name,
        score=round(score, 4),
        test_type=test_type,
        chain_length=chain_length
    )
    
    # Update Prometheus histogram
    METRIC_SCORES.labels(
        metric_name=metric_name,
        test_type=test_type,
        chain_length=str(chain_length) if chain_length else "none"
    ).observe(score)


def log_framework_stability(
    metric_name: str,
    coefficient_of_variation: float,
    chain_length: int,
    logger: Optional[structlog.BoundLogger] = None
):
    """
    Log framework stability metrics.
    
    Args:
        metric_name: Name of the metric
        coefficient_of_variation: CV value indicating stability
        chain_length: Length of conversation chain
        logger: Optional bound logger instance
    """
    if logger is None:
        logger = structlog.get_logger("framework_stability")
    
    stability_status = "stable" if coefficient_of_variation < 0.25 else "variable"
    
    logger.info(
        "framework_stability_measured",
        metric_name=metric_name,
        coefficient_of_variation=round(coefficient_of_variation, 4),
        chain_length=chain_length,
        stability_status=stability_status
    )
    
    # Update Prometheus gauge
    FRAMEWORK_STABILITY_GAUGE.labels(
        metric_name=metric_name,
        chain_length=str(chain_length)
    ).set(coefficient_of_variation)


def export_prometheus_metrics() -> str:
    """Export Prometheus metrics in text format."""
    return generate_latest(METRICS_REGISTRY).decode('utf-8')


def save_metrics_to_file(filepath: str = "test-reports/prometheus_metrics.txt"):
    """Save Prometheus metrics to file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w') as f:
        f.write(export_prometheus_metrics())
    
    logger = structlog.get_logger("metrics_export")
    logger.info("prometheus_metrics_exported", filepath=filepath)


def create_monitoring_dashboard_config() -> Dict[str, Any]:
    """Create Grafana dashboard configuration for monitoring."""
    return {
        "dashboard": {
            "title": "DeepEval Testing Metrics",
            "tags": ["deepeval", "testing", "metrics"],
            "panels": [
                {
                    "title": "Test Execution Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(deepeval_tests_total[5m])",
                            "legendFormat": "Tests per second"
                        }
                    ]
                },
                {
                    "title": "Framework Stability",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": "deepeval_framework_stability_coefficient",
                            "legendFormat": "Stability CV"
                        }
                    ]
                },
                {
                    "title": "Metric Score Distribution",
                    "type": "histogram",
                    "targets": [
                        {
                            "expr": "deepeval_metric_scores",
                            "legendFormat": "Score distribution"
                        }
                    ]
                },
                {
                    "title": "Error Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(deepeval_errors_total[5m])",
                            "legendFormat": "Errors per second"
                        }
                    ]
                }
            ]
        }
    }


if __name__ == "__main__":
    # Example usage
    configure_logging(
        log_level="INFO",
        enable_prometheus=True,
        enable_json=True,
        log_file="logs/deepeval_testing.log"
    )
    
    logger = structlog.get_logger("example")
    
    with log_test_execution("example_test", "deepeval", chain_length=5, logger=logger) as test_logger:
        test_logger.info("Running example test")
        
        with log_metric_evaluation("AnswerRelevancy", logger=test_logger) as metric_logger:
            metric_logger.info("Evaluating answer relevancy")
            
        log_metric_score("AnswerRelevancy", 0.85, chain_length=5, logger=test_logger)
        log_framework_stability("AnswerRelevancy", 0.12, 5, logger=test_logger)
    
    # Export metrics
    print("Prometheus Metrics:")
    print(export_prometheus_metrics()) 