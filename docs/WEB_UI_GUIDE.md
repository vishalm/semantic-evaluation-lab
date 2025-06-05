# 🌐 Semantic Evaluation Lab - Web UI Guide

## Overview

The Semantic Evaluation Lab Web UI is a comprehensive, user-friendly interface that provides complete control over your AI evaluation environment. Built with modern technologies and featuring real-time updates, intuitive design, and powerful automation capabilities.

## 🚀 Quick Start

### Start the Web UI Demo

```bash
# Start complete demo environment (recommended for first-time users)
make ui-demo

# Or start just the web UI with monitoring
make ui-dev

# Access the interface
open http://localhost:5000
```

## 🎯 Access Points

Once started, you can access these interfaces:

- **🌐 Main Web UI**: http://localhost:5000
- **📊 API Documentation**: http://localhost:5000/api/docs  
- **🏥 Health Check**: http://localhost:5000/api/health
- **📈 Grafana Monitoring**: http://localhost:3000 (admin/admin)
- **🔍 Prometheus Metrics**: http://localhost:9090
- **🔥 Load Testing**: http://localhost:8089

## 🎨 Interface Features

### 1. Dashboard Tab - Lab Control Center

**🏠 Main Dashboard**
- **Service Status Monitoring**: Real-time health checks for all services
- **Quick Action Buttons**: One-click lab management
  - Start Full Lab (all services + automation)
  - Start Dev Lab (development mode)
  - Start Testing Lab (testing optimized)
  - Stop Lab (all services)
- **Live Statistics**: Active services, healthy services, current time
- **Service Management**: Individual service status with direct links

**Real-time Features:**
- WebSocket-powered live updates every 10 seconds
- Service health monitoring (healthy/unhealthy/unknown)
- Color-coded status indicators (green/yellow/red)
- Auto-refreshing service statistics

### 2. Tests Tab - Automated Testing

**🧪 Test Management Interface**
- **Test Cards**: Visual cards for each test type
  - Unit Tests (code validation)
  - Functional Tests (application functionality)
  - LLM Evaluation (DeepEval quality metrics)
  - Conversation Chains (multi-turn conversation tests)
  - Load Tests (performance testing)
  - All Tests (complete suite)

**Test Features:**
- One-click test execution
- Real-time test status (running/completed)
- Visual feedback with loading states
- Automatic result collection

### 3. Load Testing Tab - Performance Analysis

**🔥 Load Testing Interface**
- Interactive Locust integration
- Configurable user scenarios
- Real-time performance metrics
- DeepEval quality monitoring during load tests

### 4. Monitoring Tab - Observability

**📊 Monitoring Dashboard**
- Direct access to Grafana dashboards
- Prometheus metrics explorer
- Real-time system health monitoring
- Performance analytics

### 5. Configuration Tab - Environment Management

**⚙️ Configuration Management**
- Environment variable management
- Lab settings configuration
- Real-time configuration validation
- Template system for different scenarios

### 6. Logs Tab - Real-time Debugging

**📋 Live Log Viewer**
- Real-time log streaming
- Service-specific log filtering
- Search and filtering capabilities
- Structured log display

## 🛠️ Technical Architecture

### Backend (FastAPI)

**Core Components:**
- **FastAPI Application**: Modern Python web framework
- **WebSocket Manager**: Real-time communication
- **Docker Integration**: Container management via Docker API
- **Service Health Monitoring**: Automated health checks
- **Configuration Management**: Environment handling

**API Endpoints:**
```
GET  /api/health              - Health check
GET  /api/services            - Service status
GET  /api/lab/status          - Lab comprehensive status
POST /api/lab/start/{profile} - Start lab with profile
POST /api/lab/stop            - Stop all services
POST /api/tests/{test_type}   - Run specific tests
POST /api/load-test           - Configure load tests
GET  /api/config              - Get configuration
POST /api/config              - Update configuration
GET  /api/logs/{service}      - Get service logs
```

### Frontend (React)

**Modern React Interface:**
- **Responsive Design**: Works on desktop, tablet, mobile
- **Real-time Updates**: WebSocket integration
- **Modern UI**: Tailwind CSS with custom styling
- **Interactive Components**: Dynamic state management
- **Progressive Enhancement**: Works without JavaScript

**Component Architecture:**
- App (main container)
- Navigation (tab-based navigation)
- Dashboard (service management)
- TestManager (test execution)
- LoadTesting (performance testing)
- Monitoring (observability)
- Configuration (settings)
- LogViewer (debugging)

## 🎛️ Usage Scenarios

### 1. Daily Development Workflow

```bash
# Start development environment with UI
make ui-dev

# Access web interface
open http://localhost:5000

# Use Dashboard to:
# - Monitor service health
# - Run tests as needed
# - Check logs for debugging
# - Monitor performance metrics
```

### 2. Demo/Presentation Setup

```bash
# Start complete demo environment
make ui-demo

# Access points for demo:
# - Main interface: http://localhost:5000
# - Monitoring: http://localhost:3000
# - Load testing: http://localhost:8089
```

