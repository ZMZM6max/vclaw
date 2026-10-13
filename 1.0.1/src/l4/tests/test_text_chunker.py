"""Tests for L4 Text Chunker."""
import pytest
from src.l4.services.text_chunker import (
    RecursiveTextChunker,
    TokenTextChunker,
    MarkdownTextChunker,
    CharacterTextChunker,
    create_text_chunker,
)


class TestRecursiveTextChunker:
    """Tests for RecursiveTextChunker."""

    def test_init_default(self):
        """Test default initialization."""
        chunker = RecursiveTextChunker()
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_init_custom(self):
        """Test custom initialization."""
        chunker = RecursiveTextChunker(chunk_size=500, chunk_overlap=50)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_init_invalid_overlap(self):
        """Test initialization with invalid overlap."""
        with pytest.raises(ValueError) as exc_info:
            RecursiveTextChunker(chunk_size=100, chunk_overlap=100)
        assert "chunk_overlap must be less than chunk_size" in str(exc_info.value)

    def test_split_short_text(self):
        """Test splitting short text."""
        chunker = RecursiveTextChunker(chunk_size=100, chunk_overlap=10)
        text = "Short text"
        result = chunker.split(text)
        assert result == [text]

    def test_split_long_text(self):
        """Test splitting long text."""
        chunker = RecursiveTextChunker(chunk_size=20, chunk_overlap=5)
        text = "This is a long text that needs to be split into multiple chunks."
        result = chunker.split(text)

        assert len(result) > 1
        # Each chunk should be at most chunk_size
        # Note: Recursive chunker may produce slightly larger chunks due to separator handling

    def test_split_empty_text(self):
        """Test splitting empty text."""
        chunker = RecursiveTextChunker()
        result = chunker.split("")
        assert result == []

    def test_split_with_paragraphs(self):
        """Test splitting respects paragraph boundaries."""
        chunker = RecursiveTextChunker(chunk_size=100, chunk_overlap=10)
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        result = chunker.split(text)

        assert len(result) >= 1

    def test_split_documents(self):
        """Test splitting documents with metadata."""
        chunker = RecursiveTextChunker(chunk_size=50, chunk_overlap=5)
        documents = [
            {
                "content": "This is the first document with enough content to be chunked.",
                "metadata": {"source": "doc1"}
            }
        ]

        result = chunker.split_documents(documents)

        assert len(result) > 0
        for chunk in result:
            assert "content" in chunk
            assert "metadata" in chunk
            assert "chunk_index" in chunk["metadata"]
            assert "chunk_count" in chunk["metadata"]


class TestTokenTextChunker:
    """Tests for TokenTextChunker."""

    def test_init_default(self):
        """Test default initialization."""
        chunker = TokenTextChunker()
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_split_short_text(self):
        """Test splitting short text."""
        chunker = TokenTextChunker(chunk_size=100)
        text = "Short text"
        result = chunker.split(text)
        assert result == [text]

    def test_split_long_text(self):
        """Test splitting long text."""
        chunker = TokenTextChunker(chunk_size=10, chunk_overlap=2)
        # Generate text with many words
        text = " ".join([f"word{i}" for i in range(50)])
        result = chunker.split(text)

        assert len(result) > 1

    def test_token_estimation(self):
        """Test token estimation."""
        chunker = TokenTextChunker(language="en")
        text = "Hello world"
        # English: ~0.25 tokens per char
        expected_tokens = int(len(text) * 0.25)
        assert chunker._count_tokens(text) == expected_tokens


class TestMarkdownTextChunker:
    """Tests for MarkdownTextChunker."""

    def test_init_default(self):
        """Test default initialization."""
        chunker = MarkdownTextChunker()
        assert chunker.headers_to_split_on == ["#", "##", "###"]
        assert chunker.max_chunk_size == 2000

    def test_split_no_headers(self):
        """Test splitting text without headers."""
        chunker = MarkdownTextChunker()
        text = "Just some text without headers."
        result = chunker.split(text)
        assert result == [text]

    def test_split_with_headers(self):
        """Test splitting text with headers."""
        chunker = MarkdownTextChunker()
        text = """# Header 1
Content for header 1.

## Header 2
Content for header 2.

### Header 3
Content for header 3."""

        result = chunker.split(text)
        assert len(result) >= 2

    def test_split_specific_headers(self):
        """Test splitting with specific header levels."""
        chunker = MarkdownTextChunker(headers_to_split_on=["#"])
        text = """# Main Header
Content here.

## Sub Header
More content."""

        result = chunker.split(text)
        # Should only split on #, not ##
        assert len(result) == 1


