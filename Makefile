.PHONY: build test test-integration lint typecheck security ci up down status clean cli eval eval-sweep eval-calibrate eval-ci eval-train-linear demo helm-template start stop restart status-all seed backup verify-ledger

# ── Stack Orchestration Scripts ──────────────────────────────────
start:
	./scripts/start_all.sh

stop:
	./scripts/stop_all.sh

restart:
	./scripts/restart_all.sh

status-all:
	./scripts/status_all.sh

seed:
	./scripts/seed_demo_data.sh

verify-ledger:
	./scripts/verify_ledger.sh

# ── Docker Compose ───────────────────────────────────────────────
up:
	./scripts/start_all.sh --build

down:
	./scripts/stop_all.sh -v

status:
	./scripts/status_all.sh

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
	cd cmd/kmind && go build -o ../../bin/kmind .
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

test-e2e:
	@echo "Running end-to-end system verification tests..."
	PYTHONPATH="shared/python:$$PYTHONPATH" pytest tests/e2e -v

# ── Intent evaluation ────────────────────────────────────────────
# Scores the classifier against a held-out labelled set. Falls back to
# rules-only when no embedder is reachable, so it runs anywhere.
eval:
	cd services/router && python3 eval/run_eval.py

# Accuracy versus abstention across thresholds. Pick an operating point from
# this table rather than guessing a number.
eval-sweep:
	cd services/router && python3 eval/run_eval.py --sweep

# Fit the softmax temperature on a held-out split. Confidence gates behaviour,
# so the number has to mean something before a threshold is placed on it.
eval-calibrate:
	cd services/router && python3 eval/run_eval.py --calibrate

# CI gate: a policy miss means sensitive content was under-enforced.
eval-ci:
	cd services/router && python3 eval/run_eval.py --fail-on-policy-miss

# Train a logistic head over frozen embeddings. Writes models/linear_head.json
# only when it beats k-NN on the held-out harness.
eval-train-linear:
	cd services/router && python3 eval/train_linear_head.py

# Partner demo: intent routing, retrieval, secret block, PII local_only.
demo:
	./scripts/partner_demo.sh

# Render the Helm chart without installing (sanity check).
helm-template:
	helm template kubemind ./charts/kubemind --namespace kubemind

# ── Linting ──────────────────────────────────────────────────────
lint:
	@echo "Linting Python services..."
	cd services/router && ruff check src/
	cd services/mind && ruff check src/
	cd services/agents && ruff check src/
	cd services/sentinel && ruff check src/
	$(MAKE) typecheck
	@echo "Linting Go CLI..."
	cd cmd/tricore && go vet ./...
	@echo "Linting Dashboard..."
	cd dashboard && npm run lint

typecheck:
	MYPYPATH=services/router/src:shared/python mypy --ignore-missing-imports \
		services/router/src/router/auth.py \
		services/router/src/router/keymint_runtime.py \
		services/router/src/router/policy.py \
		shared/python/kubemind_auth shared/python/kubemind_policy

security:
	bandit -q -lll -r services/router/src services/mind/src services/agents/src services/sentinel/src
	python3 scripts/check_secrets.py
	pip-audit -r services/router/requirements.txt -r services/mind/requirements.txt -r services/agents/requirements.txt -r services/sentinel/requirements.txt
	cd dashboard && npm audit --audit-level=high

ci: lint test eval-ci security

# ── Cleanup ──────────────────────────────────────────────────────
clean:
	docker compose down -v
	docker system prune -f
	rm -rf bin/ services/*/src/__pycache__ services/*/.mypy_cache