### 3. CI/CD Integration

The web UI can be started in headless mode for CI/CD:

```bash
# Start services programmatically
docker-compose --profile web-ui up -d

# Run automated tests via API
curl -X POST http://localhost:5000/api/tests/all

# Get results
curl http://localhost:5000/api/lab/status
```

### 4. Load Testing & Analysis

```bash
# Start with monitoring
make ui-full

# Navigate to Load Testing tab
# - Configure test parameters
# - Monitor real-time metrics
# - Analyze results in Grafana
```

## 🔧 Configuration Options

### Environment Variables

The Web UI respects all lab environment variables:

```bash
# Core Configuration
LAB_NAME=Semantic-Evaluation-Lab
LAB_ENVIRONMENT=development
AUTO_RUN_TESTS=false
ENABLE_MONITORING=true

# Web UI Specific
WEB_UI_PORT=5000
WEB_UI_HOST=0.0.0.0
DOCKER_HOST=unix:///var/run/docker.sock
```

### Docker Profiles

Start different combinations:

```bash
# Web UI only
docker-compose --profile web-ui up -d

# Web UI + Development
docker-compose --profile dev --profile web-ui up -d

# Complete environment
docker-compose --profile all --profile web-ui up -d
```

## 🎯 Key Benefits

### For Developers
- **Visual Service Management**: No need to remember Docker commands
- **Real-time Feedback**: Immediate status updates
- **Integrated Testing**: Run tests from the interface
- **Live Debugging**: Stream logs in real-time

### For DevOps/SRE
- **Health Monitoring**: Centralized service health
- **Performance Metrics**: Integrated observability
- **Automation Control**: Manage automated processes
- **Scalability Insights**: Load testing integration

### For Researchers/Analysts
- **LLM Evaluation**: Visual test execution
- **Quality Metrics**: DeepEval integration
- **Conversation Analysis**: Multi-turn test management
- **Result Visualization**: Integrated reporting

### For Demos/Presentations
- **Professional Interface**: Modern, clean design
- **One-click Operations**: Simplified management
- **Real-time Updates**: Dynamic demonstrations
- **Comprehensive Coverage**: All features accessible

## 🚀 Advanced Features

### Real-time Service Orchestration
- Automatic dependency detection
- Health-based startup sequences
- Graceful degradation
- Auto-recovery mechanisms

### Intelligent Test Management
- Environment-aware test execution
- Automatic test skipping for missing dependencies
- Quality threshold monitoring
- Comprehensive reporting

### Dynamic Configuration
- Runtime configuration updates
- Environment template system
- Validation and error handling
- Backup and restore

### Monitoring Integration
- Prometheus metrics collection
- Grafana dashboard embedding
- Alert management
- Performance analytics

## 🔍 Troubleshooting

### Common Issues

**Web UI Not Starting:**
```bash
# Check Docker status
docker-compose ps

# Check logs
make ui-logs

# Restart service
make ui-restart
```

**Services Not Detected:**
```bash
# Verify Docker connection
docker ps

# Check service profiles
docker-compose --profile all ps

# Restart with clean state
make ui-stop && make ui-start
```

**Real-time Updates Not Working:**
- Check WebSocket connection in browser DevTools
- Verify no firewall blocking port 5000
- Restart web UI service

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Set debug environment
ENABLE_DEBUG_MODE=true make ui-start

# Check detailed logs
make ui-logs
```

## 📱 Mobile & Responsive Design

The Web UI is fully responsive and works on:
- Desktop browsers (Chrome, Firefox, Safari, Edge)
- Tablet devices (iPad, Android tablets)
- Mobile phones (iOS, Android)
- Progressive Web App features

## 🔐 Security Considerations

### Docker Socket Access
The Web UI requires Docker socket access for container management:
- Mounted read-only where possible
- Container isolation
- No privileged mode required

### Network Security
- Internal Docker network communication
- No external dependencies
- Local-only by default (can be configured for remote access)

### Data Protection
- No sensitive data stored in UI
- Real-time data only
- No persistent storage of credentials

## 🚀 Future Enhancements

Planned features for upcoming versions:
- **Advanced Analytics**: ML-powered insights
- **Custom Dashboards**: User-configurable views
- **Team Collaboration**: Multi-user support
- **Advanced Alerts**: Custom notification rules
- **Export/Import**: Configuration management
- **Plugin System**: Extensible architecture

## 📚 Related Documentation

- [AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md) - Complete automation setup
- [README.md](../README.md) - Project overview
- [Load Testing Guide](./LOAD_TESTING_GUIDE.md) - Performance testing
- [Monitoring Setup](./MONITORING_GUIDE.md) - Observability configuration

---

**🎉 The Semantic Evaluation Lab Web UI transforms complex AI evaluation workflows into an intuitive, visual experience. Start with `make ui-demo` and explore the full capabilities of your evaluation laboratory!** 