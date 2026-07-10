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
	# Filter to lines that look like ``target: ## description`` and
	# are NOT comments — header prose like "# Why a separate section:
	# the e2e suite" used to leak into help output once the project
	# grew past 30 targets.
	#
	# ``0-9`` MUST be in the char class — e2e-* targets contain a
	# digit and were silently dropped by the original ``[a-zA-Z_-]+``
	# regex. That bug shipped in phase 0 and survived every refactor
	# because nobody actually scrolled through ``make help`` until
	# the e2e section landed. Caught today, never again.
	@awk '/^[a-zA-Z0-9_-]+:.*##/ && !/^#/ {split($$0, a, ":.*## "); printf "  \033[36m%-20s\033[0m %s\n", a[1], a[2]}' $(MAKEFILE_LIST)
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
#
# DEBUG defaults ON — operators expect to see HTTP requests, SQL,
# and LLM round-trips when they run a local dev backend. To get the
# silent prod-style behaviour, run ``make dev-backend-quiet``.
# Override any value with ``DEBUG=false make dev-backend`` etc.
.PHONY: dev-backend
dev-backend: export DEBUG ?= true
dev-backend: export ENVIRONMENT ?= development
dev-backend: export LOG_LEVEL ?= DEBUG
dev-backend: ## Start backend in background (DEBUG on by default), write logs to logs/backend.log
	@mkdir -p logs
	@if [ -f .backend.pid ] && kill -0 $$(cat .backend.pid) 2>/dev/null; then \
	  echo "[backend] already running (PID $$(cat .backend.pid)) — DEBUG=$$DEBUG LOG_LEVEL=$$LOG_LEVEL"; \
	else \
	  echo "[backend] starting with DEBUG=$$DEBUG LOG_LEVEL=$$LOG_LEVEL ENVIRONMENT=$$ENVIRONMENT"; \
	  $(PY) backend/run_backend.py > logs/backend.log 2>&1 & \
	  echo $$! > .backend.pid; \
	  echo "[backend] started (PID $$(cat .backend.pid)) — logs at logs/backend.log"; \
	fi

# Same as ``dev-backend`` but flips DEBUG off (matches what
# ``make build`` / the Tauri-bundled binary will do at runtime).
# Useful for verifying behaviour under prod-like settings without
# rebuilding.
.PHONY: dev-backend-quiet
dev-backend-quiet: export DEBUG := false
dev-backend-quiet: export LOG_LEVEL := INFO
dev-backend-quiet: ## Start backend in background with DEBUG off (prod-like)
	@mkdir -p logs
	@if [ -f .backend.pid ] && kill -0 $$(cat .backend.pid) 2>/dev/null; then \
	  echo "[backend] already running (PID $$(cat .backend.pid)) — DEBUG=$$DEBUG LOG_LEVEL=$$LOG_LEVEL"; \
	else \
	  echo "[backend] starting with DEBUG=$$DEBUG LOG_LEVEL=$$LOG_LEVEL ENVIRONMENT=$$ENVIRONMENT"; \
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
	  echo "[logs] no logs/backend.log yet — run \`make dev\` or \`make dev-debug\` first"; \
	  exit 1; \
	fi
	@tail -n +1 -f logs/backend.log | grep --line-buffered -E '"level":"(error|warning)"|ERROR|WARNING'

# Filter the live backend log for HTTP / SQL / LLM traffic.
# Operators care about three things when debugging:
#   - HTTP method/path/status/duration   → _access_log_dispatch
#   - SQL from SQLAlchemy + Alembic      → alembic.runtime + sqlalchemy.engine
#   - LLM round-trips                    → llm / openai-like logger names
# All three surface when ``LOG_LEVEL=DEBUG`` is set (dev-backend
# default since e2e phase 0).
.PHONY: logs-traffic
logs-traffic: ## Tail HTTP requests + SQL + LLM calls from the backend log
	@if [ ! -f logs/backend.log ]; then \
	  echo "[logs-traffic] no logs/backend.log yet — run \`make dev-backend\` first"; \
	  exit 1; \
	fi
	@tail -n +1 -f logs/backend.log | grep --line-buffered -E 'method=|alembic|sqlalchemy|llm|openai|chat_request|http'

