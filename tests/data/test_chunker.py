import pytest
import os
import shutil
import tempfile

# Adjust these imports if your module/package structure differs
from src.config import KomodoConfig
from src.core import ParallelChunker

@pytest.fixture
def sample_dir():
    """
    Returns the path to the sample directory containing .gitignore, keepme.txt, etc.
    """
    return os.path.join(os.path.dirname(__file__), "data", "sample_dir")

def test_parallel_chunker_ignores(sample_dir):
    """
    Tests that ParallelChunker processes sample_dir, respects .gitignore,
    and writes out chunk files containing only keepme.txt data.
    """
    tmpdir = tempfile.mkdtemp(prefix="komodo_test_")

    try:
        config = KomodoConfig(
            max_size=1024,           # small max_size for demonstration
            token_mode=False,
            output_dir=tmpdir,
            stream=False,
            ignore_patterns=None,   
            priority_rules=None,
            binary_extensions=None
        )

        with ParallelChunker(config) as pc:
            pc.process_directory(sample_dir)

        chunk_files = [f for f in os.listdir(tmpdir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0, "Expected at least one chunk file to be created."

        with open(os.path.join(tmpdir, chunk_files[0]), "r") as f:
            data = f.read()

        assert "keepme.txt" in data, "Expected keepme.txt content in the chunk."

        assert "ignoreme.log" not in data, "ignoreme.log should be ignored (via .gitignore)."
        assert "secret.txt" not in data, "secret.txt should be ignored (via .gitignore)."

    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    pytest.main()