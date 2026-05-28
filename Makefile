.PHONY: help setup install install-dev clean clean-cache lint format format-check type-check check shell info deps-outdated lock mvcc-internals

# Variables
PROJECT_NAME := "Relational Database Skills To Master Practical Labs"
PYTHON := python3
UV := uv
FLOX := flox activate --
SRC_DIR := labs
VENV := .venv

# Colors for help output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Default target
help: ## Show this help message
	@echo "$(BLUE)$(PROJECT_NAME) - Available Make Targets$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Notes:$(NC)"
	@echo "  • All commands run within flox environment"

##########################
##@ Setup & Installation
##########################

setup: ## Initialize project: create venv, install dependencies
	@echo "$(BLUE)Setting up project environment...$(NC)"
	@echo "$(GREEN)==> Creating Python virtual environment with uv...$(NC)"
	$(FLOX) $(UV) sync --all-packages
	@echo "$(GREEN)✓ Virtual environment created and dependencies installed$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Activate flox environment: eval \"\$$(flox activate)\""

install: ## Install/sync dependencies (after pyproject.toml changes)
	@echo "$(GREEN)==> Syncing dependencies...$(NC)"
	$(FLOX) $(UV) sync --all-packages

install-dev: ## Install with dev dependencies
	@echo "$(GREEN)==> Installing all dependencies including dev tools...$(NC)"
	$(FLOX) $(UV) sync --all-groups --all-packages

##################
##@ Code Quality
##################

lint: ## Run ruff linter
	@echo "$(GREEN)==> Running ruff linter...$(NC)"
	$(FLOX) $(UV) run ruff check $(SRC_DIR) $(TEST_DIR)

format: ## Format code with ruff
	@echo "$(GREEN)==> Formatting code with ruff...$(NC)"
	$(FLOX) $(UV) run ruff format $(SRC_DIR) $(TEST_DIR)
	$(FLOX) $(UV) run ruff check --fix $(SRC_DIR) $(TEST_DIR)

format-check: ## Check code formatting without modifying files
	@echo "$(GREEN)==> Checking code formatting...$(NC)"
	$(FLOX) $(UV) run ruff format --check $(SRC_DIR) $(TEST_DIR)

type-check: ## Run mypy type checker
	@echo "$(GREEN)==> Running mypy type checker...$(NC)"
	@for dir in labs/*; do \
		if [ -d "$$dir/app" ]; then \
			MYPYPATH=$$dir $(FLOX) $(UV) run mypy --explicit-package-bases $$dir/app || exit 1; \
		fi; \
	done

check: format-check lint type-check ## Run all code quality checks (format, lint, type)

##################
##@ Development
##################

shell: ## Start Python shell with project context
	@echo "$(GREEN)==> Starting Python shell...$(NC)"
	$(FLOX) $(UV) run python

##################
##@ Practical Labs
##################

mvcc-internals: ## Run the MVCC Internals lab bootstrap script
	@echo "$(GREEN)==> Running MVCC Internals Lab...$(NC)"
	$(FLOX) $(UV) run labs/001-mvcc-internals/main.py

##################
##@ Cleanup
##################

clean: ## Remove build artifacts, cache files, and venv
	@echo "$(GREEN)==> Cleaning build artifacts...$(NC)"
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-cache: ## Remove only cache files (keep venv)
	@echo "$(GREEN)==> Cleaning cache files...$(NC)"
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -path ./$(VENV) -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -path ./$(VENV) -prune -o -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -path ./$(VENV) -prune -o -type f -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
	find . -path ./$(VENV) -prune -o -type f -name "*.pyo" -exec rm -f {} + 2>/dev/null || true
	find . -path ./$(VENV) -prune -o -type f -name "*.egg" -exec rm -f {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cache cleanup complete$(NC)"

##################
##@ Utilities
##################

info: ## Display project information
	@echo "$(BLUE)Project Information$(NC)"
	@echo "  Name: $(PROJECT_NAME)"
	@echo "  Python: $(shell $(FLOX) python --version 2>/dev/null || echo 'Not in flox env')"
	@echo "  UV: $(shell $(FLOX) uv --version 2>/dev/null || echo 'Not in flox env')"
	@echo "  Virtual Environment: $(VENV)"
	@echo ""
	@echo "$(BLUE)Installed Packages$(NC)"
	@$(FLOX) $(UV) pip list 2>/dev/null || echo "  Run '$(GREEN)make setup$(NC)' first"

deps-outdated: ## Check for outdated dependencies
	@echo "$(GREEN)==> Checking for outdated dependencies...$(NC)"
	$(FLOX) $(UV) pip list --outdated

lock: ## Regenerate uv.lock file
	@echo "$(GREEN)==> Regenerating lock file...$(NC)"
	$(FLOX) $(UV) lock