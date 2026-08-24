# KubeMind CI baseline

Status: local technical gate passing; release provenance pending

## Supported baseline

- Python: 3.10 locally, 3.11 in GitHub Actions
- Node.js: 22
- Go: version declared by `cmd/tricore/go.mod`
- Python tooling: pinned in `requirements-dev.txt`
- Service dependencies: pinned in each service `requirements.txt`
- Dashboard dependencies: locked by `dashboard/package-lock.json`

Install all Python dependencies into an isolated environment, install the dashboard with `npm ci`, then run:

```bash
make ci
```

`make ci` gates Python lint, a scoped type check of the router's security and policy boundary, Go vet, dashboard lint, all four service test suites, the intent-policy evaluation, high-severity static security findings, high-confidence secret patterns, Python dependency vulnerabilities, and high-severity npm advisories.

The type gate is deliberately scoped. It does not claim that all legacy Python modules are fully typed. Expanding that scope is follow-up hardening and must not be represented as completed coverage.

## Verified local evidence (2026-08-23)

| Gate | Result |
|---|---|
| Router | 250 passed, 3 skipped in 1.25s |
| Mind | 32 passed, 1 skipped in 0.71s |
| Agents | 15 passed, 3 skipped in 0.62s |
| Sentinel | 91 passed in 2.51s |
| Ruff | pass across all service source trees |
| Mypy | pass for 8 security/contract source files |
| Go vet | pass |
| Dashboard ESLint | pass with 26 non-blocking warnings from a clean `npm ci` install |
| Bandit | no high-severity findings |
| Secret scan | pass; only exact synthetic-canary files are exempted |
| pip-audit | no known vulnerabilities |
| npm audit | zero vulnerabilities |
| Intent evaluation | 0 policy misses; 87.0% accuracy; 40.7% abstention |

The suites retain explicit skips for tests that require live PostgreSQL, Ollama, or a running service stack. They are not silently counted as unit coverage.

## Security boundary

The agent shell utility executes a parsed argument vector with `shell=False`. Its executable allowlist is not a sandbox: production use still requires an isolated worker/container, an unprivileged identity, a workspace mount boundary, network policy, CPU/memory/time limits, and an auditable command policy.

Credential-shaped values used to test policy and redaction are exempted only through the exact paths in `scripts/check_secrets.py`. Adding a fixture requires review of that allowlist; source and configuration remain scanned.

## Reproducibility and release boundary

The repository had extensive pre-existing uncommitted work when this hardening pass began. The current source snapshot passes the local gates, but it cannot satisfy clean-checkout reproducibility until an owner reviews and commits the intended changes, then runs `make ci` from a fresh clone of that commit. The GitHub Actions workflow is present but has not yet supplied hosted-runner evidence.

Do not describe this baseline as production-certified. Licensing/provenance, image pinning, SBOM/signing, integration environments, load budgets, and release approval remain separate gates.
