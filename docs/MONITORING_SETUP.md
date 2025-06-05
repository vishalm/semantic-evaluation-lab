# 📊 Monitoring Setup Guide

This guide explains how to set up and use the comprehensive monitoring stack for the Semantic Kernel project, featuring Prometheus and Grafana for collecting and visualizing metrics from Ollama, test executions, and system resources.

## 🎯 Overview

The monitoring stack provides:

- **Real-time dashboards** for LLM evaluation and performance
- **Metrics collection** from Ollama, tests, and system resources  
- **Automated alerting** for service health and performance issues
- **Historical data** for trend analysis and capacity planning

## 🚀 Quick Start

### 1. Start the Complete Monitoring Stack

```bash
# Start monitoring services (Prometheus + Grafana + Metrics Exporter)
make monitoring-start

# Or start development environment with monitoring
make monitoring-dev
```

### 2. Access the Dashboards

- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Metrics Exporter**: http://localhost:8000/metrics
- **Node Exporter**: http://localhost:9100/metrics

### 3. Run Tests with Metrics Collection

```bash
# Run tests with monitoring enabled
make monitoring-test-with-metrics

# Run specific test types
make test-dynamic-conversations
make test-conversation-chains
make eval-llm-comprehensive
```

## 📈 Dashboard Features

### Semantic Kernel - LLM Evaluation Dashboard

The main dashboard provides four key sections:

#### 🎯 Overview Panel
- **Total Tests Run**: Cumulative test execution count
- **Test Success Rate**: Pass/fail ratio over time
- **Average Test Duration**: Performance trending
- **Ollama Status**: Service availability indicator

#### 🧪 Test Execution Metrics
- **Test Execution Rate**: Real-time test throughput
- **Test Duration**: Individual test performance tracking
- **Dynamic vs Static Conversations**: Comparison metrics
- **Framework Stability**: DeepEval coefficient tracking

#### 🤖 Ollama Performance Metrics
- **Request Rate**: Ollama API calls per second
- **Response Time**: Latency monitoring
- **Model Usage**: Active model statistics
- **Error Rates**: Failed request tracking

#### 💻 System Resources
- **CPU Usage**: System processor utilization
- **Memory Usage**: RAM consumption and availability
- **Disk I/O**: Read/write operations per second
- **Container Resources**: Docker container metrics

## 🔧 Configuration

### Prometheus Configuration

The `prometheus.yml` file defines scraping targets:

```yaml
scrape_configs:
  - job_name: 'semantic-kernel-app'
    static_configs:
      - targets: ['metrics-exporter:8000']
    scrape_interval: 10s

  - job_name: 'ollama'
    static_configs:
      - targets: ['ollama:11434']
    scrape_interval: 15s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 15s
```

### Grafana Provisioning

Automatic dashboard and datasource provisioning through:

- `grafana/provisioning/datasources/prometheus.yml` - Prometheus datasource
- `grafana/provisioning/dashboards/dashboard.yml` - Dashboard provider
- `grafana/provisioning/dashboards/definitions/` - Dashboard definitions

### Metrics Exporter

The `prometheus_exporter.py` service collects:

- **System metrics** via psutil
- **Ollama health** via API calls
- **Test results** from JSON reports
- **Application uptime** and health status

## 📊 Available Metrics

### Test Execution Metrics
```
deepeval_tests_total{test_type, status}
deepeval_tests_passed_total{test_type}
deepeval_tests_failed_total{test_type}
deepeval_test_duration_seconds{test_name}
```

### Ollama Service Metrics
```
ollama_service_up
ollama_models_total
ollama_requests_total{model, status}
ollama_response_time_seconds{model}
```

### System Metrics
```
system_cpu_usage_percent
system_memory_usage_bytes
system_memory_total_bytes
system_disk_usage_bytes{path}
system_disk_total_bytes{path}
```

### Application Metrics
```
app_uptime_seconds
app_health_status
```

## 🛠️ Management Commands

