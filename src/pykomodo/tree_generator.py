import io
from contextlib import redirect_stdout
from treeline.renderer import tree

class TreeGenerator:
    def __init__(self):
        self.tree_structure = None
        self.tree_header = None
    
    def generate_tree_structure(self, directory_path):
        try:
            f = io.StringIO()
            with redirect_stdout(f):
                tree(
                    directory=directory_path,
                    max_depth=3,
                    show_size=False,
                    show_all=False,
                    show_code_structure=False
                )
            return f.getvalue()
            
        except Exception:
            return "[Tree structure not available]"

    def prepare_tree_header(self, source_directory):
        if self.tree_structure is None:
            tree_content = self.generate_tree_structure(source_directory)
            self.tree_structure = tree_content
            
            self.tree_header = (
                "=" * 80 + "\n" +
                "PROJECT STRUCTURE\n" +
                "=" * 80 + "\n\n" +
                tree_content + "\n" +
                "=" * 80 + "\n\n"
            )
        
        return self.tree_header

    def reset(self):
        self.tree_structure = None
        self.tree_header = None