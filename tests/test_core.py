import unittest
import os
import tempfile
import shutil
from pykomodo.core import PyCConfig, PriorityRule

class TestPriorityRule(unittest.TestCase):
    def test_creation(self):
        rule = PriorityRule("*.py", 10)
        self.assertEqual(rule.pattern, "*.py")
        self.assertEqual(rule.score, 10)

class TestPyCConfig(unittest.TestCase):
    def setUp(self):
        self.config = PyCConfig()
        self.test_dir = tempfile.mkdtemp()
        self.test_file_txt = os.path.join(self.test_dir, "example.txt")
        self.test_file_bin = os.path.join(self.test_dir, "binary.bin")
        self.test_file_empty = os.path.join(self.test_dir, "empty.txt")
        
        with open(self.test_file_txt, "w", encoding="utf-8") as f:
            f.write("some text data\nwith multiple lines\n")
        with open(self.test_file_bin, "wb") as f:
            f.write(b"\x00\x01\x02somebinary")
        with open(self.test_file_empty, "w", encoding="utf-8") as f:
            pass

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_defaults(self):
        config = PyCConfig()
        self.assertEqual(config.max_size, 0)
        self.assertFalse(config.token_mode)
        self.assertIsNone(config.output_dir)
        self.assertFalse(config.stream)
        self.assertEqual(config.ignore_patterns, [])
        self.assertEqual(config.unignore_patterns, [])
        self.assertEqual(config.priority_rules, [])
        self.assertEqual(config.binary_exts, [])

    def test_add_ignore_pattern(self):
        self.config.add_ignore_pattern("*.txt")
        self.assertIn("*.txt", self.config.ignore_patterns)
        
        self.config.add_ignore_pattern("*.log")
        self.assertEqual(len(self.config.ignore_patterns), 2)

    def test_add_unignore_pattern(self):
        self.config.add_unignore_pattern("*.md")
        self.assertIn("*.md", self.config.unignore_patterns)

    def test_add_priority_rule(self):
        self.config.add_priority_rule("*.py", 10)
        self.assertTrue(any(r.pattern == "*.py" and r.score == 10 for r in self.config.priority_rules))

    def test_should_ignore(self):
        self.config.add_ignore_pattern("*.txt")
        self.assertTrue(self.config.should_ignore("example.txt"))
        self.assertFalse(self.config.should_ignore("example.py"))

    def test_unignore_overrides_ignore(self):
        self.config.add_ignore_pattern("*.txt")
        self.config.add_unignore_pattern("important.txt")
        
        self.assertTrue(self.config.should_ignore("example.txt"))
        self.assertFalse(self.config.should_ignore("important.txt"))

    def test_ignore_patterns(self):
        self.config.add_ignore_pattern("test_*")
        self.config.add_ignore_pattern("*.log")
        
        self.assertTrue(self.config.should_ignore("test_file.py"))
        self.assertTrue(self.config.should_ignore("debug.log"))
        self.assertFalse(self.config.should_ignore("main.py"))

    def test_calculate_priority(self):
        self.config.add_priority_rule("*.txt", 5)
        self.config.add_priority_rule("*example*", 10)
        self.assertEqual(self.config.calculate_priority("example.txt"), 10)
        self.assertEqual(self.config.calculate_priority("other.txt"), 5)
        self.assertEqual(self.config.calculate_priority("none.dat"), 0)

    def test_is_binary_file_by_extension(self):
        self.config.binary_exts = ["bin", "exe"]
        self.assertTrue(self.config.is_binary_file(self.test_file_bin))

    def test_is_binary_file_by_content(self):
        self.assertFalse(self.config.is_binary_file(self.test_file_txt))
        self.assertTrue(self.config.is_binary_file(self.test_file_bin))

    def test_is_binary_file_missing(self):
        missing_file = os.path.join(self.test_dir, "missing.txt")
        self.assertTrue(self.config.is_binary_file(missing_file))

    def test_read_file_contents(self):
        contents = self.config.read_file_contents(self.test_file_txt)
        self.assertIn("some text data", contents)

    def test_read_missing_file(self):
        missing_file = os.path.join(self.test_dir, "missing.txt")
        contents = self.config.read_file_contents(missing_file)
        self.assertEqual(contents, "<NULL>")

    def test_read_empty_file(self):
        contents = self.config.read_file_contents(self.test_file_empty)
        self.assertEqual(contents, "")

    def test_count_tokens(self):
        text = "this is a test with seven tokens"
        count = self.config.count_tokens(text)
        self.assertEqual(count, 7)

    def test_count_tokens_extra_spaces(self):
        text = "  this   has    extra     spaces  "
        count = self.config.count_tokens(text)
        self.assertEqual(count, 4)

    def test_count_tokens_empty(self):
        count = self.config.count_tokens("")
        self.assertEqual(count, 0)

    def test_count_tokens_whitespace_only(self):
        count = self.config.count_tokens("   \n\t  ")
        self.assertEqual(count, 0)

    def test_make_c_string(self):
        self.assertEqual(self.config.make_c_string(None), "<NULL>")
        self.assertEqual(self.config.make_c_string("data"), "data")
        self.assertEqual(self.config.make_c_string(""), "")

    def test_repr(self):
        self.config.max_size = 1000
        self.config.add_ignore_pattern("*.log")
        
        repr_str = repr(self.config)
        self.assertIn("max_size=1000", repr_str)
        self.assertIn("*.log", repr_str)

    def test_case_sensitivity(self):
        self.config.add_ignore_pattern("*.TXT")
        self.assertFalse(self.config.should_ignore("file.txt"))
        self.assertTrue(self.config.should_ignore("file.TXT"))

if __name__ == "__main__":
    unittest.main()