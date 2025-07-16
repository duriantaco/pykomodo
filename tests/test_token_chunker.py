import os
import sys
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

try:
    from pykomodo.token_chunker import TokenBasedChunker, TIKTOKEN_AVAILABLE
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from pykomodo.token_chunker import TokenBasedChunker, TIKTOKEN_AVAILABLE
    except ImportError:
        try:
            from pykomodo.token_chunker import TokenBasedChunker, TIKTOKEN_AVAILABLE
        except ImportError:
            pytest.skip("TokenBasedChunker not available", allow_module_level=True)

@pytest.fixture
def test_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def output_dir(test_dir):
    """Create an output directory for chunks."""
    out_dir = os.path.join(test_dir, "chunks")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

@pytest.fixture
def sample_files(test_dir):
    """Create sample files for testing."""
    # Python file
    py_file = os.path.join(test_dir, "test.py")
    with open(py_file, "w") as f:
        f.write("""def hello_world():
    print("Hello, world!")
    return 42

class TestClass:
    def __init__(self):
        self.value = 123
        
    def get_value(self):
        return self.value
""")

    md_file = os.path.join(test_dir, "README.md")
    with open(md_file, "w") as f:
        f.write("""# Test Project
        
This is a test project for token-based chunking.

## Features

- Feature 1
- Feature 2
- Feature 3

## Examples

```python
def example():
    return "This is an example"
```
""")

    long_file = os.path.join(test_dir, "long.txt")
    with open(long_file, "w") as f:
        f.write(" ".join(["word"] * 2000))
        
    api_file = os.path.join(test_dir, "api_key.txt")
    with open(api_file, "w") as f:
        f.write('API_KEY = "sk_test_abcdefghijklmnopqrstuvwxyz123456789012"')
        
    return {
        "py_file": py_file,
        "md_file": md_file,
        "long_file": long_file,
        "api_file": api_file
    }

@pytest.fixture
def mock_pdf_file(test_dir):
    """Mock a PDF file using MagicMock and patch."""
    pdf_path = os.path.join(test_dir, "test.pdf")
    with open(pdf_path, "w") as f:
        f.write("PDF_MOCK")
    return pdf_path

