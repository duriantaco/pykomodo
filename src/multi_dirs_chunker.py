import os
import fnmatch
import sys
import concurrent.futures

BUILTIN_IGNORES = [
    "**/.git/**",
    "**/.idea/**",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "**/node_modules/**",
    "target",
    "venv",
]

class PriorityRule:
    def __init__(self, pattern, score):
        self.pattern = pattern
        self.score = score

class ParallelChunker:
    def __init__(
        self,
        equal_chunks=None,          
        max_chunk_size=None,       
        output_dir="chunks",
        user_ignore=None,
        user_unignore=None,
        binary_extensions=None,
        priority_rules=None,
        num_threads=4
    ):
        if equal_chunks is not None and max_chunk_size is not None:
            raise ValueError("Cannot specify both equal_chunks and max_chunk_size")
        if equal_chunks is None and max_chunk_size is None:
            raise ValueError("Must specify either equal_chunks or max_chunk_size")

        self.equal_chunks = equal_chunks
        self.max_chunk_size = max_chunk_size
        self.output_dir = output_dir
        self.num_threads = num_threads

        if user_ignore is None:
            user_ignore = []
        if user_unignore is None:
            user_unignore = []

        self.ignore_patterns = BUILTIN_IGNORES[:]
        self.ignore_patterns.extend(user_ignore)
        self.unignore_patterns = list(user_unignore)
        
        self.unignore_patterns.append("*.py")

        if binary_extensions is None:
            binary_extensions = ["exe", "dll", "so"]
        self.binary_exts = set(ext.lower() for ext in binary_extensions)

        self.priority_rules = []
        if priority_rules:
            for rule_data in priority_rules:
                if isinstance(rule_data, PriorityRule):
                    self.priority_rules.append(rule_data)
                else:
                    pat, score = rule_data
                    self.priority_rules.append(PriorityRule(pat, score))

        self.loaded_files = []

    def should_ignore_file(self, path):
        """
        Return True if `path` should be ignored based on patterns.
        """
        path = os.path.normpath(path)

        for pat in self.unignore_patterns:
            if self._matches_pattern(path, pat):
                return False

        for pat in self.ignore_patterns:
            if self._matches_pattern(path, pat):
                return True
        
        return False

    def _matches_pattern(self, path, pattern):
        if "node_modules" in pattern and "node_modules" in path:
            return True
                
        if "**" in pattern:
            pattern = pattern.replace("**", "*")
        
        return (fnmatch.fnmatch(path, pattern) or 
                fnmatch.fnmatch(os.path.basename(path), pattern))

    def is_binary_file(self, path):
        """
        If it's a .py file, return False directly.
        Otherwise, do the default checks.
        """
        _, ext = os.path.splitext(path)
        ext = ext.lstrip(".").lower()
        if ext == "py":
            return False

        if ext in self.binary_exts:
            return True
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                if b"\0" in chunk:
                    return True
        except OSError:
            return True
        return False

    def _collect_paths(self, dir_list):
        """
        Collect only those files that pass both `should_ignore_file == False`
        and `is_binary_file == False`.
        """
        collected = []
        for directory in dir_list:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    full_path = os.path.join(root, filename)

                    if self.should_ignore_file(full_path):
                        continue
                    if self.is_binary_file(full_path):
                        continue
                    if self.should_ignore_file(full_path):
                        continue
                    if self.is_binary_file(full_path):
                        continue
                    collected.append(full_path)
        return collected

    def _load_file_data(self, path):
        try:
            with open(path, "rb") as f:
                content = f.read()
            priority = self.calculate_priority(path)
            return (path, content, priority)
        except:
            return (path, None, 0)

    def calculate_priority(self, path):
       highest = 0
       basename = os.path.basename(path)
       for rule in self.priority_rules:
           if fnmatch.fnmatch(basename, rule.pattern):
               if rule.score > highest:
                   highest = rule.score
       return highest

    def process_directories(self, dirs):
        all_paths = self._collect_paths(dirs)
        self.loaded_files.clear()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_map = {executor.submit(self._load_file_data, p): p for p in all_paths}
            for future in concurrent.futures.as_completed(future_map):
                path, content, priority = future.result()
                if content is not None:
                    self.loaded_files.append((path, content, priority))

        self.loaded_files.sort(key=lambda x: (-x[2], x[0]))
        self._process_chunks()

    def process_directory(self, directory):
        self.process_directories([directory])

    def _split_tokens(self, content_bytes):
        try:
            text = content_bytes.decode("utf-8", errors="replace")
        except:
            text = ""
        return text.split()

    def _write_chunk(self, content_bytes, chunk_num):
        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
        try:
            with open(chunk_path, "wb") as f:
                f.write(content_bytes)
        except:
            pass

    def _process_chunks(self):
        if not self.loaded_files:
            return

        if self.equal_chunks:
            self._chunk_by_equal_parts()
        else:
            self._chunk_by_size()

    def _chunk_by_equal_parts(self):
        total_content = []
        total_size = 0
        
        for (path, content_bytes, priority) in self.loaded_files:
            try:
                content = content_bytes.decode("utf-8", errors="replace")
                size = len(content)
                total_content.append((path, content, size))
                total_size += size
            except:
                continue
        
        if not total_content:
            return
            
        n_chunks = self.equal_chunks
        target_chunk_size = max(1, total_size // n_chunks)
        
        current_chunk = []
        current_size = 0
        chunk_idx = 0
        
        for i in range(n_chunks):
            chunk_content = []
            
            while total_content and current_size < target_chunk_size:
                path, content, size = total_content[0]
                chunk_content.extend([
                    f"\n{'='*40}",
                    f"File: {path}",
                    f"{'='*40}\n",
                    content
                ])
                current_size += size
                total_content.pop(0)
            
            chunk_text = (
                f"{'='*80}\n"
                f"CHUNK {i + 1} OF {n_chunks}\n"
                f"{'='*80}\n\n"
                + "\n".join(chunk_content) if chunk_content else ""
                + "\n"
            )
            self._write_chunk(chunk_text.encode('utf-8'), i)
            
            current_size = 0

    def _chunk_by_size(self):
        chunk_number = 0
        for (path, content_bytes, priority) in self.loaded_files:
            try:
                content = content_bytes.decode("utf-8", errors="replace")
                lines = content.splitlines()
                
                if not lines:
                    empty_chunk = (
                        f"{'='*80}\n"
                        f"CHUNK {chunk_number + 1}\n"
                        f"{'='*80}\n\n"
                        f"{'='*40}\n"
                        f"File: {path}\n"
                        f"{'='*40}\n"
                        f"[Empty File]\n"
                    )
                    self._write_chunk(empty_chunk.encode('utf-8'), chunk_number)
                    chunk_number += 1
                    continue

                current_chunk_lines = []
                current_size = 0
                
                for line in lines:
                    line_size = len(line.split())  
                    
                    if current_size + line_size > self.max_chunk_size and current_chunk_lines:
                        chunk_header = [
                            "=" * 80,
                            f"CHUNK {chunk_number + 1}",
                            "=" * 80,
                            "",
                            "=" * 40,
                            f"File: {path}",
                            "=" * 40,
                            ""
                        ]
                        chunk_content = "\n".join(chunk_header + current_chunk_lines) + "\n"
                        self._write_chunk(chunk_content.encode('utf-8'), chunk_number)
                        chunk_number += 1
                        current_chunk_lines = []
                        current_size = 0
                    
                    current_chunk_lines.append(line)
                    current_size += line_size
                
                if current_chunk_lines:
                    chunk_header = [
                        "=" * 80,
                        f"CHUNK {chunk_number + 1}",
                        "=" * 80,
                        "",
                        "=" * 40,
                        f"File: {path}",
                        "=" * 40,
                        ""
                    ]
                    chunk_content = "\n".join(chunk_header + current_chunk_lines) + "\n"
                    self._write_chunk(chunk_content.encode('utf-8'), chunk_number)
                    chunk_number += 1

            except Exception as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)
                continue

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False