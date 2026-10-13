"""L4: Text Chunker - Split long texts into semantic chunks."""
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence
import re


class TextChunker(ABC):
    """Abstract base class for text chunkers."""

    @abstractmethod
    def split(self, text: str) -> List[str]:
        """Split text into chunks.

        Args:
            text: Input text to split

        Returns:
            List of text chunks
        """
        pass

    @abstractmethod
    def split_documents(self, documents: List[dict]) -> List[dict]:
        """Split multiple documents into chunks.

        Args:
            documents: List of documents with 'content' and optional 'metadata'

        Returns:
            List of chunked documents with updated metadata
        """
        pass


class RecursiveTextChunker(TextChunker):
    """Recursively split text by characters with overlap.

    Splits on separators in order of priority, recursively breaking
    larger chunks until all chunks are within chunk_size.
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[Sequence[str]] = None,
        length_function = len,
    ):
        """Initialize recursive text chunker.

        Args:
            chunk_size: Maximum size of each chunk
            chunk_overlap: Number of characters to overlap between chunks
            separators: List of separators to use in order of priority
            length_function: Function to measure text length
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = list(separators) if separators else self.DEFAULT_SEPARATORS
        self.length_function = length_function

    def split(self, text: str) -> List[str]:
        """Split text into chunks recursively."""
        if not text:
            return []

        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators."""
        # Base case: text is small enough
        if self.length_function(text) <= self.chunk_size:
            return [text] if text else []

        # No more separators, just chunk by size
        if not separators:
            return self._chunk_by_size(text)

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split by current separator
        if separator:
            parts = text.split(separator)
        else:
            # Empty separator means character-by-character split
            return self._chunk_by_size(text)

        # Merge small parts and split large parts
        chunks = []
        current_chunk = ""

        for part in parts:
            # Add separator back (except for first part)
            part_with_sep = (separator if current_chunk else "") + part

            # Check if adding this part would exceed chunk_size
            if self.length_function(current_chunk) + self.length_function(part_with_sep) <= self.chunk_size:
                current_chunk += part_with_sep
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(current_chunk)

                # If part itself is larger than chunk_size, split it recursively
                if self.length_function(part) > self.chunk_size:
                    # Recursively split this large part
                    sub_chunks = self._split_recursive(part, remaining_separators)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)

        # Add overlap between chunks
        return self._add_overlap(chunks)

    def _chunk_by_size(self, text: str) -> List[str]:
        """Chunk text by fixed size with overlap."""
        if self.length_function(text) <= self.chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < self.length_function(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """Add overlap between chunks."""
        if not chunks or len(chunks) == 1:
            return chunks

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]

            # Get overlap from end of previous chunk
            overlap_text = prev_chunk[-self.chunk_overlap:] if self.length_function(prev_chunk) > self.chunk_overlap else prev_chunk

            # Add overlap to current chunk
            result.append(overlap_text + current_chunk)

        return result

    def split_documents(self, documents: List[dict]) -> List[dict]:
        """Split documents into chunks with metadata."""
        result = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {}).copy()

            chunks = self.split(content)

            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunker_type": "recursive",
                })

                result.append({
                    "content": chunk,
                    "metadata": chunk_metadata,
                })

        return result


class TokenTextChunker(TextChunker):
    """Split text by token count (approximated by character count or tokenizer)."""

    # Approximate tokens per character for different languages
    TOKENS_PER_CHAR = {
        "en": 0.25,  # English
        "zh": 0.5,   # Chinese
        "default": 0.3,
    }

    def __init__(
        self,
        chunk_size: int = 500,  # tokens
        chunk_overlap: int = 50,  # tokens
        encoding_name: Optional[str] = None,  # e.g., "cl100k_base" for tiktoken
        language: str = "default",
    ):
        """Initialize token text chunker.

        Args:
            chunk_size: Maximum number of tokens per chunk
            chunk_overlap: Number of tokens to overlap
            encoding_name: Tiktoken encoding name (if available)
            language: Language code for token estimation
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name
        self.language = language
        self.tokens_per_char = self.TOKENS_PER_CHAR.get(language, self.TOKENS_PER_CHAR["default"])

        # Try to use tiktoken if specified
        self._tokenizer = None
        if encoding_name:
            try:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding(encoding_name)
            except ImportError:
                pass  # Fall back to character-based estimation
            except Exception:
                pass  # Invalid encoding name

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        else:
            # Estimate based on character count
            return int(len(text) * self.tokens_per_char)

    def split(self, text: str) -> List[str]:
        """Split text by token count."""
        if not text:
            return []

        if self._count_tokens(text) <= self.chunk_size:
            return [text]

        # Split by words first
        words = text.split(" ")
        chunks = []
        current_chunk = []
        current_tokens = 0

        for word in words:
            word_tokens = self._count_tokens(word + " ")

            if current_tokens + word_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(" ".join(current_chunk))

                # Calculate overlap
                overlap_tokens = 0
                overlap_words = []
                for w in reversed(current_chunk):
                    w_tokens = self._count_tokens(w + " ")
                    if overlap_tokens + w_tokens <= self.chunk_overlap:
                        overlap_words.insert(0, w)
                        overlap_tokens += w_tokens
                    else:
                        break

                current_chunk = overlap_words + [word]
                current_tokens = overlap_tokens + word_tokens
            else:
                current_chunk.append(word)
                current_tokens += word_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def split_documents(self, documents: List[dict]) -> List[dict]:
        """Split documents into chunks with metadata."""
        result = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {}).copy()

            chunks = self.split(content)

            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunker_type": "token",
                })

                result.append({
                    "content": chunk,
                    "metadata": chunk_metadata,
                })

        return result


