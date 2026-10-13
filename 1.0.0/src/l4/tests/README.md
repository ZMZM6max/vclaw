# L4 Memory & Knowledge Layer Tests

This directory contains unit tests for the L4 (Memory & Knowledge) layer of the VClaw system.

## Test Files

| File | Purpose | Dependencies | Status |
|------|---------|--------------|--------|
| `test_embedding.py` | Embedding service tests (Mock, OpenAI, Sentence Transformers) | None (Mock), `openai`, `sentence-transformers` | ✅ Ready |
| `test_text_chunker.py` | Text chunker tests (Recursive, Token, Markdown, Character) | None | ✅ Ready |
| `test_vector_store.py` | Vector store tests (Memory, ChromaDB, FAISS) | `numpy` (required), `chromadb`, `faiss-cpu` (optional) | ✅ Ready |
| `test_memory_store.py` | Memory store tests (InMemory, File, Compression) | None | ✅ Ready |
| `test_cache_manager.py` | Cache manager tests (LRU, TTL, EmbeddingCache, SearchCache) | None | ✅ Ready |
| `test_l4_memory.py` | Main MemoryKnowledge class integration tests | All above | ✅ Ready |
| `test_l4.py` | Legacy integration tests (kept for compatibility) | All above | ✅ Ready |

## Dependencies

### Required for all tests
```bash
pip install pytest numpy
```

### Optional (for specific test coverage)
| Feature | Package | Install Command |
|---------|---------|-----------------|
| OpenAI Embedding | `openai` | `pip install openai` |
| Local Embedding | `sentence-transformers` | `pip install sentence-transformers` |
| ChromaDB Vector Store | `chromadb` | `pip install chromadb` |
| FAISS Vector Store | `faiss-cpu` | `pip install faiss-cpu` |
| Token Counting | `tiktoken` | `pip install tiktoken` |

## Running Tests

### Run all L4 tests
```bash
pytest src/l4/tests/ -v
```

### Run specific test file
```bash
pytest src/l4/tests/test_embedding.py -v
pytest src/l4/tests/test_text_chunker.py -v
pytest src/l4/tests/test_vector_store.py -v
pytest src/l4/tests/test_memory_store.py -v
pytest src/l4/tests/test_cache_manager.py -v
pytest src/l4/tests/test_l4_memory.py -v
```

### Run specific test class
```bash
pytest src/l4/tests/test_embedding.py::TestMockEmbeddingService -v
```

### Run with coverage
```bash
pytest src/l4/tests/ --cov=src.l4 --cov-report=html
```

### Skip slow tests (model loading)
```bash
pytest src/l4/tests/ -v -m "not slow"
```

## Test Categories

### Unit Tests (Fast)
- Mock embedding service
- Memory vector store
- All text chunkers
- Memory compressor
- Cache manager
- In-memory conversation store

### Integration Tests (Slower)
- OpenAI embedding (requires API key)
- Sentence Transformers embedding (requires model download)
- ChromaDB vector store
- FAISS vector store
- File-based memory store

### External Service Requirements

#### OpenAI Tests
Set environment variable:
```bash
export OPENAI_API_KEY="your-key-here"
```

Tests will skip automatically if not set.

#### Sentence Transformers Tests
First run will download models (~100MB). Subsequent runs use cached models.

## Test Structure

```
test_*.py
├── Test<ClassName>           # Test class for each component
│   ├── test_init_*          # Initialization tests
│   ├── test_basic_*         # Basic functionality
│   ├── test_error_*         # Error handling
│   └── test_edge_*          # Edge cases
├── TestCreate*              # Factory function tests
└── Test*Integration         # Integration tests
```

## Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| Embedding | 90%+ |
| Text Chunker | 90%+ |
| Vector Store | 85%+ |
| Memory Store | 85%+ |
| Cache Manager | 90%+ |
| MemoryKnowledge | 80%+ |

## Notes

- Mock implementations are tested thoroughly and run quickly
- External service tests are marked with `@pytest.mark.skip` or conditional logic
- Tests use temporary directories for file operations
- All tests clean up after themselves

## Adding New Tests

When adding new tests:
1. Follow existing naming convention: `test_<component>_<scenario>`
2. Add docstrings describing what is being tested
3. Group related tests in test classes
4. Use fixtures for common setup
5. Mark slow/external tests appropriately
