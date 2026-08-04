from mind.chunking import chunk_text, expand_nodes_with_chunks, tokens_to_chars


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("hello world", max_tokens=512)
        assert chunks == ["hello world"]

    def test_long_text_multiple_chunks(self):
        text = "word " * 2000
        chunks = chunk_text(text, max_tokens=64, overlap_tokens=8)
        assert len(chunks) > 1
        assert all(len(c) <= tokens_to_chars(64) + tokens_to_chars(8) + 50 for c in chunks)

    def test_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_paragraph_strategy(self):
        text = "Para one.\n\n" + ("x" * 100) + "\n\nPara three with more content here."
        chunks = chunk_text(text, max_tokens=40, overlap_tokens=5)
        assert len(chunks) >= 1


class TestExpandNodes:
    def test_single_chunk_preserves_id(self):
        nodes = [
            {
                "id": "n1",
                "workspace_id": "ws",
                "type": "document",
                "content": "short",
                "metadata": {"path": "/a"},
            }
        ]
        out = expand_nodes_with_chunks(nodes, max_tokens=512)
        assert len(out) == 1
        assert out[0]["id"] == "n1"
        assert out[0]["metadata"]["chunk_total"] == 1

    def test_multi_chunk_parent_metadata(self):
        nodes = [
            {
                "id": "parent",
                "workspace_id": "ws",
                "type": "document",
                "content": "word " * 2000,
                "metadata": {},
            }
        ]
        out = expand_nodes_with_chunks(nodes, max_tokens=32, overlap_tokens=4)
        assert len(out) > 1
        assert all(n["metadata"].get("parent_id") == "parent" for n in out)
        assert out[0]["metadata"]["chunk_index"] == 0
        assert out[-1]["metadata"]["chunk_total"] == len(out)
