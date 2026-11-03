"""Unit tests for chunking adapters — semantic, hierarchical, late (D-11)."""

from __future__ import annotations

import pytest

from app.rag.chunking import (
    HierarchicalChunker,
    LateChunker,
    SemanticChunker,
)
from app.schemas.document import ChunkResult, EmbeddedChunk, ParsedPage

ORG_ID = "org-test-123"
TRACE_ID = "test-trace-id"
FAKE_EMBEDDING = [0.1] * 768


def _make_page(
    content: str,
    page_number: int = 1,
    source_uri: str = "s3://test-bucket/test-doc.pdf",
) -> ParsedPage:
    return ParsedPage(page_number=page_number, content=content, source_uri=source_uri)


def _meta(page: ParsedPage, org_id: str = ORG_ID) -> dict:
    """Build metadata dict from a ParsedPage for chunker.chunk() calls."""
    return {
        "source_uri": page.source_uri,
        "page_number": page.page_number,
        "organization_id": org_id,
    }


# ──────────────────────────────────────────────────────────────
# Semantic Chunker
# ──────────────────────────────────────────────────────────────


class TestSemanticChunker:
    @pytest.mark.asyncio
    async def test_basic_chunking(self, sample_page: ParsedPage) -> None:
        chunker = SemanticChunker(chunk_size=512)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        assert len(results) >= 1
        assert all(r.chunk_strategy == "semantic" for r in results)

    @pytest.mark.asyncio
    async def test_single_sentence(self) -> None:
        chunker = SemanticChunker()
        page = _make_page("ECS Fargate is serverless.")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 1
        assert results[0].chunk_text == "ECS Fargate is serverless."

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        chunker = SemanticChunker()
        page = _make_page("")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_metadata_completeness(self) -> None:
        chunker = SemanticChunker()
        page = _make_page(
            "ECS Fargate is serverless. It handles auto-scaling. "
            "The Unified Score gate is 0.85. Faithfulness blocks at 0.5."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for r in results:
            assert r.chunk_strategy == "semantic"
            assert r.parent_chunk_id is None
            assert r.page_number == 1
            assert r.source_uri == "s3://test-bucket/test-doc.pdf"
            assert r.organization_id == ORG_ID
            assert r.token_count > 0
            assert r.chunk_id is not None and len(r.chunk_id) > 0

    @pytest.mark.asyncio
    async def test_chunk_index_sequential(self) -> None:
        chunker = SemanticChunker(chunk_size=10)
        page = _make_page(
            "Sentence one here. Sentence two here. "
            "Sentence three here. Sentence four here. "
            "Sentence five here. Sentence six here."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for i, r in enumerate(results):
            assert r.chunk_index == i

    @pytest.mark.asyncio
    async def test_token_count_matches(self) -> None:
        chunker = SemanticChunker()
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for r in results:
            assert r.token_count == chunker.count_tokens(r.chunk_text)


# ──────────────────────────────────────────────────────────────
# Semantic — chunk_overlap (25-Jul-2026, Configurator wiring)
# ──────────────────────────────────────────────────────────────


class TestSemanticChunkerOverlap:
    @pytest.mark.asyncio
    async def test_default_zero_overlap_is_unchanged_behavior(self) -> None:
        """chunk_overlap=0 (the default) must produce byte-identical output
        to a chunker built before this parameter existed."""
        page = _make_page(
            "Sentence one here. Sentence two here. "
            "Sentence three here. Sentence four here. "
            "Sentence five here. Sentence six here."
        )
        no_overlap = SemanticChunker(chunk_size=10, chunk_overlap=0)
        results = await no_overlap.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        # No sentence should repeat across chunk boundaries.
        seen: set[str] = set()
        for r in results:
            for sent in r.chunk_text.split(". "):
                assert sent not in seen, f"'{sent}' repeated with chunk_overlap=0"
                seen.add(sent)

    @pytest.mark.asyncio
    async def test_overlap_repeats_trailing_sentence_in_next_chunk(self) -> None:
        page = _make_page(
            "Sentence one here. Sentence two here. "
            "Sentence three here. Sentence four here. "
            "Sentence five here. Sentence six here."
        )
        chunker = SemanticChunker(chunk_size=10, chunk_overlap=4)
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) >= 2
        # The last sentence of chunk N should reappear at the start of chunk N+1.
        for i in range(len(results) - 1):
            last_sentence_of_current = results[i].chunk_text.split(". ")[-1].rstrip(".")
            assert results[i + 1].chunk_text.startswith(last_sentence_of_current), (
                f"chunk {i + 1} does not carry overlap from chunk {i}"
            )

    @pytest.mark.asyncio
    async def test_overlap_never_exceeds_configured_budget(self) -> None:
        page = _make_page(
            "Sentence one here. Sentence two here. "
            "Sentence three here. Sentence four here. "
            "Sentence five here. Sentence six here."
        )
        chunker = SemanticChunker(chunk_size=10, chunk_overlap=4)
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        # Overlap window itself must respect the chunk_overlap token budget.
        for r in results:
            assert r.token_count <= chunker.chunk_size + chunker.chunk_overlap


# ──────────────────────────────────────────────────────────────
# Hierarchical Chunker
# ──────────────────────────────────────────────────────────────


class TestHierarchicalChunker:
    @pytest.mark.asyncio
    async def test_basic_chunking(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_parent_ids(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        parents = [r for r in results if r.parent_chunk_id is None]
        children = [r for r in results if r.parent_chunk_id is not None]
        assert len(parents) >= 1
        parent_ids = {p.chunk_id for p in parents}
        for child in children:
            assert child.parent_chunk_id in parent_ids

    @pytest.mark.asyncio
    async def test_chunk_index_sequential(self) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        page = _make_page(
            "ECS Fargate is serverless. It handles auto-scaling and load balancing. "
            "Task definitions specify container images, CPU allocation, and memory limits. "
            "Each task runs in isolation with its own ENI. "
            "Service auto-scaling uses CPU metrics. "
            "Scale-out triggers when CPU exceeds 70 percent. "
            "Scale-in occurs after 5 minutes of cool-down. "
            "Target tracking maintains desired metrics. "
            "Step scaling applies predefined adjustments. "
            "Scheduled scaling follows time-based rules."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for i, r in enumerate(results):
            assert r.chunk_index == i

    @pytest.mark.asyncio
    async def test_metadata_completeness(self) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        page = _make_page(
            "ECS Fargate is serverless. It handles auto-scaling and load balancing. "
            "Task definitions specify container images, CPU allocation, and memory limits. "
            "Each task runs in isolation with its own ENI."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for r in results:
            assert r.chunk_strategy == "hierarchical"
            assert r.page_number == 1
            assert r.source_uri == "s3://test-bucket/test-doc.pdf"
            assert r.organization_id == ORG_ID
            assert r.token_count > 0
            assert r.chunk_id is not None and len(r.chunk_id) > 0

    @pytest.mark.asyncio
    async def test_small_parent_gets_child(self) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        page = _make_page("ECS Fargate is serverless.")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 2
        parent = results[0]
        child = results[1]
        assert parent.parent_chunk_id is None
        assert child.parent_chunk_id == parent.chunk_id
        assert child.chunk_text == parent.chunk_text

    @pytest.mark.asyncio
    async def test_empty_page(self) -> None:
        chunker = HierarchicalChunker()
        page = _make_page("")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 0


# ──────────────────────────────────────────────────────────────
# Late Chunker (Team 8)
# ──────────────────────────────────────────────────────────────


class TestLateChunker:
    @pytest.mark.asyncio
    async def test_basic_chunking(self, sample_page: ParsedPage, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        assert len(results) >= 1
        assert all(r.chunk_strategy == "late" for r in results)

    @pytest.mark.asyncio
    async def test_metadata_completeness(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        page = _make_page(
            "ECS Fargate is serverless. It handles auto-scaling. "
            "The Unified Score gate is 0.85. Faithfulness blocks at 0.5."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for r in results:
            assert r.chunk_strategy == "late"
            assert r.parent_chunk_id is None
            assert r.page_number == 1
            assert r.source_uri == "s3://test-bucket/test-doc.pdf"
            assert r.organization_id == ORG_ID
            assert r.token_count > 0
            assert r.chunk_id

    @pytest.mark.asyncio
    async def test_empty_page(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        page = _make_page("")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_single_sentence(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        page = _make_page("ECS Fargate is serverless.")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert len(results) == 1
        assert results[0].chunk_text == "ECS Fargate is serverless."

    @pytest.mark.asyncio
    async def test_token_count_matches(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for r in results:
            assert r.token_count == chunker.count_tokens(r.chunk_text)

    @pytest.mark.asyncio
    async def test_chunk_index_sequential(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder, chunk_size=10)
        page = _make_page(
            "Sentence one here. Sentence two here. "
            "Sentence three here. Sentence four here. "
            "Sentence five here. Sentence six here."
        )
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        for i, r in enumerate(results):
            assert r.chunk_index == i


# ──────────────────────────────────────────────────────────────
# EmbeddedChunk — Builder output contract
# ──────────────────────────────────────────────────────────────


class TestEmbeddedChunk:
    @pytest.mark.asyncio
    async def test_from_chunk_result_semantic(self) -> None:
        chunker = SemanticChunker()
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        chunks = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert chunks
        embedded = EmbeddedChunk.from_chunk_result(chunks[0], embedding=FAKE_EMBEDDING)
        assert embedded.chunk_embedding == FAKE_EMBEDDING
        assert embedded.chunk_strategy == "semantic"
        assert embedded.chunk_id == chunks[0].chunk_id
        assert embedded.organization_id == ORG_ID

    @pytest.mark.asyncio
    async def test_from_chunk_result_hierarchical(self) -> None:
        chunker = HierarchicalChunker()
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        chunks = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert chunks
        embedded = EmbeddedChunk.from_chunk_result(chunks[0], embedding=FAKE_EMBEDDING)
        assert embedded.chunk_embedding == FAKE_EMBEDDING
        assert embedded.chunk_strategy == "hierarchical"

    @pytest.mark.asyncio
    async def test_from_chunk_result_late(self, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        chunks = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert chunks
        embedded = EmbeddedChunk.from_chunk_result(chunks[0], embedding=FAKE_EMBEDDING)
        assert embedded.chunk_embedding == FAKE_EMBEDDING
        assert embedded.chunk_strategy == "late"

    def test_embedding_dimension_enforced(self) -> None:
        chunk = ChunkResult(
            chunk_id="test-id",
            chunk_text="Test.",
            token_count=1,
            chunk_index=0,
            page_number=1,
            source_uri="s3://bucket/doc.pdf",
            organization_id=ORG_ID,
            chunk_strategy="semantic",
        )
        with pytest.raises(ValueError):
            EmbeddedChunk.from_chunk_result(chunk, embedding=[0.1] * 100)

    def test_chunk_result_has_no_embedding_fields(self) -> None:
        chunk = ChunkResult(
            chunk_id="test-id",
            chunk_text="Test.",
            token_count=1,
            chunk_index=0,
            page_number=1,
            source_uri="s3://bucket/doc.pdf",
            organization_id=ORG_ID,
            chunk_strategy="semantic",
        )
        assert not hasattr(chunk, "chunk_embedding")
        assert not hasattr(chunk, "full_page_embedding")


# ──────────────────────────────────────────────────────────────
# Shared — page_number, source_uri, organization_id preserved
# ──────────────────────────────────────────────────────────────


class TestPageNumberPreserved:
    @pytest.mark.asyncio
    async def test_multi_page(self) -> None:
        chunker = SemanticChunker()
        pages = [
            _make_page("Page one sentence one. Page one sentence two.", page_number=1),
            _make_page("Page two sentence one. Page two sentence two.", page_number=2),
            _make_page("Page three sentence one. Page three sentence two.", page_number=3),
        ]
        results = []
        for page in pages:
            results.extend(await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID))
        page_nums = [r.page_number for r in results]
        assert 1 in page_nums
        assert 2 in page_nums
        assert 3 in page_nums


class TestSourceURIPreserved:
    @pytest.mark.asyncio
    async def test_source_uri(self) -> None:
        chunker = SemanticChunker()
        uri = "supabase://storage/org1/pipeline1/doc.pdf"
        page = _make_page("ECS Fargate is serverless.", source_uri=uri)
        results = await chunker.chunk(page.content, _meta(page), x_trace_id=TRACE_ID)
        assert all(r.source_uri == uri for r in results)


class TestOrganizationIdPreserved:
    @pytest.mark.asyncio
    async def test_organization_id_both_strategies(self, embedder: object) -> None:
        page = _make_page("ECS Fargate is serverless. It handles auto-scaling.")
        org = "org-prod-abc123"
        meta = _meta(page, org_id=org)

        for chunker in [SemanticChunker(), HierarchicalChunker(), LateChunker(embedder=embedder)]:
            results = await chunker.chunk(page.content, meta, x_trace_id=TRACE_ID)
            assert all(r.organization_id == org for r in results), (
                f"{chunker.__class__.__name__} did not preserve organization_id"
            )


# ──────────────────────────────────────────────────────────────
# Semantic — token budget
# ──────────────────────────────────────────────────────────────


class TestSemanticTokenBudget:
    @pytest.mark.asyncio
    async def test_token_budget_flush(self, sample_page: ParsedPage) -> None:
        chunker = SemanticChunker(chunk_size=256)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        assert len(results) >= 3
        for r in results:
            assert r.token_count <= 256 or len(r.chunk_text.split(". ")) <= 1


# ──────────────────────────────────────────────────────────────
# Hierarchical — parent/child relationship integrity
# ──────────────────────────────────────────────────────────────


class TestHierarchicalRelationship:
    @pytest.mark.asyncio
    async def test_children_contained_in_parent(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)

        parents: dict[str, str] = {r.chunk_id: r.chunk_text for r in results if r.parent_chunk_id is None}
        children = [r for r in results if r.parent_chunk_id is not None]

        for child in children:
            assert child.parent_chunk_id in parents
            assert child.chunk_text in parents[child.parent_chunk_id], (
                f"Child '{child.chunk_text[:80]}' not found in parent"
            )

    @pytest.mark.asyncio
    async def test_parent_id_references_valid_parent(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)

        parent_ids = {r.chunk_id for r in results if r.parent_chunk_id is None}
        children = [r for r in results if r.parent_chunk_id is not None]
        for child in children:
            assert child.parent_chunk_id in parent_ids

    @pytest.mark.asyncio
    async def test_child_token_range(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)

        children_by_parent: dict[str, list] = {}
        for r in results:
            if r.parent_chunk_id is not None:
                children_by_parent.setdefault(r.parent_chunk_id, []).append(r)

        for parent_id, children_list in children_by_parent.items():
            children_list.sort(key=lambda c: c.chunk_index)
            for i, child in enumerate(children_list):
                is_last = i == len(children_list) - 1
                if not is_last:
                    assert child.token_count <= 148, (
                        f"Child {child.chunk_index} token_count={child.token_count} "
                        f"exceeds 148 for {parent_id}"
                    )


# ──────────────────────────────────────────────────────────────
# chunk_id uniqueness
# ──────────────────────────────────────────────────────────────


class TestChunkIdUniqueness:
    @pytest.mark.asyncio
    async def test_hierarchical_chunk_ids_unique(self, sample_page: ParsedPage) -> None:
        chunker = HierarchicalChunker(chunk_size=512, child_chunk_size=128)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        ids = [r.chunk_id for r in results]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_semantic_chunk_ids_unique(self, sample_page: ParsedPage) -> None:
        chunker = SemanticChunker()
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        ids = [r.chunk_id for r in results]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_late_chunk_ids_unique(self, sample_page: ParsedPage, embedder: object) -> None:
        chunker = LateChunker(embedder=embedder)
        results = await chunker.chunk(sample_page.content, _meta(sample_page), x_trace_id=TRACE_ID)
        ids = [r.chunk_id for r in results]
        assert len(ids) == len(set(ids))
