from pykomodo.multi_dirs_chunker import ParallelChunker

def test_should_ignore_file():
    chunker = ParallelChunker(equal_chunks=1, output_dir="chunks", user_ignore=[], user_unignore=[])
    chunker.current_walk_root = "/test_project"
    chunker.ignore_patterns = ["**/node_modules/**"]

    chunker.unignore_patterns = []
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.py") == True
    assert chunker.should_ignore_file("/test_project/src/main.py") == False
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.js") == True
    
    chunker.unignore_patterns = ["*.py"]
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.py") == False 
    assert chunker.should_ignore_file("/test_project/src/main.py") == False 
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.js") == True 
    
    chunker.unignore_patterns = ["**/node_modules/**/*.js"]
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.py") == True  
    assert chunker.should_ignore_file("/test_project/node_modules/some_module.js") == False  
    
    assert chunker.should_ignore_file("/test_project/subdir/node_modules/another_module.py") == True
    chunker.unignore_patterns = ["*.py"]
    assert chunker.should_ignore_file("/test_project/subdir/node_modules/another_module.py") == False

if __name__ == "__main__":
    test_should_ignore_file()