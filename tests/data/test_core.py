# test_core.py

import os
import shutil
import tempfile
import pytest

from src.core import (
    PyCConfig,
    add_ignore_pattern,
    add_priority_rule,
    py_should_ignore,
    py_calculate_priority,
    py_make_c_string,
    py_read_file_contents,
    py_count_tokens,
    py_is_binary_file,
)

@pytest.fixture
def sample_config():
    return PyCConfig()

def test_make_c_string():
    txt = "Hello World"
    out = py_make_c_string(txt)
    assert out == "Hello World"
    assert py_make_c_string("") == ""
    assert py_make_c_string(None) == "<NULL>"

def test_read_file_contents():
    tmpdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmpdir, "testfile.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("LineOne\nLineTwo\n")
        contents = py_read_file_contents(path)
        assert contents == "LineOne\nLineTwo\n"
        missing = py_read_file_contents(os.path.join(tmpdir, "no_such.txt"))
        assert missing == "<NULL>"
    finally:
        shutil.rmtree(tmpdir)

def test_count_tokens():
    assert py_count_tokens("") == 0
    assert py_count_tokens("hello") == 1
    assert py_count_tokens("hello world") == 2
    assert py_count_tokens("  one   two  three   ") == 3

def test_is_binary_file():
    tmpdir = tempfile.mkdtemp()
    try:
        bin_path = os.path.join(tmpdir, "data.bin")
        with open(bin_path, "wb") as f:
            f.write(b"Hello\x00World")
        txt_path = os.path.join(tmpdir, "data.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Plain text file")

        assert py_is_binary_file(bin_path, ["bin"]) is True
        assert py_is_binary_file(txt_path, ["bin"]) is False
        assert py_is_binary_file(bin_path, []) is True
        assert py_is_binary_file(txt_path, []) is False
    finally:
        shutil.rmtree(tmpdir)

def test_should_ignore(sample_config):
    assert py_should_ignore("secret.txt", sample_config) is False
    add_ignore_pattern(sample_config, "secret.txt")
    assert py_should_ignore("secret.txt", sample_config) is True

def test_calculate_priority(sample_config):
    assert py_calculate_priority("myfile.txt", sample_config) == 0
    add_priority_rule(sample_config, "*.txt", 5)
    assert py_calculate_priority("myfile.txt", sample_config) == 5

if __name__ == "__main__":
    pytest.main(["-v", __file__])