class MarkdownTextChunker(TextChunker):
    """Split Markdown text by headers."""

    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(
        self,
        headers_to_split_on: Optional[List[str]] = None,
        max_chunk_size: int = 2000,
    ):
        """Initialize Markdown text chunker.

        Args:
            headers_to_split_on: List of header levels to split on (e.g., ["#", "##"])
            max_chunk_size: Maximum size of content within a header section
        """
        self.headers_to_split_on = headers_to_split_on or ["#", "##", "###"]
        self.max_chunk_size = max_chunk_size

    def split(self, text: str) -> List[str]:
        """Split Markdown text by headers."""
        if not text:
            return []

        # Find all headers
        matches = list(self.HEADER_PATTERN.finditer(text))

        if not matches:
            # No headers, treat as single chunk (or chunk by size)
            if len(text) <= self.max_chunk_size:
                return [text]
            # Fall back to recursive chunking
            fallback = RecursiveTextChunker(chunk_size=self.max_chunk_size)
            return fallback.split(text)

        chunks = []

        for i, match in enumerate(matches):
            header_level = match.group(1)
            header_text = match.group(2)
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            # Only split on specified header levels
            if header_level in self.headers_to_split_on:
                section_content = text[start_pos:end_pos].strip()

                # If section is too large, chunk it
                if len(section_content) > self.max_chunk_size:
                    fallback = RecursiveTextChunker(chunk_size=self.max_chunk_size)
                    sub_chunks = fallback.split(section_content)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(section_content)

        return chunks if chunks else [text]

    def split_documents(self, documents: List[dict]) -> List[dict]:
        """Split Markdown documents into chunks with metadata."""
        result = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {}).copy()

            # Extract headers for metadata
            headers = []
            for match in self.HEADER_PATTERN.finditer(content):
                headers.append({
                    "level": len(match.group(1)),
                    "text": match.group(2),
                })

            chunks = self.split(content)

            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunker_type": "markdown",
                    "headers": headers,
                })

                result.append({
                    "content": chunk,
                    "metadata": chunk_metadata,
                })

        return result


class CharacterTextChunker(TextChunker):
    """Simple character-based chunker with overlap."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "",
    ):
        """Initialize character text chunker.

        Args:
            chunk_size: Maximum number of characters per chunk
            chunk_overlap: Number of characters to overlap
            separator: Separator to prefer splitting on
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def split(self, text: str) -> List[str]:
        """Split text by character count."""
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to find separator to break on
            if self.separator and end < len(text):
                # Look for separator within reasonable range
                search_start = max(start, end - 100)
                search_end = min(len(text), end + 100)
                sep_pos = text.rfind(self.separator, search_start, search_end)

                if sep_pos != -1 and sep_pos > start:
                    end = sep_pos + len(self.separator)

            chunks.append(text[start:end])
            start = end - self.chunk_overlap

        return chunks

    def split_documents(self, documents: List[dict]) -> List[dict]:
        """Split documents into chunks with metadata."""
        result = []

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {}).copy()

            chunks = self.split(content)

            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunker_type": "character",
                })

                result.append({
                    "content": chunk,
                    "metadata": chunk_metadata,
                })

        return result


def create_text_chunker(
    chunker_type: str = "recursive",
    **kwargs
) -> TextChunker:
    """Factory function to create text chunker.

    Args:
        chunker_type: Type of chunker ('recursive', 'token', 'markdown', 'character')
        **kwargs: Chunker-specific arguments

    Returns:
        TextChunker instance

    Raises:
        ValueError: If chunker_type is not supported
    """
    chunker_type = chunker_type.lower()

    if chunker_type == "recursive":
        return RecursiveTextChunker(**kwargs)
    elif chunker_type == "token":
        return TokenTextChunker(**kwargs)
    elif chunker_type == "markdown":
        return MarkdownTextChunker(**kwargs)
    elif chunker_type == "character":
        return CharacterTextChunker(**kwargs)
    else:
        raise ValueError(
            f"Unsupported chunker type: {chunker_type}. "
            f"Supported: recursive, token, markdown, character"
        )
