"""Initialize L4 Memory & Knowledge Layer for production use.

This script:
1. Validates configuration
2. Creates necessary data directories
3. Tests the L4 connection
4. Provides usage examples

Usage:
    python init_l4.py

Environment:
    Requires .env file with OPENAI_API_KEY configured
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.l4.config.l4_config import (
    validate_l4_config,
    init_l4_data_directories,
    get_l4_memory,
    get_l4_memory_production,
    L4_CONFIG
)


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_section(text):
    """Print formatted section."""
    print(f"\n>> {text}")


def main():
    """Main initialization routine."""
    print_header("L4 Memory & Knowledge Layer Initialization")

    # -------------------------------------------------------------------------
    # Step 1: Configuration Validation
    # -------------------------------------------------------------------------
    print_section("Step 1: Validating Configuration")

    issues = validate_l4_config()

    if issues["errors"]:
        print("\n[ERROR] Configuration Errors Found:")
        for error in issues["errors"]:
            print(f"   - {error}")
        print("\n[WARN]  Please fix these errors before continuing.")
        print("   Edit your .env file to set the required variables.")
        sys.exit(1)

    if issues["warnings"]:
        print("\n[WARN]  Configuration Warnings:")
        for warning in issues["warnings"]:
            print(f"   - {warning}")

    if not issues["errors"] and not issues["warnings"]:
        print("[OK] Configuration is valid!")

    # -------------------------------------------------------------------------
    # Step 2: Create Data Directories
    # -------------------------------------------------------------------------
    print_section("Step 2: Creating Data Directories")
    init_l4_data_directories()

    # -------------------------------------------------------------------------
    # Step 3: Test L4 Initialization
    # -------------------------------------------------------------------------
    print_section("Step 3: Testing L4 Initialization")

    try:
        print("\n   Creating L4 Memory instance...")
        memory = get_l4_memory_production()
        print("[OK] L4 Memory initialized successfully!")

        # Show configuration
        print("\n   Configuration:")
        print(f"   - Embedding Provider: {L4_CONFIG['embedding']['provider']}")
        print(f"   - Embedding Model: {L4_CONFIG['embedding']['model']}")
        print(f"   - Vector Store: {L4_CONFIG['vector_store']['store_type']}")
        print(f"   - Memory Store: {L4_CONFIG['memory_store']['store_type']}")
        print(f"   - Cache Enabled: {L4_CONFIG['cache']['enable']}")

    except Exception as e:
        print(f"\n[ERROR] Failed to initialize L4: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Step 4: Run Basic Tests
    # -------------------------------------------------------------------------
    print_section("Step 4: Running Basic Tests")

    try:
        # Test 1: Store document
        print("\n   Test 1: Storing document...")
        result = memory.store(
            "Python is a high-level programming language known for its readability.",
            {"doc_id": "test-python", "category": "programming", "level": "beginner"}
        )
        if result:
            print("   [OK] Document stored successfully")
        else:
            print("   [WARN]  Document store returned False")

        # Test 2: Search
        print("\n   Test 2: Searching documents...")
        results = memory.search("programming language", top_k=3)
        print(f"   [OK] Search completed, found {len(results)} results")
        if results:
            print(f"   First result: {results[0][:100]}...")

        # Test 3: Conversation history
        print("\n   Test 3: Storing conversation history...")
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Is it easy to learn?"},
            {"role": "assistant", "content": "Yes, Python is known for being beginner-friendly."}
        ]
        memory.store_conversation("test-session-001", messages)
        history = memory.retrieve_history("test-session-001", limit=2)
        print(f"   [OK] Conversation stored and retrieved, {len(history)} messages")

        # Test 4: User preferences
        print("\n   Test 4: Storing user preferences...")
        memory.save_user_preference("user-001", "theme", "dark")
        memory.save_user_preference("user-001", "language", "zh-CN")
        theme = memory.load_user_preference("user-001", "theme")
        print(f"   [OK] User preference retrieved: theme={theme}")

        # Test 5: Statistics
        print("\n   Test 5: Getting statistics...")
        stats = memory.get_stats()
        print(f"   [OK] Statistics retrieved:")
        if "vector_store" in stats:
            vs_stats = stats["vector_store"]
            print(f"      - Vector Store: {vs_stats.get('document_count', 0)} documents")
        if "embedding_cache" in stats:
            cache_stats = stats["embedding_cache"]
            print(f"      - Embedding Cache: {cache_stats.get('size', 0)} entries")
        if "search_cache" in stats:
            cache_stats = stats["search_cache"]
            print(f"      - Search Cache: {cache_stats.get('size', 0)} entries")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Step 5: Summary
    # -------------------------------------------------------------------------
    print_header("Initialization Complete!")

    print("""
** L4 Memory & Knowledge Layer is ready to use!

Usage Example:
--------------
from config.l4_config import get_l4_memory_production

# Get configured L4 instance
memory = get_l4_memory_production()

# Store documents
memory.store("Document content", {"doc_id": "doc1"})

# Search
results = memory.search("query", top_k=5)

# Store conversation
memory.store_conversation("session-1", messages)

# Retrieve history
history = memory.retrieve_history("session-1")

Data Directories:
-----------------
- ChromaDB: ./src/l4/data/chroma_db
- Conversations: ./src/l4/data/conversations

Configuration:
--------------
Edit .env file to change settings:
- L4_EMBEDDING_PROVIDER=openai
- L4_VECTOR_STORE_TYPE=chroma
- L4_MEMORY_STORE_TYPE=file
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
