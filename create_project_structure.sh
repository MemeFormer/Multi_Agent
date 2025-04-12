#!/bin/bash

# Script to create the initial directory and file structure for the
# multi-agent-code-refactoring project within the current directory.

PROJECT_ROOT="multi-agent-code-refactoring"

echo "Creating project structure under './${PROJECT_ROOT}'..."

# --- Create Directories ---
# Use -p to create parent directories as needed and avoid errors if they exist.
mkdir -p "${PROJECT_ROOT}/src/agents"
mkdir -p "${PROJECT_ROOT}/src/operations"
mkdir -p "${PROJECT_ROOT}/src/models"
mkdir -p "${PROJECT_ROOT}/src/adapters"
mkdir -p "${PROJECT_ROOT}/src/utils"
mkdir -p "${PROJECT_ROOT}/config"
mkdir -p "${PROJECT_ROOT}/tests"
mkdir -p "${PROJECT_ROOT}/examples"

echo "Directories created."

# --- Create Files ---
# Use touch to create empty files.
touch "${PROJECT_ROOT}/src/__init__.py"
touch "${PROJECT_ROOT}/src/main.py"

touch "${PROJECT_ROOT}/src/agents/__init__.py"
touch "${PROJECT_ROOT}/src/agents/junior_engineer.py"
touch "${PROJECT_ROOT}/src/agents/senior_engineer.py"
touch "${PROJECT_ROOT}/src/agents/agent_factory.py"

touch "${PROJECT_ROOT}/src/operations/__init__.py"
touch "${PROJECT_ROOT}/src/operations/file_operations.py"
touch "${PROJECT_ROOT}/src/operations/code_operations.py"

touch "${PROJECT_ROOT}/src/models/__init__.py"
touch "${PROJECT_ROOT}/src/models/execution_plan.py"
touch "${PROJECT_ROOT}/src/models/review_feedback.py"
touch "${PROJECT_ROOT}/src/models/modification.py"

touch "${PROJECT_ROOT}/src/adapters/__init__.py"
touch "${PROJECT_ROOT}/src/adapters/groq_adapter.py"
touch "${PROJECT_ROOT}/src/adapters/command_adapter.py"

touch "${PROJECT_ROOT}/src/utils/__init__.py"
touch "${PROJECT_ROOT}/src/utils/json_utils.py"
touch "${PROJECT_ROOT}/src/utils/code_parser.py"
touch "${PROJECT_ROOT}/src/utils/profiling.py"

# Config files
touch "${PROJECT_ROOT}/config/models.json"
touch "${PROJECT_ROOT}/config/operations.json"

# Test files (add __init__.py for potential test discovery)
touch "${PROJECT_ROOT}/tests/__init__.py"
touch "${PROJECT_ROOT}/tests/test_junior_engineer.py"
touch "${PROJECT_ROOT}/tests/test_senior_engineer.py"
touch "${PROJECT_ROOT}/tests/test_file_operations.py"
touch "${PROJECT_ROOT}/tests/test_integration.py"

# Example files
touch "${PROJECT_ROOT}/examples/simple_fix.py"
touch "${PROJECT_ROOT}/examples/refactoring.py"
touch "${PROJECT_ROOT}/examples/dependency_update.py"

# Root files
touch "${PROJECT_ROOT}/README.md"
touch "${PROJECT_ROOT}/requirements.txt"
touch "${PROJECT_ROOT}/setup.py"
touch "${PROJECT_ROOT}/.gitignore"

echo "Empty files created."

# --- Add Basic Content ---
echo "# Multi-Agent Code Refactoring" > "${PROJECT_ROOT}/README.md"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/agents/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/operations/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/models/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/adapters/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/src/utils/__init__.py"
echo "# -*- coding: utf-8 -*-" > "${PROJECT_ROOT}/tests/__init__.py"

echo "# Add project dependencies here" > "${PROJECT_ROOT}/requirements.txt"
echo "# Example: groq" >> "${PROJECT_ROOT}/requirements.txt"
echo "# Example: pydantic" >> "${PROJECT_ROOT}/requirements.txt"

echo '{ "default_model": "llama3-70b-8192", "available_models": ["llama3-70b-8192", "llama-3.3-70b-versatile"] }' > "${PROJECT_ROOT}/config/models.json"
echo '{ "available_operations": ["read_file", "write_file", "list_files"] }' > "${PROJECT_ROOT}/config/operations.json"

# Basic .gitignore content
echo "__pycache__/" > "${PROJECT_ROOT}/.gitignore"
echo "*.pyc" >> "${PROJECT_ROOT}/.gitignore"
echo "*.pyo" >> "${PROJECT_ROOT}/.gitignore"
echo "*.pyd" >> "${PROJECT_ROOT}/.gitignore"
echo "" >> "${PROJECT_ROOT}/.gitignore"
echo ".env" >> "${PROJECT_ROOT}/.gitignore"
echo "venv/" >> "${PROJECT_ROOT}/.gitignore"
echo ".venv/" >> "${PROJECT_ROOT}/.gitignore"
echo "" >> "${PROJECT_ROOT}/.gitignore"
echo "build/" >> "${PROJECT_ROOT}/.gitignore"
echo "dist/" >> "${PROJECT_ROOT}/.gitignore"
echo "*.egg-info/" >> "${PROJECT_ROOT}/.gitignore"
echo "" >> "${PROJECT_ROOT}/.gitignore"
echo ".DS_Store" >> "${PROJECT_ROOT}/.gitignore"
echo "*.log" >> "${PROJECT_ROOT}/.gitignore"

echo "Added placeholder content to key files."

# --- Final Message ---
echo "--------------------------------------------------"
echo "Project structure for '${PROJECT_ROOT}' created successfully inside '$(pwd)'."
echo "Next steps:"
echo "1. Review the created structure: ls -R ${PROJECT_ROOT}"
echo "2. Add these files to Git:"
echo "   git add ${PROJECT_ROOT}/"
echo "   git add create_project_structure.sh # Optional: track the script itself"
echo "3. Commit the changes:"
echo "   git commit -m \"Initial project structure setup\""
echo "4. Push to your remote repository:"
echo "   git push origin main" # Or your default branch name
echo "--------------------------------------------------"
