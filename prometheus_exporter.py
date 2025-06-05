#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for Semantic Evaluation Lab

This module provides a standalone HTTP server that exposes metrics
for Prometheus scraping. It includes application metrics, test execution
metrics, and system performance indicators.
"""

import time
import logging
import threading
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from prometheus_client import (
    Counter, Histogram, Gauge, Info, Enum,
    CollectorRegistry, generate_latest,
    start_http_server, CONTENT_TYPE_LATEST
)

# Import existing metrics registry
from logging_config import (
    METRICS_REGISTRY,
    TEST_COUNTER,
    TEST_DURATION,
    METRIC_EVALUATION_DURATION,
    CONVERSATION_TURN_COUNTER,
    METRIC_SCORES,
    FRAMEWORK_STABILITY_GAUGE,
    ERROR_COUNTER
)


class PrometheusExporter:
    """Prometheus metrics exporter for Semantic Kernel application."""
    
    def __init__(self, port: int = 8000, enable_ollama_metrics: bool = True):
        self.port = port
        self.enable_ollama_metrics = enable_ollama_metrics
        self.logger = logging.getLogger(__name__)
        
        # Application metrics
        self.app_info = Info(
            'semantic_kernel_app',
            'Application information',
            registry=METRICS_REGISTRY
        )
        
        self.app_status = Enum(
            'semantic_kernel_app_status',
            'Application status',
            states=['starting', 'running', 'stopping', 'stopped', 'error'],
            registry=METRICS_REGISTRY
        )
        
        self.app_uptime_seconds = Gauge(
            'semantic_kernel_app_uptime_seconds',
            'Application uptime in seconds',
            registry=METRICS_REGISTRY
        )
        
        # Ollama service metrics
        if self.enable_ollama_metrics:
            self.ollama_status = Gauge(
                'ollama_service_up',
                'Ollama service availability (1=up, 0=down)',
                registry=METRICS_REGISTRY
            )
            
            self.ollama_requests_total = Counter(
                'ollama_requests_total',
                'Total requests to Ollama service',
                ['method', 'endpoint', 'status'],
                registry=METRICS_REGISTRY
            )
            
            self.ollama_request_duration = Histogram(
                'ollama_request_duration_seconds',
                'Duration of requests to Ollama service',
                ['endpoint'],
                registry=METRICS_REGISTRY
            )
            
            self.ollama_models_loaded = Gauge(
                'ollama_models_loaded',
                'Number of models currently loaded in Ollama',
                registry=METRICS_REGISTRY
            )
            
            self.ollama_memory_usage = Gauge(
                'ollama_memory_usage_bytes',
                'Memory usage of Ollama service',
                ['type'],  # type: model, cache, etc.
                registry=METRICS_REGISTRY
            )
        
        # Test execution metrics (additional to existing ones)
        self.test_queue_size = Gauge(
            'semantic_kernel_test_queue_size',
            'Number of tests in queue',
            registry=METRICS_REGISTRY
        )
        
        self.active_test_sessions = Gauge(
            'semantic_kernel_active_test_sessions',
            'Number of active test sessions',
            registry=METRICS_REGISTRY
        )
        
        # Performance metrics
        self.cpu_usage_percent = Gauge(
            'semantic_kernel_cpu_usage_percent',
            'CPU usage percentage',
            registry=METRICS_REGISTRY
        )
        
        self.memory_usage_bytes = Gauge(
            'semantic_kernel_memory_usage_bytes',
            'Memory usage in bytes',
            ['type'],  # type: rss, vms, shared
            registry=METRICS_REGISTRY
        )
        
        # Initialize app info
        self.app_info.info({
            'version': '1.0.0',
            'component': 'semantic-evaluation-lab',
            'environment': os.getenv('ENVIRONMENT', 'development')
        })
        
        self.start_time = time.time()
        self.app_status.state('starting')
        
    def update_system_metrics(self):
        """Update system performance metrics."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage_percent.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage_bytes.labels(type='total').set(memory.total)
            self.memory_usage_bytes.labels(type='available').set(memory.available)
            self.memory_usage_bytes.labels(type='used').set(memory.used)
            
            # Process specific metrics
            process = psutil.Process()
            proc_memory = process.memory_info()
            self.memory_usage_bytes.labels(type='rss').set(proc_memory.rss)
            self.memory_usage_bytes.labels(type='vms').set(proc_memory.vms)
            
        except ImportError:
            self.logger.warning("psutil not available, skipping system metrics")
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def check_ollama_status(self) -> Dict[str, Any]:
        """Check Ollama service status and collect metrics."""
        if not self.enable_ollama_metrics:
            return {}
            
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        try:
            # Check service availability
            start_time = time.time()
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                self.ollama_status.set(1)
                self.ollama_requests_total.labels(
                    method='GET',
                    endpoint='/api/tags',
                    status='success'
                ).inc()
                self.ollama_request_duration.labels(endpoint='/api/tags').observe(duration)
                
                # Parse models information
                models_data = response.json()
                models = models_data.get('models', [])
                self.ollama_models_loaded.set(len(models))
                
                return {
                    'status': 'up',
                    'models': len(models),
                    'response_time': duration
                }
            else:
                self.ollama_status.set(0)
                self.ollama_requests_total.labels(
                    method='GET',
                    endpoint='/api/tags',
                    status='error'
                ).inc()
                return {'status': 'error', 'code': response.status_code}
                
        except requests.exceptions.RequestException as e:
            self.ollama_status.set(0)
            self.ollama_requests_total.labels(
                method='GET',
                endpoint='/api/tags',
                status='failed'
            ).inc()
            self.logger.warning(f"Ollama service check failed: {e}")
            return {'status': 'down', 'error': str(e)}
    
    def update_app_metrics(self):
        """Update application-level metrics."""
        # Update uptime
        uptime = time.time() - self.start_time
        self.app_uptime_seconds.set(uptime)
        
        # Update app status
        self.app_status.state('running')
        
        # Check for test reports and update test metrics
        self.update_test_metrics_from_files()
    
    def update_test_metrics_from_files(self):
        """Update test metrics from generated report files."""
        reports_dir = "test-reports"
        if not os.path.exists(reports_dir):
            return
            
        try:
            # Look for JSON test reports
            for filename in os.listdir(reports_dir):
                if filename.endswith('_report.json'):
                    filepath = os.path.join(reports_dir, filename)
                    self.parse_test_report(filepath)
                    
            # Look for Prometheus metrics files
            for filename in os.listdir(reports_dir):
                if filename.startswith('prometheus_metrics') and filename.endswith('.txt'):
                    # These are already handled by the main metrics registry
                    pass
                    
        except Exception as e:
            self.logger.error(f"Error updating test metrics from files: {e}")
    
    def parse_test_report(self, filepath: str):
        """Parse a test report JSON file and update metrics."""
        try:
            with open(filepath, 'r') as f:
                report_data = json.load(f)
            
            # Extract test execution data
            if 'tests' in report_data:
                for test in report_data['tests']:
                    test_name = test.get('nodeid', 'unknown')
                    outcome = test.get('outcome', 'unknown')
                    duration = test.get('duration', 0)
                    
                    # Update test counters
                    test_type = self.extract_test_type(test_name)
                    chain_length = self.extract_chain_length(test_name)
                    
                    # These metrics are already being updated by the test execution
                    # but we can also update from files for historical data
                    
        except Exception as e:
            self.logger.error(f"Error parsing test report {filepath}: {e}")
    
    def extract_test_type(self, test_name: str) -> str:
        """Extract test type from test name."""
        if 'conversation' in test_name:
            return 'conversation_chain'
        elif 'dynamic' in test_name:
            return 'dynamic_conversation'
        elif 'deepeval' in test_name:
            return 'deepeval'
        elif 'functional' in test_name:
            return 'functional'
        elif 'unit' in test_name:
            return 'unit'
        else:
            return 'unknown'
    
    def extract_chain_length(self, test_name: str) -> str:
        """Extract chain length from test name."""
        import re
        match = re.search(r'(\d+)_turn', test_name)
        if match:
            return match.group(1)
        return 'unknown'
    
    def metrics_handler(self):
        """Generate metrics in Prometheus format."""
        return generate_latest(METRICS_REGISTRY)
    
    def start_background_updater(self):
        """Start background thread to update metrics periodically."""
        def update_loop():
            while True:
                try:
                    self.update_app_metrics()
                    self.update_system_metrics()
                    self.check_ollama_status()
                    time.sleep(15)  # Update every 15 seconds
                except Exception as e:
                    self.logger.error(f"Error in metrics update loop: {e}")
                    time.sleep(5)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
        self.logger.info("Started background metrics updater")
    
    def start_server(self):
        """Start the Prometheus metrics HTTP server."""
        class MetricsHandler(BaseHTTPRequestHandler):
            def __init__(self, exporter, *args, **kwargs):
                self.exporter = exporter
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if self.path == '/metrics':
                    metrics_output = self.exporter.metrics_handler()
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.end_headers()
                    self.wfile.write(metrics_output)
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    health_data = {
                        'status': 'healthy',
                        'timestamp': datetime.now().isoformat(),
                        'uptime': time.time() - self.exporter.start_time
                    }
                    self.wfile.write(json.dumps(health_data).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                # Suppress default HTTP server logging
                pass
        
        # Create handler with exporter reference
        def handler(*args, **kwargs):
            MetricsHandler(self, *args, **kwargs)
        
        # Start background updater
        self.start_background_updater()
        
        # Start HTTP server
        server = HTTPServer(('0.0.0.0', self.port), handler)
        self.logger.info(f"Starting Prometheus metrics server on port {self.port}")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("Stopping Prometheus metrics server")
            self.app_status.state('stopping')
        finally:
            self.app_status.state('stopped')


def main():
    """Main entry point for the Prometheus exporter."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    port = int(os.getenv('PROMETHEUS_PORT', 8000))
    enable_ollama = os.getenv('ENABLE_OLLAMA_METRICS', 'true').lower() == 'true'
    
    exporter = PrometheusExporter(port=port, enable_ollama_metrics=enable_ollama)
    
    try:
        exporter.start_server()
    except Exception as e:
        logging.error(f"Failed to start Prometheus exporter: {e}")
        raise


if __name__ == '__main__':
    main() 