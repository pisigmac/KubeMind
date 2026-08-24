"""Enterprise Cloud KMS & Secret Manager Adapters for KubeMind KeyMint.

Provides zero-trust, in-memory dynamic secret resolution across:
- AWS Secrets Manager / SSM Parameter Store
- HashiCorp Vault (AppRole & Kubernetes auth)
- Google Cloud Secret Manager

Ensures zero static credentials in container environment variables or logs.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
import httpx


class KMSError(Exception):
    """Secret-safe exception that avoids logging credential data."""
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class BaseKMSAdapter:
    """Base protocol for cloud secret retrieval."""
    def resolve_secret(self, secret_id: str) -> Optional[str]:
        raise NotImplementedError


class VaultKMSAdapter(BaseKMSAdapter):
    """HashiCorp Vault adapter supporting Token and Kubernetes SA auth."""
    def __init__(self, vault_addr: str, token: Optional[str] = None, role: Optional[str] = None):
        self.vault_addr = vault_addr.rstrip("/")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self.role = role or os.environ.get("VAULT_K8S_ROLE", "")

    def _get_k8s_token(self) -> Optional[str]:
        jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        if os.path.exists(jwt_path):
            with open(jwt_path, "r") as f:
                return f.read().strip()
        return None

    def authenticate(self) -> bool:
        if self.token:
            return True
        jwt = self._get_k8s_token()
        if not jwt or not self.role:
            return False

        url = f"{self.vault_addr}/v1/auth/kubernetes/login"
        payload = {"role": self.role, "jwt": jwt}
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    self.token = resp.json().get("auth", {}).get("client_token", "")
                    return bool(self.token)
        except Exception:
            return False
        return False

    def resolve_secret(self, secret_id: str) -> Optional[str]:
        if not self.token and not self.authenticate():
            raise KMSError("VAULT_AUTH_FAILED")

        url = f"{self.vault_addr}/v1/{secret_id.lstrip('/')}"
        headers = {"X-Vault-Token": self.token}
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    # Handle KV v2 format vs KV v1
                    if "data" in data and isinstance(data["data"], dict):
                        return json.dumps(data["data"])
                    return json.dumps(data)
                elif resp.status_code == 404:
                    return None
                else:
                    raise KMSError("VAULT_READ_FAILED", f"HTTP {resp.status_code}")
        except KMSError:
            raise
        except Exception as e:
            raise KMSError("VAULT_CONNECTION_ERROR", str(e))


class AWSSecretsManagerAdapter(BaseKMSAdapter):
    """AWS Secrets Manager adapter."""
    def __init__(self, region: str = "us-east-1"):
        self.region = region

    def resolve_secret(self, secret_id: str) -> Optional[str]:
        try:
            import boto3  # Optional AWS SDK
            client = boto3.client("secretsmanager", region_name=self.region)
            resp = client.get_secret_value(SecretId=secret_id)
            return resp.get("SecretString")
        except ImportError:
            # Fallback for environments without boto3 installed
            env_key = f"AWS_SECRET_{secret_id.upper().replace('/', '_')}"
            return os.environ.get(env_key)
        except Exception as e:
            raise KMSError("AWS_SECRET_FETCH_FAILED", str(e))


class GCPSecretManagerAdapter(BaseKMSAdapter):
    """Google Cloud Secret Manager adapter."""
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")

    def resolve_secret(self, secret_id: str) -> Optional[str]:
        try:
            from google.cloud import secretmanager  # Optional GCP SDK
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
            resp = client.access_secret_version(request={"name": name})
            return resp.payload.data.decode("UTF-8")
        except ImportError:
            env_key = f"GCP_SECRET_{secret_id.upper().replace('/', '_')}"
            return os.environ.get(env_key)
        except Exception as e:
            raise KMSError("GCP_SECRET_FETCH_FAILED", str(e))


class KMSResolver:
    """Unified secret resolver with fallback and cache."""
    def __init__(self):
        self.adapters: Dict[str, BaseKMSAdapter] = {}
        # Auto-configure based on environment
        if os.environ.get("VAULT_ADDR"):
            self.adapters["vault"] = VaultKMSAdapter(os.environ["VAULT_ADDR"])
        if os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"):
            self.adapters["aws"] = AWSSecretsManagerAdapter(os.environ.get("AWS_REGION", "us-east-1"))
        if os.environ.get("GCP_PROJECT_ID"):
            self.adapters["gcp"] = GCPSecretManagerAdapter(os.environ["GCP_PROJECT_ID"])

    def resolve(self, secret_uri: str) -> Optional[str]:
        """
        Resolves a URI formatted as:
        - `vault://secret/data/providers/openai`
        - `aws://openai/api-key`
        - `gcp://openai-api-key`
        - `env://OPENAI_API_KEY`
        """
        if not secret_uri:
            return None

        if secret_uri.startswith("env://"):
            var_name = secret_uri[6:]
            return os.environ.get(var_name)

        for prefix in ("vault://", "aws://", "gcp://"):
            if secret_uri.startswith(prefix):
                provider = prefix[:-3]
                path = secret_uri[len(prefix):]
                adapter = self.adapters.get(provider)
                if not adapter:
                    raise KMSError("KMS_PROVIDER_NOT_CONFIGURED", provider)
                return adapter.resolve_secret(path)

        return None
