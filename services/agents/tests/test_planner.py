import pytest
import httpx
import respx
from agents.planner import Planner

class TestPlanner:
    @pytest.mark.asyncio
    async def test_plan_success(self):
        with respx.mock:
            respx.post("http://localhost:9080/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={
                    "choices": [{
                        "message": {
                            "content": "```json\n{\"todos\": [{\"step\": 1, \"task\": \"test\", \"tool\": null, \"reasoning\": \"direct\"}]}\n```"
                        }
                    }]
                })
            )
            planner = Planner()
            planner.client = httpx.AsyncClient()
            planner.is_ready = True

            result = await planner.plan("test mission", ["filesystem"])
            assert "todos" in result
            assert len(result["todos"]) == 1
            assert result["todos"][0]["task"] == "test"
            await planner.close()

    @pytest.mark.asyncio
    async def test_plan_fallback_on_error(self):
        with respx.mock:
            respx.post("http://localhost:9080/v1/chat/completions").mock(
                return_value=httpx.Response(500)
            )
            planner = Planner()
            planner.client = httpx.AsyncClient()
            planner.is_ready = True

            result = await planner.plan("test mission", ["filesystem"])
            assert "todos" in result
            assert result["todos"][0]["task"] == "test mission"
            await planner.close()
