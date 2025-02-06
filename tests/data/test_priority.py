import os
import shutil
import tempfile
from src.config import KomodoConfig
from src.multi_dirs_chunker import ParallelChunker

def test_parallel_chunker_priority():
    test_dir = os.path.join(os.path.dirname(__file__),"priority_test")
    os.makedirs(test_dir, exist_ok=True)

    with open(os.path.join(test_dir, "apple.txt"), "w") as f:
        f.write("Apple content here")
    with open(os.path.join(test_dir, "banana.md"), "w") as f:
        f.write("Banana content here")
    with open(os.path.join(test_dir, "zebra.log"), "w") as f:
        f.write("Zebra content here")

    tmpdir = tempfile.mkdtemp(prefix="komodo_test_")
    print(f"\nCreated test files in: {test_dir}")
    print(f"Output directory: {tmpdir}")

    try:
        from src.config import PriorityRule
        config = KomodoConfig(
            max_size=1024,
            token_mode=False,
            output_dir=tmpdir,
            stream=False,
            ignore_patterns=None,
            binary_extensions=None,
            priority_rules=[
                PriorityRule(pattern="*apple*", score=10),
                PriorityRule(pattern="*.md", score=5),
            ]
        )

        with ParallelChunker.from_config(config) as pc:
            print("\nProcessing directory...")
            pc.process_directory(test_dir)
            
        print(f"\nChecking output directory: {tmpdir}")
        print(f"Files in output directory: {os.listdir(tmpdir)}")
        
        chunk_files = [f for f in os.listdir(tmpdir) if f.startswith("chunk-")]
        print(f"Found chunk files: {chunk_files}")
        
        assert len(chunk_files) > 0, "No chunk files were created in output directory"

        with open(os.path.join(tmpdir, chunk_files[0]), "r") as f:
            data = f.read()

        assert "Apple content here" in data
        apple_index = data.index("Apple content here")

        assert "Banana content here" in data
        banana_index = data.index("Banana content here")

        assert apple_index < banana_index, "apple.txt is higher priority, should come first"

    finally:
        shutil.rmtree(tmpdir)
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_parallel_chunker_priority()
    print("Test completed successfully!")