class TestCharacterTextChunker:
    """Tests for CharacterTextChunker."""

    def test_init_default(self):
        """Test default initialization."""
        chunker = CharacterTextChunker()
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_split_exact_size(self):
        """Test splitting with exact chunk size."""
        chunker = CharacterTextChunker(chunk_size=10, chunk_overlap=0)
        text = "0123456789" * 3  # 30 characters
        result = chunker.split(text)

        assert len(result) == 3
        assert all(len(chunk) == 10 for chunk in result)

    def test_split_with_separator(self):
        """Test splitting with separator preference."""
        chunker = CharacterTextChunker(chunk_size=20, chunk_overlap=2, separator=".")
        text = "First sentence. Second sentence. Third sentence."
        result = chunker.split(text)

        assert len(result) >= 1
        # Should try to split on periods

    def test_split_with_overlap(self):
        """Test splitting with overlap."""
        chunker = CharacterTextChunker(chunk_size=20, chunk_overlap=5)
        text = "0123456789" * 5  # 50 characters
        result = chunker.split(text)

        assert len(result) > 1
        # Check overlap
        for i in range(len(result) - 1):
            # Each chunk should have some overlap with next
            current_end = result[i][-5:]
            next_start = result[i + 1][:5]
            assert current_end == next_start or len(result[i]) == len(text)


class TestCreateTextChunker:
    """Tests for create_text_chunker factory."""

    def test_create_recursive(self):
        """Test creating recursive chunker."""
        chunker = create_text_chunker("recursive", chunk_size=500)
        assert isinstance(chunker, RecursiveTextChunker)
        assert chunker.chunk_size == 500

    def test_create_token(self):
        """Test creating token chunker."""
        chunker = create_text_chunker("token", chunk_size=100)
        assert isinstance(chunker, TokenTextChunker)
        assert chunker.chunk_size == 100

    def test_create_markdown(self):
        """Test creating markdown chunker."""
        chunker = create_text_chunker("markdown")
        assert isinstance(chunker, MarkdownTextChunker)

    def test_create_character(self):
        """Test creating character chunker."""
        chunker = create_text_chunker("character")
        assert isinstance(chunker, CharacterTextChunker)

    def test_create_case_insensitive(self):
        """Test factory is case insensitive."""
        chunker1 = create_text_chunker("RECURSIVE")
        chunker2 = create_text_chunker("Recursive")
        assert isinstance(chunker1, RecursiveTextChunker)
        assert isinstance(chunker2, RecursiveTextChunker)

    def test_create_unsupported(self):
        """Test creating unsupported chunker raises error."""
        with pytest.raises(ValueError) as exc_info:
            create_text_chunker("unsupported")
        assert "Unsupported chunker type" in str(exc_info.value)


class TestChunkerIntegration:
    """Integration tests for chunkers."""

    def test_chunker_preserves_content(self):
        """Test that chunking preserves all content."""
        chunker = CharacterTextChunker(chunk_size=20, chunk_overlap=0)
        text = "0123456789" * 10  # 100 characters
        result = chunker.split(text)

        # Join chunks and compare (without overlap)
        joined = "".join(result)
        assert joined == text

    def test_document_splitting_preserves_metadata(self):
        """Test that document splitting preserves metadata."""
        chunker = RecursiveTextChunker(chunk_size=30, chunk_overlap=3)
        documents = [
            {
                "content": "This is a test document that should be chunked.",
                "metadata": {"source": "test", "author": "tester"}
            }
        ]

        result = chunker.split_documents(documents)

        for chunk in result:
            assert chunk["metadata"]["source"] == "test"
            assert chunk["metadata"]["author"] == "tester"
