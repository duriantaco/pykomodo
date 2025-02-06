import os
import shutil
import tempfile

from src.config import KomodoConfig
from src.multi_dirs_chunker import ParallelChunker

def test_large_file_chunking():
    test_dir = os.path.join(os.path.dirname(__file__), "large_file_test")
    os.makedirs(test_dir, exist_ok=True)

    file_path = os.path.join(test_dir, "bigfile.txt")
    with open(file_path, "w") as f:
        f.write("A" * 1024)  
        f.write("B" * 1024)  
        f.write("C" * 1024)  
        f.write("D" * 500)   
    file_size = os.path.getsize(file_path)
    print(f"Created bigfile.txt of size {file_size} bytes")

    tmpdir = tempfile.mkdtemp(prefix="komodo_test_large_")
    print(f"Output directory: {tmpdir}")

    try:
        config = KomodoConfig(
            max_size=1024,        
            token_mode=False,
            output_dir=tmpdir,
            stream=False,
            ignore_patterns=None,
            binary_extensions=None,
            priority_rules=None
        )

        with ParallelChunker.from_config(config) as pc:
            pc.process_directory(test_dir)

        chunk_files = sorted(f for f in os.listdir(tmpdir) if f.startswith("chunk-"))
        print(f"Generated chunk files: {chunk_files}")
        assert len(chunk_files) > 1, "Expected multiple chunk files for a 3.5 KB file with 1 KB max chunk size"

        total_data = b""
        for cfile in chunk_files:
            with open(os.path.join(tmpdir, cfile), "rb") as f:
                chunk_data = f.read()
                total_data += chunk_data

        assert b"A" * 1024 in total_data, "Missing A-block"
        assert b"B" * 1024 in total_data, "Missing B-block"
        assert b"C" * 1024 in total_data, "Missing C-block"
        assert b"D" * 500 in total_data,  "Missing D-block"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    test_large_file_chunking()
    print("Test test_large_file_chunking completed successfully!")