# Stop the background backend started by `make dev-backend`.
#
# Why we probe both .backend.pid AND the live port: a previous
# teardown sometimes leaves an orphan process whose pid file
# has been cleaned up but which is still bound to :55245. Killing
# only via pidfile leaves it listening and breaks the next
# `dev-backend`. The lsof step catches that case before we give
# up.
#
# NB: do NOT auto-kill the lsof match — the process might be a
# user's manually-started dev backend (see AGENTS.md / memory
# PPID rule). We report it and let the operator decide.
.PHONY: stop-backend
stop-backend: ## Stop the background backend started by dev-backend
	@KILLED=0; \
	if [ -f .backend.pid ]; then \
	  PID=$$(cat .backend.pid); \
	  if kill -0 $$PID 2>/dev/null; then \
	    kill $$PID && echo "[backend] stopped (PID $$PID)"; \
	    KILLED=1; \
	  else \
	    echo "[backend] PID $$PID not running; cleaning pidfile"; \
	  fi; \
	  rm -f .backend.pid; \
	fi; \
	if [ $$KILLED -eq 0 ]; then \
	  STALE=$$(lsof -nP -i :55245 -t 2>/dev/null | head -1); \
	  if [ -n "$$STALE" ]; then \
	    echo "[backend] (warning) :55245 is held by PID $$STALE but no pidfile — left untouched"; \
	    echo "[backend] (warning) if this is not your manual dev backend, run:"; \
	    echo "[backend]   kill $$STALE"; \
	  else \
	    echo "[backend] no pidfile; nothing to stop"; \
	  fi; \
	fi

# ── Tests ─────────────────────────────────────────────────────

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

# ─── E2E (Playwright, real backend + real Vite) ─────────────────
#
# Why a separate section: the e2e suite
#   - talks to a real FastAPI on 127.0.0.1:55245 (not mocks)
#   - drives a real Vite dev server on 127.0.0.1:5173
#   - costs real LLM tokens when a chat test fires
#
# The backend fixture (frontend/e2e/fixtures/backend.ts) assumes
# the backend is already up. ``e2e-backend`` brings it up via
# ``make dev-backend`` (which writes .backend.pid); ``e2e``
# chains them together, and ``e2e-smoke`` chains ``e2e-smoke-only``
# for the @smoke slice.

.PHONY: e2e-backend
e2e-backend: ## Start the FastAPI backend that the e2e suite talks to
	$(MAKE) dev-backend
	@echo "[e2e] waiting for backend on :55245 ..."
	@for i in $$(seq 1 30); do \
	  if curl -fsS http://127.0.0.1:55245/api/health >/dev/null 2>&1; then \
	    echo "[e2e] backend ready"; exit 0; \
	  fi; \
	  sleep 1; \
	done; \
	echo "[e2e] backend did not become ready in 30 s" >&2; \
	exit 1

.PHONY: e2e-frontend-up
e2e-frontend-up: ## Start the Vite dev server the e2e suite drives
	@if ! curl -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then \
	  echo "[e2e] starting Vite on :5173 (one-shot, logs at frontend/e2e-vite.log)"; \
	  cd frontend && $(NPM) run dev -- --host 127.0.0.1 --port 5173 --strictPort \
	    > e2e-vite.log 2>&1 & \
	  echo $$! > ../.vite.pid; \
	  for i in $$(seq 1 30); do \
	    if curl -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then \
	      echo "[e2e] Vite ready"; exit 0; \
	    fi; \
	    sleep 1; \
	  done; \
	  echo "[e2e] Vite did not become ready in 30 s" >&2; \
	  exit 1; \
	else \
	  echo "[e2e] Vite already running on :5173"; \
	fi

.PHONY: e2e-frontend-down
e2e-frontend-down: ## Stop the Vite dev server started by e2e-frontend-up
	@if [ -f .vite.pid ]; then \
	  PID=$$(cat .vite.pid); \
	  if kill -0 $$PID 2>/dev/null; then \
	    kill $$PID && echo "[e2e] Vite stopped (PID $$PID)"; \
	    rm -f .vite.pid; \
	  else \
	    echo "[e2e] Vite PID $$PID not running; cleaning pidfile"; \
	    rm -f .vite.pid; \
	  fi; \
	else \
	  echo "[e2e] no .vite.pid; nothing to stop"; \
	fi

.PHONY: e2e-stack-up
e2e-stack-up: e2e-backend e2e-frontend-up ## Bring up backend + Vite for e2e

.PHONY: e2e-stack-down
e2e-stack-down: stop-backend e2e-frontend-down ## Tear down backend + Vite

.PHONY: e2e-install
e2e-install: ## Install Playwright browsers (chromium only)
	cd frontend && $(NPM) run e2e:install-browsers

.PHONY: e2e-smoke
e2e-smoke: ## Run only @smoke tests (~30 s, smoke coverage of the 5 critical journeys)
	$(MAKE) e2e-stack-up
	cd frontend && $(NPM) run e2e -- --grep '@smoke'
	E2E_EXIT=$$?; \
	$(MAKE) -s e2e-stack-down || true; \
	exit $$E2E_EXIT

.PHONY: e2e
e2e: ## Run full Playwright E2E suite (real backend + Vite, real LLM cost)
	$(MAKE) e2e-stack-up
	cd frontend && $(NPM) run e2e
	E2E_EXIT=$$?; \
	$(MAKE) -s e2e-stack-down || true; \
	exit $$E2E_EXIT

.PHONY: e2e-headed
e2e-headed: ## Run e2e with a visible browser window
	$(MAKE) e2e-stack-up
	cd frontend && $(NPM) run e2e:headed
	E2E_EXIT=$$?; \
	$(MAKE) -s e2e-stack-down || true; \
	exit $$E2E_EXIT

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
