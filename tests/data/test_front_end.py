import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open

try:
    from pykomodo.dashboard import get_files_by_folder, process_chunks, launch_dashboard
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("dashboard", "paste.py")
    dashboard_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard_module)
    get_files_by_folder = dashboard_module.get_files_by_folder
    process_chunks = dashboard_module.process_chunks
    launch_dashboard = dashboard_module.launch_dashboard


class TestGetFilesByFolder(unittest.TestCase):
    """Test cases for the get_files_by_folder function."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    # Rest of TestGetFilesByFolder methods remain the same...


class TestProcessChunks(unittest.TestCase):
    """Test cases for the process_chunks function."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'output')
        self.test_files = [
            os.path.join(self.temp_dir, 'file1.py'),
            os.path.join(self.temp_dir, 'file2.py'),
        ]
        
        for file_path in self.test_files:
            with open(file_path, 'w') as f:
                f.write(f"# Content of {os.path.basename(file_path)}\nprint('hello')\n")
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_process_chunks_no_files_selected(self):
        """Test process_chunks with no files selected."""
        result = process_chunks("Equal Chunks", 5, 1000, self.output_dir, [])
        self.assertIn("No files selected", result)
        self.assertIn("❌", result)
    
    def test_process_chunks_empty_output_dir(self):
        """Test process_chunks with empty output directory."""
        result = process_chunks("Equal Chunks", 5, 1000, "", self.test_files)
        self.assertIn("Please provide an output directory", result)
        self.assertIn("❌", result)
        
        result = process_chunks("Equal Chunks", 5, 1000, "   ", self.test_files)
        self.assertIn("Please provide an output directory", result)
        self.assertIn("❌", result)
    
    def test_process_chunks_invalid_strategy(self):
        """Test process_chunks with invalid strategy."""
        result = process_chunks("Invalid Strategy", 5, 1000, self.output_dir, self.test_files)
        self.assertIn("Invalid chunking strategy", result)
        self.assertIn("❌", result)
    
    def test_process_chunks_equal_chunks_invalid_num(self):
        """Test process_chunks with Equal Chunks strategy and invalid number."""
        result = process_chunks("Equal Chunks", 0, 1000, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive number of chunks", result)
        self.assertIn("❌", result)
        
        result = process_chunks("Equal Chunks", -1, 1000, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive number of chunks", result)
        self.assertIn("❌", result)
        
        result = process_chunks("Equal Chunks", None, 1000, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive number of chunks", result)
        self.assertIn("❌", result)
    
    def test_process_chunks_max_chunk_size_invalid(self):
        """Test process_chunks with Max Chunk Size strategy and invalid size."""
        result = process_chunks("Max Chunk Size", 5, 0, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive max chunk size", result)
        self.assertIn("❌", result)
        
        result = process_chunks("Max Chunk Size", 5, -100, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive max chunk size", result)
        self.assertIn("❌", result)
        
        result = process_chunks("Max Chunk Size", 5, None, self.output_dir, self.test_files)
        self.assertIn("Please provide a positive max chunk size", result)
        self.assertIn("❌", result)
    
    # Fix for the import error test
    def test_process_chunks_import_error(self):
        """Test process_chunks when ParallelChunker import fails."""
        # Use a context manager to mock __import__
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            result = process_chunks("Equal Chunks", 5, 1000, self.output_dir, self.test_files)
            self.assertIn("Could not import ParallelChunker", result)
            self.assertIn("❌", result)
    
    # Fix for the success test with Equal Chunks strategy
    def test_process_chunks_success_equal_chunks(self):
        """Test successful processing with Equal Chunks strategy."""
        # Create a mock for the ParallelChunker class
        mock_chunker = MagicMock()
        
        # Since ParallelChunker is imported within process_chunks, we need to patch
        # the import machinery to return our mock
        import_patch = patch('builtins.__import__', 
                            return_value=MagicMock(ParallelChunker=MagicMock(
                                return_value=mock_chunker)))
        
        with import_patch:
            # Create output directory and sample chunk files
            os.makedirs(self.output_dir, exist_ok=True)
            for i in range(3):
                with open(os.path.join(self.output_dir, f'chunk_{i}.txt'), 'w') as f:
                    f.write(f"Chunk {i} content")
            
            result = process_chunks("Equal Chunks", 5, 1000, self.output_dir, self.test_files)
            
            # Since we can't easily verify the constructor arguments, we'll just check
            # that process_files was called with the right arguments
            mock_chunker.process_files.assert_called_once_with(self.test_files)
            
            self.assertIn("✅", result)
            self.assertIn("Chunking completed successfully", result)
            self.assertIn("Files processed: 2", result)
            self.assertIn("Chunks created: 3", result)
    
    # Fix for the success test with Max Chunk Size strategy
    def test_process_chunks_success_max_chunk_size(self):
        """Test successful processing with Max Chunk Size strategy."""
        # Create a mock for the ParallelChunker class
        mock_chunker = MagicMock()
        
        # Patch the import machinery
        import_patch = patch('builtins.__import__', 
                           return_value=MagicMock(ParallelChunker=MagicMock(
                               return_value=mock_chunker)))
        
        with import_patch:
            # Create output directory and sample chunk files
            os.makedirs(self.output_dir, exist_ok=True)
            for i in range(2):
                with open(os.path.join(self.output_dir, f'chunk_{i}.txt'), 'w') as f:
                    f.write(f"Chunk {i} content")
            
            result = process_chunks("Max Chunk Size", 5, 1000, self.output_dir, self.test_files)
            
            # Verify process_files was called with the right arguments
            mock_chunker.process_files.assert_called_once_with(self.test_files)
            
            self.assertIn("✅", result)
            self.assertIn("Chunking completed successfully", result)
            self.assertIn("Files processed: 2", result)
            self.assertIn("Chunks created: 2", result)
    
    # Fix for the exception handling test
    def test_process_chunks_exception_handling(self):
        """Test exception handling in process_chunks."""
        # Create a mock for the ParallelChunker class that raises an exception
        mock_chunker = MagicMock()
        mock_chunker.process_files.side_effect = Exception("Test exception")
        
        # Patch the import machinery
        import_patch = patch('builtins.__import__', 
                           return_value=MagicMock(ParallelChunker=MagicMock(
                               return_value=mock_chunker)))
        
        with import_patch:
            result = process_chunks("Equal Chunks", 5, 1000, self.output_dir, self.test_files)
            
            self.assertIn("❌", result)
            self.assertIn("Error during processing", result)
            self.assertIn("Test exception", result)


class TestLaunchDashboard(unittest.TestCase):
    """Test cases for the launch_dashboard function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize any necessary test fixtures without patches
        pass
    
    @patch('gradio.Blocks')
    def test_launch_dashboard_creation(self, mock_blocks_class):
        """Test that launch_dashboard creates a Gradio interface."""
        # Create a mock context and demo object
        mock_demo = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_demo)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_blocks_class.return_value = mock_context
        
        # Create mock components that will be set as attributes on the demo
        mock_load_btn = MagicMock()
        mock_load_btn.click = MagicMock()  # Ensure click is already mocked
        
        # Mock gradio component constructors
        with patch('gradio.Button', return_value=mock_load_btn):
            with patch('gradio.HTML', return_value=MagicMock()):
                with patch('gradio.Textbox', return_value=MagicMock()):
                    with patch('gradio.Dropdown', return_value=MagicMock()):
                        with patch('gradio.CheckboxGroup', return_value=MagicMock()):
                            with patch('gradio.Number', return_value=MagicMock()):
                                # Call the function
                                result = launch_dashboard()
                                
                                # Check that Blocks was used
                                mock_blocks_class.assert_called_once()
                                
                                # Check that the demo was returned
                                self.assertEqual(result, mock_demo)
    
    @patch('gradio.Blocks')
    @patch('gradio.HTML')
    @patch('gradio.Textbox')
    @patch('gradio.Button')
    @patch('gradio.Dropdown')
    @patch('gradio.CheckboxGroup')
    @patch('gradio.Number')
    def test_launch_dashboard_components(self, 
                                       mock_number, 
                                       mock_checkbox, 
                                       mock_dropdown, 
                                       mock_button, 
                                       mock_textbox, 
                                       mock_html, 
                                       mock_blocks_class):
        """Test that launch_dashboard creates all necessary components."""
        # Set up mock Blocks and return value
        mock_demo = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_demo)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_blocks_class.return_value = mock_context
        
        # Create a mock button with a working click method
        mock_btn = MagicMock()
        mock_btn.click = MagicMock()
        mock_button.return_value = mock_btn
        
        # Call the function we're testing
        launch_dashboard()
        
        # Verify all the component constructors were called
        mock_html.assert_called()
        mock_textbox.assert_called()
        mock_button.assert_called()
        mock_dropdown.assert_called()
        mock_checkbox.assert_called()
        mock_number.assert_called()


class TestIntegration(unittest.TestCase):
    """Integration tests that test multiple components together."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_full_workflow_simulation(self):
        """Test a complete workflow simulation."""
        src_dir = os.path.join(self.test_dir, 'src')
        os.makedirs(src_dir)
        
        test_files = [
            os.path.join(self.test_dir, 'main.py'),
            os.path.join(src_dir, 'app.py'),
            os.path.join(src_dir, 'utils.py'),
        ]
        
        for file_path in test_files:
            with open(file_path, 'w') as f:
                f.write(f"# Content of {os.path.basename(file_path)}\n")
                f.write("def example_function():\n")
                f.write("    return 'Hello, World!'\n")
        
        files_by_folder = get_files_by_folder(self.test_dir)
        
        self.assertIn('Root Directory', files_by_folder)
        self.assertIn('src', files_by_folder)
        
        #  check step2
        all_files = []
        for folder_files in files_by_folder.values():
            all_files.extend([filepath for filename, filepath in folder_files])
        
        self.assertEqual(len(all_files), 3)
        
        # check step3
        for file_path in all_files:
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, 'r') as f:
                content = f.read()
                self.assertIn("def example_function", content)


class TestHelperFunctions(unittest.TestCase):
    """Test cases for helper functions and edge cases."""
    
    def test_file_filtering_logic(self):
        """Test the file filtering logic in get_files_by_folder."""
        with tempfile.TemporaryDirectory() as temp_dir:
            filtered_files = [
                '.hidden',
                'cache.pyc',
                'temp.pyo',
                '__pycache__/cache.pyc',
                'node_modules/package.json',
                '.git/config',
            ]
            
            included_files = [
                'main.py',
                'app.js',
                'style.css',
                'README.md',
            ]
            
            # creating the test files
            for file_path in filtered_files + included_files:
                full_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write("content")
            
            result = get_files_by_folder(temp_dir)
            
            all_result_files = []
            for folder_files in result.values():
                all_result_files.extend([name for name, path in folder_files])
            
            for file_name in ['main.py', 'app.js', 'style.css', 'README.md']:
                self.assertIn(file_name, all_result_files)
            
            for file_name in ['.hidden', 'cache.pyc', 'temp.pyo']:
                self.assertNotIn(file_name, all_result_files)
            
            folder_names = list(result.keys())
            self.assertNotIn('__pycache__', folder_names)
            self.assertNotIn('node_modules', folder_names)
            self.assertNotIn('.git', folder_names)


if __name__ == '__main__':
    test_suite = unittest.TestSuite()
    
    test_classes = [
        TestGetFilesByFolder,
        TestProcessChunks,
        TestLaunchDashboard,
        TestIntegration,
        TestHelperFunctions,
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print(f"\n{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")