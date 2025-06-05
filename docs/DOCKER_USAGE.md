# Docker Usage Guide for Semantic Kernel Demo

## Overview

This guide covers the complete Docker setup for the Semantic Kernel Demo project, including development, testing, and production environments. The Docker setup provides consistent, reproducible environments across all stages of development and deployment.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Docker Architecture                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │Development  │    │   Testing   │    │ Production  │  │
│  │Environment  │    │Environment  │    │Environment  │  │
│  │             │    │             │    │             │  │
│  │ • Hot reload│    │ • Isolated  │    │ • Optimized │  │
│  │ • Debugging │    │ • Parallel  │    │ • Security  │  │
│  │ • Jupyter   │    │ • CI/CD     │    │ • Resources │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                   │                   │       │
│         └───────────────────┼───────────────────┘       │
│                             │                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │            Shared Infrastructure                    │  │
│  │                                                     │  │
│  │  ┌──────────────┐    ┌──────────────┐              │  │
│  │  │    Ollama    │    │   Networks   │              │  │
│  │  │   Service    │    │  & Volumes   │              │  │
│  │  │              │    │              │              │  │
│  │  │ • Local LLM  │    │ • Isolated   │              │  │
│  │  │ • Health     │    │ • Persistent │              │  │
│  │  │ • Models     │    │ • Named      │              │  │
│  │  └──────────────┘    └──────────────┘              │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker 20.10+ installed
- Docker Compose v2.0+ installed
- At least 8GB RAM available
- 10GB free disk space

### Validation

```bash
# Check Docker environment
make docker-env-check

# Validate Docker Compose configurations
make docker-validate
```

### Development Environment

```bash
# Start complete development environment
make docker-dev

# This starts:
# - Application service (development mode)
# - Ollama service with local models
# - All necessary networks and volumes

# Check status
make docker-ps

# View logs
make docker-logs
```

## Docker Images

### Multi-Stage Build Targets

| Target | Purpose | Size (approx) | Features |
|--------|---------|---------------|----------|
| `base` | Common foundation | 800MB | Python, dependencies, user setup |
| `development` | Development work | 1.2GB | + dev tools, Jupyter, hot reload |
| `test` | Testing environments | 1.0GB | + test frameworks, optimized for CI |
| `production` | Production deployment | 900MB | Minimal, security hardened |
| `ci` | CI/CD pipelines | 1.1GB | + CI tools, reporting, analysis |

### Building Images

```bash
# Build all images
make docker-build

# Build specific target
make docker-build-dev      # Development image
make docker-build-test     # Testing image
make docker-build-prod     # Production image
make docker-build-ci       # CI image

# Check image sizes
docker images semantic-kernel
```

## Services and Profiles

### Docker Compose Profiles

The project uses Docker Compose profiles to organize services:

| Profile | Services | Purpose |
|---------|----------|---------|
| `dev` | app, ollama | Development environment |
| `app` | app, ollama | Application only |
| `prod` | app-prod, ollama | Production environment |
| `test` | unit-tests, ollama | All testing services |
| `unit` | unit-tests | Unit tests only |
| `functional` | functional-tests, ollama | Functional tests |
| `llm-eval` | llm-eval-tests, ollama | LLM evaluation tests |
| `conversation` | conversation-chain-tests, ollama | Conversation chain tests |
| `dynamic` | dynamic-conversation-tests, ollama | Dynamic conversation tests |
| `quality` | quality-checks | Code quality checks |
| `ci` | ci, ollama | Complete CI pipeline |
| `jupyter` | jupyter, ollama | Jupyter notebook server |
| `setup` | ollama-setup | Ollama model setup |

### Using Profiles

```bash
# Start specific profiles
docker-compose --profile dev up -d        # Development
docker-compose --profile test up -d       # All tests
docker-compose --profile unit up         # Unit tests only
docker-compose --profile quality up      # Quality checks

# Multiple profiles
docker-compose --profile dev --profile jupyter up -d
```

## Testing with Docker

### Unit Tests

```bash
# Run unit tests in Docker
make docker-test-unit

# Run unit tests with parallel execution
docker-compose -f docker-compose.ci.yml up --abort-on-container-exit unit-tests-parallel

# Interactive unit test debugging
docker-compose --profile unit run --rm unit-tests bash
```

### Functional Tests

```bash
# Run functional tests (with Ollama)
make docker-test-functional

# Setup and run functional tests
make docker-setup  # Setup Ollama models first
make docker-test-functional
```

### LLM Evaluation Tests

```bash
# Run LLM evaluation tests (requires OPENAI_API_KEY)
OPENAI_API_KEY=your-key make docker-test-llm-eval

# Run conversation chain tests
OPENAI_API_KEY=your-key make docker-test-conversation

# Run dynamic conversation tests
OPENAI_API_KEY=your-key make docker-test-dynamic
```

### Complete Test Suite

```bash
# Run all tests
make docker-test-all

# Run CI pipeline
make docker-ci

# Run parallel CI tests
make docker-ci-parallel
```

