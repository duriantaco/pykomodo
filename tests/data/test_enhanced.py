import unittest
import os
import tempfile
import shutil
from src.enhanced_chunker import EnhancedParallelChunker

class TestEnhancedParallelChunker(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        self.python_file = os.path.join(self.test_dir, "example.py")
        with open(self.python_file, "w", encoding="utf-8") as f:
            f.write('''"""
                This is a test docstring.
                """
                import pandas as pd
                from datetime import datetime

                class TestClass:
                    def __init__(self):
                        pass
                        
                    def test_method(self):
                        # This is a comment
                        pass

                def standalone_function():
                    """Function docstring"""
                    return True
                ''')
        
        self.redundant_file = os.path.join(self.test_dir, "redundant.py")
        with open(self.redundant_file, "w", encoding="utf-8") as f:
            f.write('''def standalone_function():
                """Function docstring"""
                return True
            ''')
        
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_metadata_extraction(self):
        """Test if metadata is correctly extracted from files"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            extract_metadata=True
        )
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertEqual(len(chunk_files), 1)
        
        with open(os.path.join(self.output_dir, chunk_files[0]), 'r') as f:
            content = f.read()
            
        self.assertIn('METADATA:', content)
        self.assertIn('FUNCTIONS: standalone_function, test_method', content)
        self.assertIn('CLASSES: TestClass', content)
        self.assertIn('IMPORTS: import pandas, from datetime', content)
        self.assertIn('This is a test docstring', content)

    def test_relevance_scoring(self):
        """Test if relevance scoring works correctly"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            min_relevance_score=0.5  
        )
        
        low_relevance = os.path.join(self.test_dir, "low_relevance.py")
        with open(low_relevance, "w") as f:
            f.write("# Just comments\n# More comments\n# Even more comments\nx = 1")
        
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        for chunk_file in chunk_files:
            with open(os.path.join(self.output_dir, chunk_file), 'r') as f:
                content = f.read()
                if 'low_relevance.py' in content:
                    relevance_line = [l for l in content.split('\n') if 'RELEVANCE_SCORE:' in l][0]
                    score = float(relevance_line.split(':')[1].strip())
                    self.assertLess(score, 1.0)  

    def test_redundancy_removal(self):
        """Test if redundant content is properly removed"""
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            remove_redundancy=True
        )
        chunker.process_directory(self.test_dir)
        
        all_content = []
        chunk_files = sorted([f for f in os.listdir(self.output_dir) if f.startswith('chunk-')])
        for chunk_file in chunk_files:
            with open(os.path.join(self.output_dir, chunk_file), 'r') as f:
                all_content.append(f.read())
        
        redundant_count = sum(
            content.count('def standalone_function():') 
            for content in all_content
        )
        self.assertEqual(redundant_count, 1, "Redundant function should appear only once")

    def test_context_window_respect(self):
        """Test if chunks respect context window size"""
        small_window = 100
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            context_window=small_window
        )
        chunker.process_directory(self.test_dir)
        
        # Check each chunk size
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        for chunk_file in chunk_files:
            with open(os.path.join(self.output_dir, chunk_file), 'r') as f:
                content = f.read()
                # Allow some overhead for metadata
                self.assertLess(len(content), small_window * 1.5)

    def test_disable_features(self):
        """Test if features can be properly disabled"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            extract_metadata=False,
            add_summaries=False,
            remove_redundancy=False
        )
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        with open(os.path.join(self.output_dir, chunk_files[0]), 'r') as f:
            content = f.read()
            self.assertNotIn('METADATA:', content)
            self.assertGreater(
                content.count('def standalone_function():'),
                1
            )

if __name__ == '__main__':
    unittest.main()