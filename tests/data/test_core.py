import unittest
import os
import tempfile
import shutil
from src.core import PyCConfig, PriorityRule

class TestPyCConfig(unittest.TestCase):
    def setUp(self):
        self.config = PyCConfig()
        self.test_dir = tempfile.mkdtemp()
        self.test_file_txt = os.path.join(self.test_dir, "example.txt")
        self.test_file_bin = os.path.join(self.test_dir, "binary.bin")
        with open(self.test_file_txt, "w", encoding="utf-8") as f:
            f.write("some text data\nwith multiple lines\n")
        with open(self.test_file_bin, "wb") as f:
            f.write(b"\x00\x01\x02somebinary")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_add_ignore_pattern(self):
        self.config.add_ignore_pattern("*.txt")
        self.assertIn("*.txt", self.config.ignore_patterns)

    def test_add_unignore_pattern(self):
        self.config.add_unignore_pattern("*.md")
        self.assertIn("*.md", self.config.unignore_patterns)

    def test_add_priority_rule(self):
        self.config.add_priority_rule("*.py", 10)
        self.assertTrue(any(r.pattern == "*.py" and r.score == 10 for r in self.config.priority_rules))

    def test_should_ignore(self):
        self.config.add_ignore_pattern("*.txt")
        self.assertTrue(self.config.should_ignore("example.txt"))
        self.config.add_unignore_pattern("example.txt")
        self.assertFalse(self.config.should_ignore("example.txt"))

    def test_calculate_priority(self):
        self.config.add_priority_rule("*.txt", 5)
        self.config.add_priority_rule("*example*", 10)
        self.assertEqual(self.config.calculate_priority("example.txt"), 10)
        self.assertEqual(self.config.calculate_priority("other.txt"), 5)
        self.assertEqual(self.config.calculate_priority("none.dat"), 0)

    def test_is_binary_file(self):
        self.config.binary_exts = ["bin"]
        self.assertTrue(self.config.is_binary_file(self.test_file_bin))
        self.assertFalse(self.config.is_binary_file(self.test_file_txt))

    def test_read_file_contents(self):
        contents_txt = self.config.read_file_contents(self.test_file_txt)
        self.assertIn("some text data", contents_txt)
        contents_missing = self.config.read_file_contents("does_not_exist.txt")
        self.assertEqual(contents_missing, "<NULL>")

    def test_count_tokens(self):
        text = "this is a test with  seven tokens"
        count = self.config.count_tokens(text)
        self.assertEqual(count, 7)

    def test_make_c_string(self):
        self.assertEqual(self.config.make_c_string(None), "<NULL>")
        self.assertEqual(self.config.make_c_string("data"), "data")

if __name__ == "__main__":
    unittest.main()