class TestTokenBasedChunker:
    
    def test_initialization(self, output_dir):
        """Test initializing the TokenBasedChunker."""
        chunker = TokenBasedChunker(max_tokens_per_chunk=100, output_dir=output_dir)
        assert chunker.max_tokens_per_chunk == 100
        assert chunker.output_dir == output_dir
        
        chunker = TokenBasedChunker(equal_chunks=5, output_dir=output_dir)
        assert chunker.equal_chunks == 5
        
        with pytest.raises(ValueError):
            TokenBasedChunker(equal_chunks=5, max_tokens_per_chunk=100)
            
        with pytest.raises(ValueError):
            TokenBasedChunker(output_dir=output_dir)
            
    def test_count_tokens(self, output_dir):
        """Test token counting with and without tiktoken."""
        chunker = TokenBasedChunker(max_tokens_per_chunk=100, output_dir=output_dir)
        
        assert chunker.count_tokens("This is a test string") > 0
        
        assert chunker.count_tokens("") == 0
        
        assert chunker.count_tokens("こんにちは世界") > 0
        
        if not TIKTOKEN_AVAILABLE:
            assert chunker.count_tokens("This is a five word string") == 5
    
    def test_tiktoken_availability(self, output_dir):
        """Test that the chunker works with or without tiktoken."""
        module_name = TokenBasedChunker.__module__ + ".TIKTOKEN_AVAILABLE"
        
        with patch(module_name, True):
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  
            
            with patch("tiktoken.get_encoding", return_value=mock_encoding):
                chunker = TokenBasedChunker(max_tokens_per_chunk=100, output_dir=output_dir)
                assert chunker.count_tokens("test") == 5
        
        with patch(module_name, False):
            chunker = TokenBasedChunker(max_tokens_per_chunk=100, output_dir=output_dir)
            assert chunker.count_tokens("this is a test") == 4  

    def test_max_tokens_chunking(self, test_dir, output_dir, sample_files):
        """Test chunking with max_tokens_per_chunk."""
        chunker = TokenBasedChunker(max_tokens_per_chunk=20, output_dir=output_dir)
        chunker.process_directory(test_dir)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        for chunk_file in chunk_files:
            with open(os.path.join(output_dir, chunk_file), "r") as f:
                content = f.read()
                content_parts = content.split("=" * 40)
                for part in content_parts:
                    if len(part.strip()) > 0 and not part.startswith("CHUNK") and not part.startswith("File:"):
                        tokens = chunker.count_tokens(part)
                        assert tokens <= 50, f"Chunk {chunk_file} has {tokens} tokens, expected max 20 (with margin)"
    
    def test_equal_chunks(self, test_dir, output_dir, sample_files):
        """Test chunking with equal_chunks."""
        num_chunks = 3
        chunker = TokenBasedChunker(equal_chunks=num_chunks, output_dir=output_dir)
        chunker.process_directory(test_dir)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) == num_chunks
        
        for i in range(num_chunks):
            chunk_path = os.path.join(output_dir, f"chunk-{i}.txt")
            assert os.path.exists(chunk_path)
            with open(chunk_path, "r") as f:
                content = f.read()
                assert len(content) > 0
                assert f"CHUNK {i + 1} OF {num_chunks}" in content

    @pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken required for this test")
    def test_very_large_tokens(self, test_dir, output_dir):
        """Test handling very large token counts."""
        huge_file = os.path.join(test_dir, "huge.txt")
        with open(huge_file, "w") as f:
            f.write(" ".join(["verylongword"] * 5000))
        
        chunker = TokenBasedChunker(max_tokens_per_chunk=1000, output_dir=output_dir, verbose=True)
        chunker.process_file(huge_file)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 1
    
    def test_semantic_chunking(self, test_dir, output_dir, sample_files):
        """Test semantic chunking for Python files."""
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=50,
            output_dir=output_dir,
            semantic_chunking=True
        )
        
        chunker.process_file(sample_files["py_file"])
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        found_class = False
        found_func = False
        
        for chunk_file in chunk_files:
            with open(os.path.join(output_dir, chunk_file), "r") as f:
                content = f.read()
                if "Function: hello_world" in content:
                    found_func = True
                if "Class: TestClass" in content:
                    found_class = True
        
        assert found_func, "Function marker not found in chunks"
        assert found_class, "Class marker not found in chunks"
    
    def test_api_key_redaction(self, test_dir, output_dir, sample_files):
        """Test that API keys are properly redacted."""
        chunker = TokenBasedChunker(max_tokens_per_chunk=100, output_dir=output_dir)
        chunker.process_file(sample_files["api_file"])
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        with open(os.path.join(output_dir, chunk_files[0]), "r") as f:
            content = f.read()
            assert "sk_test_abcdefghijklmnopqrstuvwxyz123456789012" not in content
            assert "[API_KEY_REDACTED]" in content
    
    def test_dry_run(self, test_dir, output_dir, sample_files):
        """Test dry run mode."""
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=100,
            output_dir=output_dir,
            dry_run=True,
            verbose=True
        )
        
        from io import StringIO
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            chunker.process_directory(test_dir)
            
            chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
            assert len(chunk_files) == 0
            
            output = captured_output.getvalue()
            assert "[DRY-RUN]" in output
            
            for file_path in sample_files.values():
                assert os.path.basename(file_path) in output
        finally:
            sys.stdout = sys.__stdout__
    
    def test_ignore_patterns(self, test_dir, output_dir, sample_files):
        """Test file ignoring with patterns."""
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=100,
            output_dir=output_dir,
            user_ignore=["*.md"]
        )
        
        chunker.process_directory(test_dir)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        for chunk_file in chunk_files:
            with open(os.path.join(output_dir, chunk_file), "r") as f:
                content = f.read()
                assert "README.md" not in content
    
    def test_unignore_patterns(self, test_dir, output_dir, sample_files):
        """Test file unignoring with patterns."""
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=100,
            output_dir=output_dir,
            user_ignore=["*.*"],
            user_unignore=["*.py"]
        )
        
        chunker.process_directory(test_dir)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        for chunk_file in chunk_files:
            with open(os.path.join(output_dir, chunk_file), "r") as f:
                content = f.read()
                assert "test.py" in content
                assert "README.md" not in content
                assert "long.txt" not in content
                assert "api_key.txt" not in content
    
    def test_file_type_filter(self, test_dir, output_dir, sample_files):
        """Test filtering by file type."""
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=100,
            output_dir=output_dir,
            file_type="py"
        )
        
        chunker.process_directory(test_dir)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        for chunk_file in chunk_files:
            with open(os.path.join(output_dir, chunk_file), "r") as f:
                content = f.read()
                assert "test.py" in content
                assert "README.md" not in content
                assert "long.txt" not in content
    
    def test_verbose_mode(self, test_dir, output_dir, sample_files):
        """Test verbose mode."""
        from io import StringIO
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            chunker = TokenBasedChunker(
                max_tokens_per_chunk=100,
                output_dir=output_dir,
                verbose=True
            )
            chunker.process_directory(test_dir)
            
            output = captured_output.getvalue()
            
            if TIKTOKEN_AVAILABLE:
                assert "Using cl100k_base tokenizer" in output
            else:
                assert "tiktoken not available" in output
                
            assert "Creating chunks with maximum 100 tokens" in output
        finally:
            sys.stdout = sys.__stdout__
    
    def test_syntax_error_handling(self, test_dir, output_dir):
        """Test handling of Python files with syntax errors."""
        py_file = os.path.join(test_dir, "syntax_error.py")
        with open(py_file, "w") as f:
            f.write("""def broken_function(
                print("This has a syntax error")
            """)
        
        chunker = TokenBasedChunker(
            max_tokens_per_chunk=100,
            output_dir=output_dir,
            semantic_chunking=True,
            verbose=True
        )
        
        chunker.process_file(py_file)
        
        chunk_files = [f for f in os.listdir(output_dir) if f.startswith("chunk-")]
        assert len(chunk_files) > 0
        
        with open(os.path.join(output_dir, chunk_files[0]), "r") as f:
            content = f.read()
            assert "syntax_error.py" in content
            assert "This has a syntax error" in content

if __name__ == "__main__":
    pytest.main(["-v", __file__])