.PHONY: build test test-integration lint up down status clean cli eval eval-sweep eval-ci

# ── Docker Compose ───────────────────────────────────────────────
up:
	docker compose up -d --build --remove-orphans

down:
	docker compose down -v --remove-orphans

status:
	@echo "=== KubeMind Status ==="
	@docker compose ps
	@echo ""
	@echo "Health checks:"
	@curl -s http://localhost:9080/health || echo "router: DOWN"
	@curl -s http://localhost:9081/health || echo "mind: DOWN"
	@curl -s http://localhost:9082/health || echo "agents: DOWN"
	@curl -s http://localhost:9083/health || echo "sentinel: DOWN"

logs:
	docker compose logs -f $(SERVICE)

sentinel:
	docker compose logs -f sentinel

# ── Build ────────────────────────────────────────────────────────
build:
	@echo "Building services..."
	@# router and sentinel build from the repo root so shared/ is in context
	docker build -f services/router/Dockerfile -t kubemind/router .
	docker build -f services/sentinel/Dockerfile -t kubemind/sentinel .
	cd services/mind && docker build -t kubemind/mind .
	cd services/agents && docker build -t kubemind/agents .
	cd dashboard && docker build -t kubemind/dashboard .
	@echo "Building CLI (kmind)..."
	$(MAKE) cli

cli:
	mkdir -p bin
	cd cmd/tricore && go build -o ../../bin/kmind .
	@# Transitional alias for scripts still calling tricore
	cd bin && ln -sfn kmind tricore

# ── Testing ──────────────────────────────────────────────────────
test:
	@echo "Running unit tests..."
	cd services/router && pytest tests/ -v
	cd services/mind && pytest tests/ -v
	cd services/agents && pytest tests/ -v
	cd services/sentinel && pytest tests/ -v

test-integration:
	@echo "Running integration tests (requires running stack)..."
	cd tests/integration && pytest -v

# ── Intent evaluation ────────────────────────────────────────────
# Scores the classifier against a held-out labelled set. Falls back to
# rules-only when no embedder is reachable, so it runs anywhere.
eval:
	cd services/router && python3 eval/run_eval.py

# Accuracy versus abstention across thresholds. Pick an operating point from
# this table rather than guessing a number.
eval-sweep:
	cd services/router && python3 eval/run_eval.py --sweep

# CI gate: a policy miss means sensitive content was under-enforced.
eval-ci:
	cd services/router && python3 eval/run_eval.py --fail-on-policy-miss

# ── Linting ──────────────────────────────────────────────────────
lint:
	@echo "Linting Python services..."
	cd services/router && ruff check src/ && mypy src/
	cd services/mind && ruff check src/ && mypy src/
	cd services/agents && ruff check src/ && mypy src/
	cd services/sentinel && ruff check src/ && mypy src/
	@echo "Linting Go CLI..."
	cd cmd/tricore && go vet ./...
	@echo "Linting Dashboard..."
	cd dashboard && npx next lint

# ── Cleanup ──────────────────────────────────────────────────────
clean:
	docker compose down -v
	docker system prune -f
	rm -rf bin/ services/*/src/__pycache__ services/*/.mypy_cache