## Development Workflow

### Starting Development Environment

```bash
# Option 1: Quick development start
make docker-dev

# Option 2: Manual control
docker-compose --profile dev up -d
docker-compose --profile setup up ollama-setup  # Setup models
```

### Development Tools

```bash
# Open shell in development container
make docker-shell

# Start Jupyter notebook
make docker-jupyter
# Access at: http://localhost:8888

# Run quality checks
make docker-test-quality

# View container status
make docker-ps

# Monitor resource usage
make docker-stats
```

### Hot Reload Development

The development container is configured with volume mounts for hot reload:

```yaml
volumes:
  - .:/app:rw                    # Source code
  - ./logs:/app/logs:rw          # Logs
  - ./test-reports:/app/test-reports:rw  # Test outputs
  - ./htmlcov:/app/htmlcov:rw    # Coverage reports
```

### Environment Variables

Development environment variables can be set in `docker-compose.override.yml`:

```yaml
services:
  app:
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
      - CUSTOM_SETTING=value
```

## Production Deployment

### Production Configuration

```bash
# Start production services
make docker-up-prod

# Or manually with production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Production Features

- **Security Hardening**: Read-only root filesystem, no new privileges
- **Resource Limits**: Memory and CPU constraints
- **Health Checks**: Automatic service health monitoring
- **Restart Policies**: Automatic restart on failure
- **Optimized Images**: Minimal attack surface

### Production Configuration Example

```yaml
services:
  app-prod:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
      - /app/logs
```

## CI/CD Integration

### GitHub Actions with Docker

The project includes a Docker-based CI workflow (`.github/workflows/ci-docker.yml`):

```bash
# Jobs included:
# 1. docker-validation     - Validate Docker setup
# 2. docker-build         - Build all images
# 3. code-quality-docker  - Code quality in Docker
# 4. unit-tests-docker    - Unit tests (sequential + parallel)
# 5. functional-tests-docker - Functional tests with Ollama
# 6. llm-evaluation-docker - LLM evaluation tests
# 7. conversation-chain-docker - Conversation chain tests
# 8. dynamic-conversation-docker - Dynamic conversation tests
# 9. production-readiness-docker - Production image testing
# 10. docker-quality-gate - Final validation
```

### Local CI Testing

```bash
# Test the complete CI pipeline locally
make docker-ci

# Test individual CI components
make docker-test-unit
make docker-test-functional
make docker-test-llm-eval

# Setup CI environment
make docker-ci-setup
```

## Environment Configurations

### Development (docker-compose.override.yml)

```yaml
# Automatically loaded in development
# Features:
# - Port binding for debugging
# - Volume mounts for hot reload
# - Debug environment variables
# - Interactive terminal support
```

### Production (docker-compose.prod.yml)

```yaml
# Production-specific overrides
# Features:
# - Resource limits
# - Security hardening
# - Health checks
# - Restart policies
# - Read-only filesystems
```

### CI (docker-compose.ci.yml)

```yaml
# CI-optimized configuration
# Features:
# - Fast builds with cache
# - Parallel test execution
# - Minimal resource usage
# - Comprehensive reporting
```

## Networking

### Network Architecture

```yaml
networks:
  semantic-kernel-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16  # Production only
```

### Service Communication

- **Internal**: Services communicate via Docker network
- **External**: Only necessary ports exposed to host
- **Ollama**: Accessible at `http://ollama:11434` internally, `http://localhost:11434` externally

## Volume Management

### Named Volumes

```yaml
volumes:
  ollama_data:
    driver: local  # Persistent Ollama models and data
```

### Bind Mounts

- **Development**: Source code, logs, reports mounted for real-time access
- **Production**: Minimal mounts for logs and essential data only

## Monitoring and Debugging

### Container Health

```bash
# Check container health
make docker-health

# View detailed container information
docker-compose ps --format table

# Check specific service logs
docker-compose logs -f ollama
docker-compose logs -f app
```

### Resource Monitoring

```bash
# Monitor resource usage
make docker-stats

# Check container processes
docker-compose top

# Inspect volumes
docker volume inspect semantic-evaluation-lab_ollama_data
```

### Debugging

```bash
# Access container shell
make docker-shell

# Debug specific service
docker-compose --profile dev exec app bash
docker-compose --profile dev exec ollama bash

# View container configuration
docker-compose config

# Inspect service health
docker inspect semantic-kernel-app --format='{{json .State.Health}}'
```

## Troubleshooting

### Common Issues

#### 1. Port Conflicts

```bash
# Error: Port 11434 already in use
Problem: Another Ollama instance running
Solution: 
docker-compose down
sudo pkill ollama  # If running system Ollama
make docker-up
```

#### 2. Model Download Issues

```bash
# Error: Failed to pull model
Problem: Network issues or insufficient disk space
Solution:
docker-compose --profile setup logs ollama-setup
docker system df  # Check disk usage
make docker-clean  # Free up space
```

#### 3. Permission Issues

