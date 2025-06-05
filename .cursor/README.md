# 🎯 Cursor IDE Configuration

This folder contains Cursor IDE-specific configuration files to enhance the development experience for the Semantic Kernel Learning Project.

## 📁 Files Overview

### 🔧 `settings.json`
**Purpose**: Cursor IDE workspace settings optimized for Python development with Semantic Kernel

**Key Features**:
- **Python Configuration**: Black formatter, Flake8 linting, MyPy type checking
- **Line Length**: 88 characters (Black standard)
- **Auto-formatting**: Format on save with import organization
- **Virtual Environment**: Automatic activation and PYTHONPATH setup
- **File Exclusions**: Hide cache files, virtual environments, and build artifacts
- **Mermaid Support**: Enhanced preview for diagram rendering

### 📋 `rules`
**Purpose**: Comprehensive coding standards and constraints for the project

**Covers**:
- **Python Style Guidelines**: PEP 8, type hints, async patterns
- **File Organization**: Configuration management, error handling
- **Security Constraints**: Environment variables, API key protection
- **Code Quality**: Function length, naming conventions, best practices
- **Anti-Patterns**: Common mistakes to avoid

### 🤖 `instructions`
**Purpose**: Detailed guidelines for AI assistants working on this project

**Includes**:
- **Project Context**: Technology stack, configuration system
- **Development Guidelines**: Provider support, async patterns, error handling
- **Code Examples**: Configuration patterns, error handling, provider-agnostic code
- **Response Guidelines**: Code style, explanation format, debugging approaches

### 🎨 `composer.md`
**Purpose**: Specific guidelines for Cursor Composer AI assistance

**Features**:
- **Project-Specific Rules**: Configuration management, dual provider support
- **Code Patterns**: Import structure, provider-agnostic implementation
- **File Modification Guidelines**: Specific rules for editing key files
- **Quality Standards**: Python style, async programming, error messages
- **Security Requirements**: Environment variables, default configuration

## 🚀 Benefits

### For Developers:
- **Consistent Code Style**: Automatic formatting and linting
- **Enhanced Productivity**: Smart auto-completion and type checking
- **Better Navigation**: File exclusions and search optimization
- **Environment Management**: Automatic virtual environment handling

### For AI Assistants:
- **Project Understanding**: Clear context about technologies and patterns
- **Consistent Output**: Standardized code patterns and error handling
- **Quality Assurance**: Built-in validation and best practice enforcement
- **Educational Focus**: Emphasis on learning and understanding

### For Collaboration:
- **Shared Standards**: Everyone follows the same coding guidelines
- **Reduced Friction**: Automatic formatting prevents style debates
- **Quality Control**: Linting and type checking catch issues early
- **Documentation**: Clear patterns and examples for reference

## 🎯 Key Principles

### Configuration-First Development
- Never hardcode sensitive values
- Always use environment variables with validation
- Support both Ollama (local) and Azure OpenAI (cloud) seamlessly

### Educational Focus
- Code should be self-explanatory and well-documented
- Include helpful error messages with solutions
- Prioritize clarity over performance optimization

### Async-First Approach
- All AI operations use async/await patterns
- Proper exception handling for async operations
- Clean separation of sync and async code

### Security by Default
- Default to local Ollama (no cloud credentials needed)
- Validate all inputs and configuration
- Never log sensitive information

## 🔄 Usage

These configuration files work automatically when you:

1. **Open the project** in Cursor IDE
2. **Install recommended extensions** (Python, Black, Flake8)
3. **Create a virtual environment** in the project root
4. **Start coding** - formatting and linting happen automatically

The AI assistants will automatically follow the guidelines in `instructions` and `composer.md` when helping with code.

## 🛠️ Customization

Feel free to modify these files to match your team's preferences:

- **Adjust line length** in `settings.json` if needed
- **Add new rules** to the `rules` file for project-specific patterns
- **Update instructions** for new technologies or patterns
- **Extend composer guidelines** for additional use cases

Remember: These configurations are designed to support the dual-provider architecture (Ollama + Azure OpenAI) and educational nature of this project. 