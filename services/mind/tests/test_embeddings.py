import pytest
import httpx
import respx
from mind.embeddings import EmbeddingGenerator

class TestEmbeddingGenerator:
    @pytest.mark.asyncio
    async def test_init_success(self):
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(200, json={"models": [{"name": "nomic-embed-text:latest"}]})
            )
            gen = EmbeddingGenerator()
            await gen.init()
            assert gen.is_ready is True
            await gen.close()

    @pytest.mark.asyncio
    async def test_init_model_not_found(self):
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(200, json={"models": [{"name": "other-model"}]})
            )
            gen = EmbeddingGenerator()
            await gen.init()
            assert gen.is_ready is False
            await gen.close()

    @pytest.mark.asyncio
    async def test_embed_success(self):
        with respx.mock:
            respx.post("http://localhost:11434/api/embed").mock(
                return_value=httpx.Response(200, json={"embedding": [0.1] * 768})
            )
            gen = EmbeddingGenerator()
            gen.client = httpx.AsyncClient(base_url="http://localhost:11434")
            gen.is_ready = True

            result = await gen.embed("hello world")
            assert len(result) == 768
            assert result[0] == 0.1
            await gen.close()

    @pytest.mark.asyncio
    async def test_embed_failure_returns_zero_vector(self):
        with respx.mock:
            respx.post("http://localhost:11434/api/embed").mock(
                return_value=httpx.Response(500)
            )
            gen = EmbeddingGenerator()
            gen.client = httpx.AsyncClient(base_url="http://localhost:11434")
            gen.is_ready = True

            result = await gen.embed("hello world")
            assert len(result) == 768
            assert all(v == 0.0 for v in result)
            await gen.close()

    @pytest.mark.asyncio
    async def test_embed_truncate_long_text(self):
        with respx.mock:
            respx.post("http://localhost:11434/api/embed").mock(
                return_value=httpx.Response(200, json={"embedding": [0.1] * 768})
            )
            gen = EmbeddingGenerator()
            gen.client = httpx.AsyncClient(base_url="http://localhost:11434")
            gen.is_ready = True

            long_text = "word " * 5000  # Way over 8000 chars
            result = await gen.embed(long_text)
            assert len(result) == 768
            await gen.close()
