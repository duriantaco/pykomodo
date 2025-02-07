# test_gitignore.py
import os
import shutil
import tempfile
import pytest
from src.gitignore import GitignoreHandler

@pytest.fixture
def temp_dir():
    """
    Creates a temporary directory for testing,
    yields its path, then cleans up.
    """
    d = tempfile.mkdtemp()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)

def test_no_gitignore(temp_dir):
    """
    If there's no .gitignore file,
    GitignoreHandler should not ignore any path,
    nor should it crash.
    """
    handler = GitignoreHandler(temp_dir)
    assert handler.should_ignore("foo.txt") is False
    assert handler.should_ignore("any/dir/file.py") is False

def test_empty_gitignore(temp_dir):
    """
    If .gitignore exists but is empty/commented,
    it should ignore nothing.
    """
    gitignore_path = os.path.join(temp_dir, ".gitignore")
    with open(gitignore_path, "w") as f:
        f.write("# Just a comment\n\n")

    handler = GitignoreHandler(temp_dir)
    assert handler.should_ignore("foo.txt") is False
    assert handler.should_ignore("bar.py") is False

def test_basic_patterns(temp_dir):
    """
    Test a basic .gitignore with some patterns.
    """
    gitignore_path = os.path.join(temp_dir, ".gitignore")
    with open(gitignore_path, "w") as f:
        f.write("""
        # Ignore all .log files
        *.log
        # Also ignore a "build" dir
        build/
                """)

    handler = GitignoreHandler(temp_dir)
    assert handler.should_ignore("stuff.log") is True
    assert handler.should_ignore("logs/test.log") is True
    assert handler.should_ignore("build/something") is True
    assert handler.should_ignore("build/subdir/file") is True
    assert handler.should_ignore("notes.txt") is False
    assert handler.should_ignore("buildup/code") is False

def test_whitespace_and_comments(temp_dir):
    """
    Ensure lines with trailing spaces or commented lines are handled properly.
    """
    gitignore_path = os.path.join(temp_dir, ".gitignore")
    with open(gitignore_path, "w") as f:
        f.write("""
        # Lines below ignore .tmp
        *.tmp   
        # Next line ignore a folder named 'dist'
        dist/    
        # commented out line
        # *.secret 
                """)

    handler = GitignoreHandler(temp_dir)

    assert handler.should_ignore("temp.tmp") is True
    assert handler.should_ignore("foo/bar.tmp") is True
    assert handler.should_ignore("dist/stuff") is True
    assert handler.should_ignore("secrets.secret") is False
    assert handler.should_ignore("otherfile.txt") is False

if __name__ == "__main__":
    pytest.main(["-v", __file__])
    print("Test completed successfully!")