### Core Monitoring
```bash
make monitoring-start       # Start monitoring stack
make monitoring-stop        # Stop monitoring services
make monitoring-restart     # Restart monitoring services
make monitoring-logs        # View monitoring logs
make monitoring-status      # Check service status
```

### Development & Testing
```bash
make monitoring-dev         # Dev environment + monitoring
make monitoring-setup       # Setup with Ollama models
make monitoring-full        # Complete environment
make monitoring-test-with-metrics  # Run tests with metrics
```

### Health & Maintenance
```bash
make monitoring-health      # Check all service health
make monitoring-validate    # Validate configuration
make monitoring-cleanup     # Clean monitoring data
make monitoring-export-metrics  # Export current metrics
```

### Quick Aliases
```bash
make mon                   # Start monitoring
make mon-stop             # Stop monitoring
make mon-logs             # View logs
make mon-health           # Health check
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Services Not Starting
```bash
# Check Docker daemon
make docker-env-check

# Validate configuration
make monitoring-validate

# Check logs
make monitoring-logs
```

#### 2. No Metrics Appearing
```bash
# Check metrics exporter
curl http://localhost:8000/health
curl http://localhost:8000/metrics

# Check Prometheus targets
# Visit: http://localhost:9090/targets
```

#### 3. Grafana Dashboard Issues
```bash
# Check Grafana logs
docker-compose logs grafana

# Reset Grafana data
make monitoring-cleanup
make monitoring-start
```

#### 4. Ollama Metrics Missing
```bash
# Check Ollama health
curl http://localhost:11434/api/tags

# Restart Ollama service
docker-compose restart ollama
```

### Health Checks

The `monitoring-health` command checks all services:

```bash
make monitoring-health
```

Expected output:
```
🏥 Checking monitoring services health...
Prometheus:
  ✅ Prometheus is ready
Grafana:
  ✅ Grafana is ready
Metrics Exporter:
  ✅ Metrics Exporter is ready
Node Exporter:
  ✅ Node Exporter is ready
Ollama:
  ✅ Ollama is ready
```

## 🚀 Advanced Usage

### Custom Metrics

Add custom metrics to the exporter by modifying `prometheus_exporter.py`:

```python
CUSTOM_METRICS = {
    'my_metric': Counter('my_custom_metric_total', 'Description', registry=METRICS_REGISTRY)
}
```

### Dashboard Customization

1. Access Grafana at http://localhost:3000
2. Login with admin/admin
3. Edit the "Semantic Kernel - LLM Evaluation Dashboard"
4. Add new panels or modify existing ones
5. Save the dashboard

### Alert Configuration

Add alerting rules in `prometheus/alerts/` directory:

```yaml
groups:
  - name: semantic_kernel_alerts
    rules:
      - alert: HighTestFailureRate
        expr: rate(deepeval_tests_failed_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High test failure rate detected"
```

## 📚 Integration with CI/CD

The monitoring stack integrates with CI/CD pipelines:

```bash
# In CI pipeline
make monitoring-setup
make test-all-with-metrics
make monitoring-export-metrics
```

Metrics are automatically collected during test runs and can be exported for analysis.

## 🔐 Security Considerations

- Default Grafana credentials should be changed in production
- Prometheus and Grafana should be secured with authentication
- Metrics endpoints should be protected in production environments
- Network access should be restricted using Docker networks

## 📈 Performance Impact

The monitoring stack is designed to be lightweight:

- **Metrics Collection**: ~15s intervals
- **Resource Usage**: <100MB RAM, <1% CPU
- **Storage**: ~10MB/day for metrics data
- **Network**: Minimal overhead for metric scraping

## 🤝 Contributing

To add new metrics or dashboard panels:

1. Update `prometheus_exporter.py` for new metrics
2. Modify dashboard JSON in `grafana/provisioning/dashboards/definitions/`
3. Test with `make monitoring-validate`
4. Document new features in this guide

---

For more information, see:
- [Docker Usage Guide](DOCKER_USAGE.md)
- [Dynamic Conversation Testing](DYNAMIC_CONVERSATION_TESTING.md)
- [Project README](../README.md) 