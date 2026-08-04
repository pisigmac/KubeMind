import os
import json
import httpx
from typing import List, Dict, Any, Optional

class Planner:
    def __init__(self):
        self.router_url = os.environ.get("ROUTER_URL", "http://localhost:9080")
        self.default_model = os.environ.get("PLANNER_MODEL", "llama3.1")
        self.client: Optional[httpx.AsyncClient] = None
        self.is_ready = False

    async def init(self):
        self.client = httpx.AsyncClient(timeout=60)
        self.is_ready = True

    async def plan(self, prompt: str, available_tools: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Planner not initialized")

        tools_str = ", ".join(available_tools) if available_tools else "none"

        plan_prompt = f"""You are a task planner. Break the following mission into a sequence of steps.
Each step should specify which tool to use (if any) and what to do.

Available tools: {tools_str}

Mission: {prompt}

Respond with JSON only:
{{
  "todos": [
    {{"step": 1, "task": "description", "tool": "tool_name or null", "reasoning": "why this step"}}
  ],
  "estimated_steps": number
}}"""

        try:
            resp = await self.client.post(
                f"{self.router_url}/v1/chat/completions",
                headers={
                    "X-Workspace-ID": "default",
                    "Authorization": "Bearer tricore-local-dev-key",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model or self.default_model,
                    "messages": [{"role": "user", "content": plan_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            plan = json.loads(content.strip())

            # Validate structure
            if "todos" not in plan:
                plan["todos"] = [{"step": 1, "task": prompt, "tool": None, "reasoning": "Direct execution"}]

            return plan

        except Exception as e:
            # Fallback: single-step plan
            return {
                "todos": [{"step": 1, "task": prompt, "tool": None, "reasoning": f"Direct execution (planning failed: {str(e)})"}],
                "estimated_steps": 1,
            }

    async def close(self):
        if self.client:
            await self.client.aclose()
