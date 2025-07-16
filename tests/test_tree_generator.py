import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from pykomodo.tree_generator import TreeGenerator

class TestTreeGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = TreeGenerator()
        self.test_dir = tempfile.mkdtemp()
        
        os.makedirs(os.path.join(self.test_dir, "src"))
        os.makedirs(os.path.join(self.test_dir, "tests"))
        
        with open(os.path.join(self.test_dir, "README.md"), "w") as f:
            f.write("# Test Project")
        with open(os.path.join(self.test_dir, "src", "main.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(self.test_dir, "tests", "test_main.py"), "w") as f:
            f.write("import unittest")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_initial_state(self):
        self.assertIsNone(self.generator.tree_structure)
        self.assertIsNone(self.generator.tree_header)

    @patch('pykomodo.tree_generator.tree')
    def test_generate_tree_structure_success(self, mock_tree):
        mock_tree.return_value = None
        
        with patch('sys.stdout', new_callable=lambda: MagicMock()) as mock_stdout:
            mock_stdout.write = MagicMock()
            
            with patch('io.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = "fake tree output"
                
                result = self.generator.generate_tree_structure(self.test_dir)
                
                self.assertEqual(result, "fake tree output")

    def test_generate_tree_structure_exception(self):
        with patch('pykomodo.tree_generator.tree', side_effect=Exception("Tree failed")):
            result = self.generator.generate_tree_structure(self.test_dir)
            self.assertEqual(result, "[Tree structure not available]")

    @patch('pykomodo.tree_generator.tree')
    def test_prepare_tree_header_first_call(self, mock_tree):
        with patch.object(self.generator, 'generate_tree_structure', return_value="sample tree"):
            header = self.generator.prepare_tree_header(self.test_dir)
            
            self.assertIn("PROJECT STRUCTURE", header)
            self.assertIn("sample tree", header)
            self.assertIn("=" * 80, header)
            self.assertIsNotNone(self.generator.tree_structure)
            self.assertIsNotNone(self.generator.tree_header)

    @patch('pykomodo.tree_generator.tree')
    def test_prepare_tree_header_cached(self, mock_tree):
        with patch.object(self.generator, 'generate_tree_structure', return_value="sample tree") as mock_gen:
            header1 = self.generator.prepare_tree_header(self.test_dir)
            header2 = self.generator.prepare_tree_header(self.test_dir)
            
            self.assertEqual(header1, header2)
            mock_gen.assert_called_once()

    def test_reset(self):
        self.generator.tree_structure = "some structure"
        self.generator.tree_header = "some header"
        
        self.generator.reset()
        
        self.assertIsNone(self.generator.tree_structure)
        self.assertIsNone(self.generator.tree_header)

    @patch('pykomodo.tree_generator.tree')
    def test_header_format(self, mock_tree):
        with patch.object(self.generator, 'generate_tree_structure', return_value="test tree"):
            header = self.generator.prepare_tree_header(self.test_dir)
            
            lines = header.split('\n')
            self.assertTrue(lines[0].startswith("="))
            self.assertEqual(lines[1], "PROJECT STRUCTURE")
            self.assertTrue(lines[2].startswith("="))
            self.assertIn("file organization", lines[3])

    def test_generate_tree_with_real_directory(self):
        try:
            result = self.generator.generate_tree_structure(self.test_dir)
            self.assertIsInstance(result, str)
            self.assertNotEqual(result, "[Tree structure not available]")
        except ImportError:
            result = self.generator.generate_tree_structure(self.test_dir)
            self.assertEqual(result, "[Tree structure not available]")

    def test_multiple_resets(self):
        with patch.object(self.generator, 'generate_tree_structure', return_value="tree"):
            self.generator.prepare_tree_header(self.test_dir)
            self.assertIsNotNone(self.generator.tree_header)
            
            self.generator.reset()
            self.assertIsNone(self.generator.tree_header)
            
            self.generator.reset()
            self.assertIsNone(self.generator.tree_header)

    @patch('pykomodo.tree_generator.tree')
    def test_prepare_header_after_reset(self, mock):
        with patch.object(self.generator, 'generate_tree_structure', return_value="tree1") as mock_gen:
            header1 = self.generator.prepare_tree_header(self.test_dir)
            
            self.generator.reset()
            
            mock_gen.return_value = "tree2"
            header2 = self.generator.prepare_tree_header(self.test_dir)
            
            self.assertNotEqual(header1, header2)
            self.assertEqual(mock_gen.call_count, 2)

if __name__ == "__main__":
    unittest.main()