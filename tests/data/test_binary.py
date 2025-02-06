import os
import shutil
import tempfile
from src.config import KomodoConfig
from src.multi_dirs_chunker import ParallelChunker

def test_parallel_chunker_binary():
    test_dir = os.path.join(os.path.dirname(__file__), "binary_test")
    os.makedirs(test_dir, exist_ok=True)
    print(f"\nCreated test directory: {test_dir}")

    with open(os.path.join(test_dir, "hello.bin"), "wb") as f:
        f.write(b"Hello\x00Binary\n")
    print("Created hello.bin")

    with open(os.path.join(test_dir, "notes.txt"), "w") as f:
        f.write("This is a normal text file")
    print("Created notes.txt")

    tmpdir = tempfile.mkdtemp(prefix="komodo_test_")
    print(f"Output directory: {tmpdir}")

    try:
        config = KomodoConfig(
            max_size=1024,
            token_mode=False,
            output_dir=tmpdir,
            stream=False,
            ignore_patterns=None,
            binary_extensions=["bin"],
            priority_rules=None
        )

        print("\nProcessing files...")
        with ParallelChunker(config) as pc:
            pc.process_directory(test_dir)

        print(f"\nChecking output directory: {tmpdir}")
        all_files = os.listdir(tmpdir)
        print(f"All files in output: {all_files}")
        
        chunk_files = [f for f in all_files if f.startswith("chunk-")]
        print(f"Found {len(chunk_files)} chunk files")
        
        if len(chunk_files) == 0:
            print("\nError: No chunks created!")
            print(f"Test dir exists? {os.path.exists(test_dir)}")
            print(f"Output dir exists? {os.path.exists(tmpdir)}")
            print(f"Test dir contents: {os.listdir(test_dir)}")
            raise Exception("No chunk files were created")

        print("\nReading first chunk:")
        with open(os.path.join(tmpdir, chunk_files[0]), "r") as f:
            data = f.read()
            print("Chunk contents:", data)

        if "notes.txt" not in data:
            raise Exception("Expected normal text file to appear in chunk")
        if "hello.bin" in data:
            raise Exception("Binary file should not appear in chunk")

    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        print("Debug information:")
        if os.path.exists(test_dir):
            print(f"Test directory contents: {os.listdir(test_dir)}")
        if os.path.exists(tmpdir):
            print(f"Output directory contents: {os.listdir(tmpdir)}")
        raise  

    finally:
        print("\nCleaning up...")
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_parallel_chunker_binary()
    print("Test completed successfully!")