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
        user_ignore=None,
        user_unignore=None,
        binary_extensions=None,
        priority_rules=None,
        max_size=10 * 1024 * 1024,
        token_mode=False,
        output_dir=None,
        stream=False,
        num_threads=4,
        whole_chunk_mode=False,
        max_tokens_per_chunk=None,
        num_token_chunks=None
    ):
        self.max_size = max_size
        self.token_mode = token_mode
        self.output_dir = output_dir
        self.stream = stream
        self.num_threads = num_threads
        self.whole_chunk_mode = whole_chunk_mode
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.num_token_chunks = num_token_chunks

        if user_ignore is None:
            user_ignore = []
        if user_unignore is None:
            user_unignore = []

        self.ignore_patterns = BUILTIN_IGNORES[:]
        self.ignore_patterns.extend(user_ignore)
        self.unignore_patterns = list(user_unignore)

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
        _, ext = os.path.splitext(path)
        ext = ext.lstrip(".").lower()
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
        collected = []
        for directory in dir_list:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    full_path = os.path.join(root, filename)
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

    def _write_to_stdout(self, data_bytes):
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(data_bytes)
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(data_bytes.decode("utf-8", "replace"))
            sys.stdout.flush()

    def _write_chunk(self, content_bytes, chunk_num):
        if self.stream:
            self._write_to_stdout(content_bytes)
        else:
            if self.output_dir:
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
            else:
                chunk_path = f"chunk-{chunk_num}.txt"
            try:
                with open(chunk_path, "wb") as f:
                    f.write(content_bytes)
            except:
                pass

    def _write_chunk_single_file(self, aggregator_file, content_bytes):
        if aggregator_file is None:
            self._write_to_stdout(content_bytes)
        else:
            aggregator_file.write(content_bytes)

    def _process_chunks(self):
        if not self.loaded_files:
            return

        chunk_size = self.max_size
        chunk_number = 0
        aggregator_file = None
        if self.whole_chunk_mode:
            if self.stream:
                aggregator_file = None
            else:
                out_name = (
                    os.path.join(self.output_dir, "whole_chunk_mode-output.txt")
                    if self.output_dir else "whole_chunk_mode-output.txt"
                )
                try:
                    aggregator_file = open(out_name, "wb")
                except:
                    aggregator_file = None

        if self.token_mode:
            if self.num_token_chunks and self.num_token_chunks > 0:
                self._chunk_by_num_token_chunks(aggregator_file)
            elif self.max_tokens_per_chunk and self.max_tokens_per_chunk > 0:
                self._chunk_by_max_tokens(aggregator_file)
            else:
                self._default_token_chunking(aggregator_file)
        else:
            self._byte_chunking(aggregator_file)

        if aggregator_file and not self.stream:
            aggregator_file.close()

    def _chunk_by_num_token_chunks(self, aggregator_file):
        chunk_number = 0
        all_files = []
        total_size = 0
        
        for (path, content_bytes, priority) in self.loaded_files:
            try:
                content = content_bytes.decode("utf-8", errors="replace")
                total_size += len(content)
                all_files.append((path, content))
            except:
                continue
        
        if not all_files:
            return
            
        size_per_chunk = total_size // self.num_token_chunks
        
        current_chunk = []
        current_size = 0
        chunk_count = 0
        
        for path, content in all_files:
            if current_size + len(content) > size_per_chunk and chunk_count < self.num_token_chunks - 1:
                if current_chunk:
                    chunk_content = (
                        f"{'='*80}\n"
                        f"CHUNK {chunk_count + 1} OF {self.num_token_chunks}\n"
                        f"{'='*80}\n\n"
                        + "\n".join(current_chunk)
                        + "\n"
                    )
                    
                    if self.whole_chunk_mode:
                        self._write_chunk_single_file(aggregator_file, chunk_content.encode('utf-8'))
                    else:
                        self._write_chunk(chunk_content.encode('utf-8'), chunk_count)
                    
                    chunk_count += 1
                    current_chunk = []
                    current_size = 0
            
            current_chunk.extend([
                f"\n{'='*40}",
                f"File: {path}",
                f"{'='*40}\n",
                content
            ])
            current_size += len(content)
        
        if current_chunk:
            chunk_content = (
                f"{'='*80}\n"
                f"CHUNK {chunk_count + 1} OF {self.num_token_chunks}\n"
                f"{'='*80}\n\n"
                + "\n".join(current_chunk)
                + "\n"
            )
            
            if self.whole_chunk_mode:
                self._write_chunk_single_file(aggregator_file, chunk_content.encode('utf-8'))
            else:
                self._write_chunk(chunk_content.encode('utf-8'), chunk_count)

    def _chunk_by_max_tokens(self, aggregator_file):
        chunk_number = 0
        for (path, content_bytes, priority) in self.loaded_files:
            prefix = f"File: {path}\n".encode("utf-8")
            tokens = self._split_tokens(content_bytes)
            if not tokens:
                empty_chunk = prefix + b"\n"
                if self.whole_chunk_mode:
                    self._write_chunk_single_file(aggregator_file, empty_chunk)
                else:
                    self._write_chunk(empty_chunk, chunk_number)
                    chunk_number += 1
                continue

            idx = 0
            total_tokens = len(tokens)
            while idx < total_tokens:
                sub_list = tokens[idx : idx + self.max_tokens_per_chunk]
                idx += len(sub_list)
                data_str = f"File: {path}\n{' '.join(sub_list)}\n"
                data_bytes = data_str.encode("utf-8")
                if self.whole_chunk_mode:
                    self._write_chunk_single_file(aggregator_file, data_bytes)
                else:
                    self._write_chunk(data_bytes, chunk_number)
                    chunk_number += 1

    def _default_token_chunking(self, aggregator_file):
        chunk_number = 0
        for (path, content_bytes, priority) in self.loaded_files:
            prefix = f"File: {path}\n".encode("utf-8")
            tokens = self._split_tokens(content_bytes)
            if not tokens:
                empty_chunk = prefix + b"\n"
                if self.whole_chunk_mode:
                    self._write_chunk_single_file(aggregator_file, empty_chunk)
                else:
                    self._write_chunk(empty_chunk, chunk_number)
                    chunk_number += 1
                continue

            idx = 0
            total_tokens = len(tokens)
            # fallback to self.max_size as "tokens" if none provided
            chunk_size_tokens = self.max_size
            while idx < total_tokens:
                sub_list = tokens[idx : idx + chunk_size_tokens]
                idx += len(sub_list)
                data_str = f"File: {path}\n{' '.join(sub_list)}\n"
                data_bytes = data_str.encode("utf-8")
                if self.whole_chunk_mode:
                    self._write_chunk_single_file(aggregator_file, data_bytes)
                else:
                    self._write_chunk(data_bytes, chunk_number)
                    chunk_number += 1

    def _byte_chunking(self, aggregator_file):
        chunk_size = self.max_size
        chunk_number = 0
        sep = b"\n"
        for (path, content_bytes, priority) in self.loaded_files:
            prefix = f"File: {path}\n".encode("utf-8")
            needed = len(prefix) + len(content_bytes) + len(sep)
            if self.whole_chunk_mode:
                if needed <= chunk_size:
                    self._write_chunk_single_file(aggregator_file, prefix + content_bytes + sep)
                else:
                    pos = 0
                    remaining = len(content_bytes)
                    while remaining > 0:
                        can_take = chunk_size - len(prefix) - len(sep)
                        taking = min(remaining, can_take)
                        chunk_data = prefix + content_bytes[pos : pos + taking] + sep
                        self._write_chunk_single_file(aggregator_file, chunk_data)
                        pos += taking
                        remaining -= taking
            else:
                if needed <= chunk_size:
                    self._write_chunk(prefix + content_bytes + sep, chunk_number)
                    chunk_number += 1
                else:
                    pos = 0
                    remaining = len(content_bytes)
                    while remaining > 0:
                        can_take = chunk_size - len(prefix) - len(sep)
                        taking = min(remaining, can_take)
                        chunk_data = prefix + content_bytes[pos : pos + taking] + sep
                        self._write_chunk(chunk_data, chunk_number)
                        chunk_number += 1
                        pos += taking
                        remaining -= taking

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
