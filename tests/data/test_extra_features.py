# test_extra_features.py

import os
import sys
import shutil
import tempfile
import pytest
from src.multi_dirs_chunker import ParallelChunker

@pytest.fixture
def temp_dirs():
    """
    Create a temporary test directory and output directory, then yield them.
    Clean them up after the test.
    """
    test_dir = tempfile.mkdtemp(prefix="komodo_test_")
    output_dir = tempfile.mkdtemp(prefix="komodo_output_")
    yield test_dir, output_dir
    shutil.rmtree(test_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)

def create_test_file(directory, name, content):
    """
    Simple helper to create a test file with the given name and content
    inside 'directory'.
    """
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(content)
    return path

def read_all_chunks(output_dir):
    """
    Collect and return the contents of all chunk-*.txt files as a single string.
    """
    chunk_files = sorted(
        f for f in os.listdir(output_dir)
        if f.startswith("chunk-")
    )
    data = []
    for cf in chunk_files:
        with open(os.path.join(output_dir, cf), "r") as infile:
            data.append(infile.read())
    return "".join(data)

def test_whole_chunk_mode(temp_dirs):
    test_dir, output_dir = temp_dirs
    file_paths = []
    contents = [
        "Hello from file1.\n" * 10,
        "Hello from file2.\n" * 10,
        "Hello from file3.\n" * 10,
    ]
    filenames = ["file1.txt", "file2.txt", "file3.txt"]

    for fn, c in zip(filenames, contents):
        create_test_file(test_dir, fn, c)

    chunker = ParallelChunker(
        max_size=50,
        output_dir=output_dir,
        whole_chunk_mode=True,
        stream=False,
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    out_files = os.listdir(output_dir)
    assert len(out_files) == 1, f"Expected exactly 1 file, found {out_files}"
    assert out_files[0].startswith("whole_chunk_mode-output"), \
        "Aggregator file has an unexpected name"

    aggregator_path = os.path.join(output_dir, out_files[0])
    with open(aggregator_path, "r") as agg:
        data = agg.read()

    for fn, c in zip(filenames, contents):
        header_line = f"File: {os.path.join(test_dir, fn)}\n"
        assert header_line in data, f"Missing header line for {fn}"
        snippet = c[:10]
        assert snippet in data, f"Missing content snippet '{snippet}' from {fn}"

def test_stream_mode_stdout(temp_dirs, capfd):
    test_dir, _ = temp_dirs
    
    filenames = ["alpha.txt", "beta.txt"]
    contents = ["Alpha content", "Beta content"]
    for fn, c in zip(filenames, contents):
        create_test_file(test_dir, fn, c)

    chunker = ParallelChunker(
        max_size=10,
        stream=True, 
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    captured = capfd.readouterr()
    output = captured.out

    for fn in filenames:
        assert fn in output, f"Missing filename {fn} in stdout"
    for text in contents:
        assert text in output, f"Missing file content '{text}' in stdout"

def test_token_mode(temp_dirs):
    test_dir, output_dir = temp_dirs
    
    tokens = [f"word{i}" for i in range(25)]
    content = " ".join(tokens)
    create_test_file(test_dir, "twenty_five_tokens.txt", content)

    chunker = ParallelChunker(
        max_size=999999,
        token_mode=True,
        output_dir=output_dir,
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    combined = read_all_chunks(output_dir)

    assert "twenty_five_tokens.txt" in combined
    for t in tokens:
        assert t in combined, f"Token {t} not found in the output"

def test_ignore_unignore(temp_dirs):
    test_dir, output_dir = temp_dirs
    
    create_test_file(test_dir, "main.py", "print('Hello')\n")
    create_test_file(test_dir, "notes.md", "# Some notes\n")
    create_test_file(test_dir, "README.md", "# This is the readme\n")

    chunker = ParallelChunker(
        output_dir=output_dir,
        user_ignore=["*.md"],   # ignore all .md
        user_unignore=["README.md"],  # but unignore README.md
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    data = read_all_chunks(output_dir)

    assert "main.py" in data, "main.py should appear"
    assert "README.md" in data, "README.md should appear (unignored)"
    # 'notes.md' should NOT appear
    assert "notes.md" not in data, "notes.md should be ignored"

def test_large_file_splitting(temp_dirs):
    test_dir, output_dir = temp_dirs
    
    big_content = "X" * 10000
    create_test_file(test_dir, "bigfile.txt", big_content)

    chunker = ParallelChunker(
        max_size=1024,
        output_dir=output_dir,
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    combined = read_all_chunks(output_dir)
    assert "bigfile.txt" in combined
    assert combined.count("X") >= 10000, "Missing some of the big file content"

@pytest.mark.skipif(sys.platform.startswith("win"),
    reason="Symlinks are not always available/permissions on Windows by default")
def test_symlink_handling(temp_dirs):
    test_dir, output_dir = temp_dirs

    real_file = create_test_file(test_dir, "realfile.txt", "Real file content\n")

    symlink_path = os.path.join(test_dir, "link_to_realfile.txt")
    os.symlink(real_file, symlink_path)

    chunker = ParallelChunker(
        output_dir=output_dir,
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    data = read_all_chunks(output_dir)
    assert "link_to_realfile.txt" in data, "Expected symlink name to appear in chunk"
    assert "Real file content" in data, "Expected symlinked file content to appear"

def test_nested_directories(temp_dirs):
    test_dir, output_dir = temp_dirs

    os.makedirs(os.path.join(test_dir, "subdir", "subsubdir"))
    create_test_file(test_dir, "top.txt", "Top-level file\n")
    create_test_file(os.path.join(test_dir, "subdir"), "middle.txt", "Subdir file\n")
    create_test_file(os.path.join(test_dir, "subdir", "subsubdir"), "bottom.txt", "Deep file\n")

    chunker = ParallelChunker(
        output_dir=output_dir,
        num_threads=1
    )
    chunker.process_directories([test_dir])
    chunker.close()

    data = read_all_chunks(output_dir)
    assert "top.txt" in data, "Top-level file missing"
    assert "middle.txt" in data, "Subdir file missing"
    assert "bottom.txt" in data, "Deeper subdir file missing"

def test_high_concurrency_stress(temp_dirs):
    test_dir, output_dir = temp_dirs
    
    for i in range(100):
        create_test_file(test_dir, f"file_{i}.txt", f"Content for file {i}\n" * 5)
    
    chunker = ParallelChunker(
        max_size=512,
        output_dir=output_dir,
        num_threads=8  
    )
    chunker.process_directories([test_dir])
    chunker.close()

    data = read_all_chunks(output_dir)
    assert "file_0.txt" in data
    assert "Content for file 0" in data
    assert "file_99.txt" in data
    assert "Content for file 99" in data

if __name__ == "__main__":
    pytest.main(["-vv", __file__])