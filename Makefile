# ──────────────────────────────────────────────────────────────────
#  Roleplay Studio — Makefile
#  Common dev / build / test / lint entry points.
#  Run `make` or `make help` for the full list of targets.
# ──────────────────────────────────────────────────────────────────

# Backend (FastAPI + Hypercorn) runs on this port. Tauri and the
# Vite dev server both expect it here — do not change without
# updating frontend/src/lib/api.ts (API_BASE).
BACKEND_PORT := 55245
BACKEND_HOST := 127.0.0.1

# `.venv/bin/python` is the canonical interpreter (created by uv
# or python -m venv). We don't shell out to plain `python` so the
# target works inside CI and on developer machines alike.
PY := .venv/bin/python
NPM := npm

.DEFAULT_GOAL := help

# ─── Help ──────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo "Roleplay Studio — available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Tip: most targets also have a :-backend / :-frontend variant."

# ─── Install ───────────────────────────────────────────────────────

.PHONY: install
install: ## Install backend + frontend dependencies
	$(MAKE) install-backend
	$(MAKE) install-frontend

.PHONY: install-backend
install-backend: ## Set up Python venv and install backend deps
	uv sync
	uv pip install --python $(PY) -e ".[test]"

.PHONY: install-frontend
install-frontend: ## Install frontend npm deps
	cd frontend && $(NPM) install

# ─── Dev (full stack) ──────────────────────────────────────────────
#
#  `make dev`      — production-like: backend in prod mode, Tauri desktop
#  `make dev-debug`— everything `dev` does, PLUS backend runs with
#                    DEBUG=true so the LLM debug modal is enabled.

.PHONY: dev
dev: ## Run backend (prod mode) + Tauri desktop in one command
	$(MAKE) dev-backend
	$(MAKE) dev-tauri

# `dev-debug` keeps the backend in the FOREGROUND so Python logger
# output (structlog + uvicorn + our own loggers) streams straight to
# the terminal. The previous design backgrounded the backend and
# piped to ``logs/backend.log``, which was fine for a quick ``make
# dev`` smoke test but made ``dev-debug`` useless for live error
# triage — you'd have to alt-tab into another terminal and tail
# the file. Now the tail is the terminal you're in.
#
# Tauri stays in the background because it opens a window and would
# otherwise block this Make target from returning. If you need the
# backend logs even *after* Tauri takes over the screen, run
# ``make logs`` in another shell to follow the file.
.PHONY: dev-debug
dev-debug: export DEBUG := true
dev-debug: export ENVIRONMENT := development
dev-debug: ## Run backend in FOREGROUND (DEBUG=true) + Tauri in background
	$(MAKE) -j2 dev-backend-debug-fg dev-tauri

# Foreground backend variant for ``dev-debug`` (live Python logger
# output in the terminal). Unlike ``dev-backend`` it does not
# background the process and does not write a pidfile — when you
# Ctrl-C this make target, the backend dies with the make process
# and you can rerun cleanly.
.PHONY: dev-backend-debug-fg
dev-backend-debug-fg: ## Start backend in foreground (live logs) — used by dev-debug
	@mkdir -p logs
	@echo "[backend] starting in foreground (DEBUG=$(DEBUG) ENVIRONMENT=$(ENVIRONMENT)) — Ctrl-C to stop"
	@$(PY) backend/run_backend.py 2>&1 | tee logs/backend.log

.PHONY: dev-tauri
dev-tauri: ## Run Tauri desktop (assumes backend is already up)
	cd frontend && npx tauri dev

.PHONY: dev-frontend
dev-frontend: ## Run Vite dev server only (no Tauri, browser-only)
	cd frontend && $(NPM) run dev

# Start backend in the background. Writes PID to .backend.pid so
# `make stop` can kill it cleanly. Logs go to logs/backend.log.
.PHONY: dev-backend
dev-backend: ## Start backend in background, write logs to logs/backend.log
	@mkdir -p logs
	@if [ -f .backend.pid ] && kill -0 $$(cat .backend.pid) 2>/dev/null; then \
	  echo "[backend] already running (PID $$(cat .backend.pid))"; \
	else \
	  $(PY) backend/run_backend.py > logs/backend.log 2>&1 & \
	  echo $$! > .backend.pid; \
	  echo "[backend] started (PID $$(cat .backend.pid)) — logs at logs/backend.log"; \
	fi

# Follow the live backend log without restarting the server. Useful
# in a second terminal while ``make dev`` is running, or for
# post-mortem after a crash.
.PHONY: logs
logs: ## Tail the backend log (Ctrl-C to stop following)
	@if [ ! -f logs/backend.log ]; then \
	  echo "[logs] no logs/backend.log yet — run \`make dev\` or \`make dev-debug\` first"; \
	  exit 1; \
	fi
	@tail -n +1 -f logs/backend.log