```bash
# Error: Permission denied writing to volume
Problem: User permissions in container
Solution:
# Fix volume ownership
sudo chown -R $USER:$USER logs/ test-reports/ htmlcov/
```

#### 4. Memory Issues

```bash
# Error: Container killed (OOMKilled)
Problem: Insufficient memory
Solution:
# Check memory usage
docker stats
# Increase Docker memory allocation
# Or use smaller models in Ollama
```

### Reset and Cleanup

```bash
# Stop all services
make docker-down

# Clean up resources
make docker-clean        # Remove containers, networks
make docker-clean-all    # Remove everything including images
make docker-reset        # Complete reset and rebuild

# Clean up volumes (caution: removes all data)
docker volume prune -f
```

### Performance Optimization

#### 1. Build Optimization

```bash
# Use BuildKit for faster builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Use build cache
docker build --cache-from semantic-kernel:dev .
```

#### 2. Resource Allocation

```bash
# Adjust Docker Desktop settings:
# - Memory: 8GB minimum, 16GB recommended
# - CPU: 4 cores minimum
# - Disk: 20GB for development
```

#### 3. Image Optimization

```bash
# Check image layers
docker history semantic-kernel:prod

# Remove unused images
docker image prune -f

# Multi-stage builds already optimized for size
```

## Security Considerations

### Container Security

- **Non-root user**: All containers run as `appuser`
- **Read-only filesystem**: Production containers use read-only root
- **No new privileges**: Security option prevents privilege escalation
- **Resource limits**: Prevent resource exhaustion attacks

### Network Security

- **Isolated networks**: Services communicate on isolated Docker networks
- **Minimal exposure**: Only necessary ports exposed to host
- **Internal communication**: Services use internal DNS for communication

### Secrets Management

```bash
# Use environment variables for secrets
OPENAI_API_KEY=your-key docker-compose up

# Or use Docker secrets (Swarm mode)
echo "your-api-key" | docker secret create openai_key -
```

## Advanced Usage

### Custom Images

```dockerfile
# Extend base image for custom requirements
FROM semantic-kernel:dev

# Add custom dependencies
RUN pip install additional-package

# Add custom configuration
COPY custom-config.py /app/
```

### Multi-Environment Setup

```bash
# Development
docker-compose up -d

# Staging
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Integration with External Services

```yaml
# Add external database
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: semantic_kernel
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - semantic-kernel-network
```

## Best Practices

### Development

1. **Use profiles**: Organize services with Docker Compose profiles
2. **Volume mounts**: Use bind mounts for development, named volumes for data
3. **Environment files**: Use `.env` files for configuration
4. **Health checks**: Implement health checks for all services
5. **Resource limits**: Set appropriate resource limits

### Testing

1. **Isolated environments**: Each test type has its own service configuration
2. **Parallel execution**: Use parallel testing where possible
3. **Artifact collection**: Preserve test results and reports
4. **Cleanup**: Clean up test resources after execution

### Production

1. **Security hardening**: Use read-only filesystems and security options
2. **Resource management**: Set memory and CPU limits
3. **Monitoring**: Implement health checks and logging
4. **Backup strategy**: Regular backup of persistent volumes
5. **Update strategy**: Plan for container and image updates

## Migration Guide

### From Local Development

```bash
# If you were running locally:
# 1. Stop local services
pkill -f ollama
pkill -f jupyter

# 2. Start Docker environment
make docker-dev

# 3. Migrate data (if needed)
cp -r local-logs/ logs/
cp -r local-reports/ test-reports/
```

### To Production

```bash
# 1. Build production images
make docker-build-prod

# 2. Test production locally
make docker-up-prod

# 3. Deploy to production environment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Support and Resources

### Getting Help

1. **Check logs**: Always start with `make docker-logs`
2. **Validate configuration**: Use `make docker-validate`
3. **Check health**: Use `make docker-health`
4. **Review documentation**: This guide and Docker Compose files
5. **Community resources**: Docker documentation and forums

### Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Ollama Docker Guide](https://ollama.ai/docs/docker)
- [Semantic Kernel Documentation](https://learn.microsoft.com/en-us/semantic-kernel/)
- [DeepEval Documentation](https://docs.confident-ai.com/)

---

## Summary

The Docker setup provides:

✅ **Consistent Environments**: Same setup across development, testing, and production  
✅ **Isolated Dependencies**: No conflicts with local system  
✅ **Easy Reproduction**: One command to reproduce any environment  
✅ **Scalable Testing**: Parallel test execution with isolated services  
✅ **Production Ready**: Security hardened with resource management  
✅ **CI/CD Integration**: Complete pipeline automation  
✅ **Developer Friendly**: Hot reload, debugging, and interactive tools  

**Ready for enterprise-grade AI application development with Docker!** 

# Check Docker volumes
docker volume ls | grep ollama
docker volume inspect semantic-evaluation-lab_ollama_data

# Clean volumes if needed
docker volume rm semantic-evaluation-lab_ollama_data 