# Same as ``logs`` but only ERROR / WARNING lines — useful when
# you want to spot-check for failures without scrolling through
# the whole stream.
.PHONY: logs-errors
logs-errors: ## Tail only ERROR/WARNING lines from the backend log
	@if [ ! -f logs/backend.log ]; then \
	  echo "[logs-errors] no logs/backend.log yet — run \`make dev\` or \`make dev-debug\` first"; \
	  exit 1; \
	fi
	@tail -n +1 -f logs/backend.log | grep --line-buffered -E '"level":"(error|warning)"|ERROR|WARNING'

# Stop the background backend started by `make dev-backend`.
.PHONY: stop-backend
stop-backend: ## Stop the background backend started by dev-backend
	@if [ -f .backend.pid ]; then \
	  PID=$$(cat .backend.pid); \
	  if kill -0 $$PID 2>/dev/null; then \
	    kill $$PID && echo "[backend] stopped (PID $$PID)"; \
	    rm -f .backend.pid; \
	  else \
	    echo "[backend] PID $$PID not running; cleaning pidfile"; \
	    rm -f .backend.pid; \
	  fi; \
	else \
	  echo "[backend] no pidfile; nothing to stop"; \
	fi

# ─── Tests ─────────────────────────────────────────────────────────

.PHONY: test
test: ## Run all tests (backend + frontend)
	$(MAKE) test-backend
	$(MAKE) test-frontend

.PHONY: test-backend
test-backend: ## Run backend pytest suite
	$(PY) -m pytest

.PHONY: test-frontend
test-frontend: ## Run frontend vitest suite
	cd frontend && $(NPM) run test

# ─── Lint / Format / Type-check ────────────────────────────────────

.PHONY: lint
lint: ## Lint backend (ruff) + frontend (eslint)
	$(MAKE) lint-backend
	$(MAKE) lint-frontend

.PHONY: lint-backend
lint-backend: ## Run ruff check on backend
	ruff check .

.PHONY: lint-frontend
lint-frontend: ## Run eslint on frontend
	cd frontend && $(NPM) run lint

.PHONY: lint-fix
lint-fix: ## Auto-fix lint issues (backend + frontend)
	ruff check --fix .
	cd frontend && $(NPM) run lint:fix

.PHONY: format
format: ## Check formatting (backend + frontend)
	ruff format --check .
	cd frontend && $(NPM) run format

.PHONY: format-fix
format-fix: ## Auto-format everything
	ruff format .
	cd frontend && $(NPM) run format:fix

.PHONY: check
check: ## Type-check frontend (svelte-check)
	cd frontend && $(NPM) run check

# ─── Pre-commit ────────────────────────────────────────────────────

.PHONY: precommit
precommit: ## Run pre-commit on all staged files
	pre-commit run --all-files

# ─── Build ─────────────────────────────────────────────────────────

.PHONY: build
build: ## Build production artifacts (frontend + backend)
	$(MAKE) build-frontend
	$(MAKE) build-backend

# Default Tauri output path. Matches tauri.conf.json productName —
# spaces in the bundle name are kept verbatim (Tauri does the same).
TAURI_DMG_PATH := frontend/src-tauri/target/release/bundle/dmg/Roleplay Studio_0.1.0_aarch64.dmg

.PHONY: build-dmg
build-dmg:
	cd frontend && $(NPM) run tauri build

.PHONY: install-dmg
install-dmg: ## Install the freshly-built .dmg to /Applications, stripping Gatekeeper quarantine
	@if [ ! -f "$(TAURI_DMG_PATH)" ]; then \
		echo "❌ $(TAURI_DMG_PATH) not found. Run \`make build\` first."; \
		exit 1; \
	fi
	bash scripts/install.sh "$(TAURI_DMG_PATH)"

.PHONY: build-frontend
build-frontend: ## Build frontend (Vite)
	cd frontend && $(NPM) run build

.PHONY: build-backend
build-backend: ## Build backend binary (PyInstaller)
	$(PY) -m PyInstaller backend/run_backend.spec

# ─── Clean ─────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove build artifacts, caches, and the background backend
	$(MAKE) clean-frontend
	$(MAKE) clean-backend
	$(MAKE) stop-backend
	rm -rf logs/ .backend.pid

.PHONY: clean-frontend
clean-frontend: ## Remove frontend build artifacts
	cd frontend && rm -rf node_modules .svelte-kit dist build .vite

.PHONY: clean-backend
clean-backend: ## Remove backend build artifacts and Python caches
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -not -path '*/\.venv/*' -exec rm -rf {} + 2>/dev/null || true
