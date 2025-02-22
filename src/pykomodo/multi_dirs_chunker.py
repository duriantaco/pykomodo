import os
import fnmatch
import re
import concurrent.futures
import ast  

BUILTIN_IGNORES = [
    "**/.git/**",
    "**/.idea/**",
    "**/.vscode/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "**/.DS_Store",
    "**/node_modules/**",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "**/node_modules/**",
    "target",
    "venv",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.bmp",
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
        num_threads=4,
        dry_run=False,
        semantic_chunking=False
    ):
        if equal_chunks is not None and max_chunk_size is not None:
            raise ValueError("Cannot specify both equal_chunks and max_chunk_size")
        if equal_chunks is None and max_chunk_size is None:
            raise ValueError("Must specify either equal_chunks or max_chunk_size")

        self.equal_chunks = equal_chunks
        self.max_chunk_size = max_chunk_size
        self.output_dir = output_dir
        self.num_threads = num_threads
        self.dry_run = dry_run 
        self.semantic_chunking = semantic_chunking

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
        self.current_walk_root = None

    def is_absolute_pattern(self, pattern):
        if pattern.startswith("/"):
            return True
        if re.match(r"^[a-zA-Z]:\\", pattern):
            return True
        return False

    def _match_segments(self, path_segs, pattern_segs, pi=0, pj=0):
        if pj == len(pattern_segs):
            return pi == len(path_segs)
        if pi == len(path_segs):
            return all(seg == '**' for seg in pattern_segs[pj:])
        seg_pat = pattern_segs[pj]
        if seg_pat == "**":
            if self._match_segments(path_segs, pattern_segs, pi, pj + 1):
                return True
            return self._match_segments(path_segs, pattern_segs, pi + 1, pj)
        if fnmatch.fnmatch(path_segs[pi], seg_pat):
            return self._match_segments(path_segs, pattern_segs, pi + 1, pj + 1)
        return False

    def _double_star_fnmatch(self, path, pattern):
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")
        return self._match_segments(path.split("/"), pattern.split("/"))

    def _matches_pattern(self, abs_path, rel_path, pattern):
        target = abs_path if self.is_absolute_pattern(pattern) else rel_path

        if "**" in pattern:
            if self._double_star_fnmatch(target, pattern):
                return True
        else:
            if fnmatch.fnmatch(target, pattern):
                return True
        if not self.is_absolute_pattern(pattern) and "/" not in pattern:
            if fnmatch.fnmatch(os.path.basename(abs_path), pattern):
                return True
        return False

    def should_ignore_file(self, path):
        abs_path = os.path.abspath(path)
        root = self.current_walk_root or os.path.dirname(abs_path)
        rel_path = os.path.relpath(abs_path, start=root).replace("\\", "/")
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]

        for pat in self.unignore_patterns:
            if self._matches_pattern(abs_path, rel_path, pat):
                return False

        for pat in self.ignore_patterns:
            if self._matches_pattern(abs_path, rel_path, pat):
                return True

        return False

    def is_binary_file(self, path):
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
        collected = []
        for directory in dir_list:
            self.current_walk_root = os.path.abspath(directory)
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if os.path.commonprefix([
                        os.path.abspath(self.output_dir),
                        os.path.abspath(full_path)
                    ]) == os.path.abspath(self.output_dir):
                        continue
                    if self.should_ignore_file(full_path):
                        continue
                    collected.append(full_path)

        return collected

    def _load_file_data(self, path):
        try:
            with open(path, "rb") as f:
                content = f.read()
            return path, content, self.calculate_priority(path)
        except:
            return path, None, 0

    def calculate_priority(self, path):
        highest = 0
        basename = os.path.basename(path)
        for rule in self.priority_rules:
            if fnmatch.fnmatch(basename, rule.pattern):
                highest = max(highest, rule.score)
        return highest

    def process_directories(self, dirs):
        all_paths = self._collect_paths(dirs)
        self.loaded_files.clear()
        if self.dry_run:
            print("[DRY-RUN] The following files would be processed (in priority order):")
            tmp_loaded = []
            for p in all_paths:
                priority = self.calculate_priority(p)
                tmp_loaded.append((p, priority))
            tmp_loaded.sort(key=lambda x: -x[1])  
            for path, pr in tmp_loaded:
                print(f"  - {path} (priority={pr})")
            return  

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as ex:
            future_map = {ex.submit(self._load_file_data, p): p for p in all_paths}
            for fut in concurrent.futures.as_completed(future_map):
                path, content, priority = fut.result()
                if content is not None and not self.is_binary_file(path):
                    self.loaded_files.append((path, content, priority))
        self.loaded_files.sort(key=lambda x: (-x[2], x[0]))
        self._process_chunks()

    def process_directory(self, directory):
        self.process_directories([directory])

    def _split_tokens(self, content_bytes):
        try:
            return content_bytes.decode("utf-8", errors="replace").split()
        except:
            return []

    def _write_chunk(self, content_bytes, chunk_num):
        os.makedirs(self.output_dir, exist_ok=True)
        p = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
        try:
            with open(p, "wb") as f:
                f.write(content_bytes)
        except:
            pass

    def _process_chunks(self):
        if not self.loaded_files:
            return
        if self.semantic_chunking:
            self._chunk_by_semantic()
        elif self.equal_chunks:
            self._chunk_by_equal_parts()
        else:
            self._chunk_by_size()

    def _chunk_by_equal_parts(self):
        total_content = []
        total_size = 0
        for (path, content_bytes, _) in self.loaded_files:
            try:
                c = content_bytes.decode("utf-8", errors="replace")
                s = len(c)
                total_content.append((path, c, s))
                total_size += s
            except:
                continue
        if not total_content:
            return
        n_chunks = self.equal_chunks
        tgt = max(1, total_size // n_chunks)
        cur_size = 0
        for i in range(n_chunks):
            chunk_content = []
            while total_content and cur_size < tgt:
                p, c, s = total_content[0]
                chunk_content.extend([
                    "\n" + "="*40,
                    f"File: {p}",
                    "="*40 + "\n",
                    c
                ])
                cur_size += s
                total_content.pop(0)
            txt = (
                "="*80 + "\n"
                + f"CHUNK {i + 1} OF {n_chunks}\n"
                + "="*80 + "\n\n"
                + "\n".join(chunk_content)
                + "\n"
            )
            self._write_chunk(txt.encode("utf-8"), i)
            cur_size = 0

    def _chunk_by_size(self):
        idx = 0
        for (path, content_bytes, _) in self.loaded_files:
            try:
                c = content_bytes.decode("utf-8", errors="replace")
                lines = c.splitlines()
                if not lines:
                    t = (
                        "="*80 + "\n"
                        + f"CHUNK {idx + 1}\n"
                        + "="*80 + "\n\n"
                        + "="*40 + "\n"
                        + f"File: {path}\n"
                        + "="*40 + "\n"
                        + "[Empty File]\n"
                    )
                    self._write_chunk(t.encode("utf-8"), idx)
                    idx += 1
                    continue
                current_chunk_lines = []
                current_size = 0
                for line in lines:
                    line_size = len(line.split())
                    if current_size + line_size > self.max_chunk_size and current_chunk_lines:
                        h = [
                            "="*80,
                            f"CHUNK {idx + 1}",
                            "="*80,
                            "",
                            "="*40,
                            f"File: {path}",
                            "="*40,
                            ""
                        ]
                        chunk_data = "\n".join(h + current_chunk_lines) + "\n"
                        self._write_chunk(chunk_data.encode("utf-8"), idx)
                        idx += 1
                        current_chunk_lines = []
                        current_size = 0
                    current_chunk_lines.append(line)
                    current_size += line_size
                if current_chunk_lines:
                    h = [
                        "="*80,
                        f"CHUNK {idx + 1}",
                        "="*80,
                        "",
                        "="*40,
                        f"File: {path}",
                        "="*40,
                        ""
                    ]
                    chunk_data = "\n".join(h + current_chunk_lines) + "\n"
                    self._write_chunk(chunk_data.encode("utf-8"), idx)
                    idx += 1
            except:
                continue

    def _chunk_by_semantic(self):
        """
        For each loaded file:
        - If .py => parse AST, chunk by top-level function/class
        - Otherwise => fallback to one chunk or call your old logic.
        """
        chunk_index = 0
        for (path, content_bytes, priority) in self.loaded_files:
            try:
                text = content_bytes.decode("utf-8", errors="replace")
            except:
                continue

            if path.endswith(".py"):
                chunk_index = self._chunk_python_file_ast(path, text, chunk_index)
            else:
                chunk_index = self._chunk_nonpython_file_by_size(path, text, chunk_index)

    def _chunk_nonpython_file_by_size(self, path, text, chunk_index):
        lines = text.splitlines()
        if not lines:
            t = (
                "="*80 + "\n"
                + f"CHUNK {chunk_index + 1}\n"
                + "="*80 + "\n\n"
                + "="*40 + "\n"
                + f"File: {path}\n"
                + "="*40 + "\n"
                + "[Empty File]\n"
            )
            self._write_chunk(t.encode("utf-8"), chunk_index)
            return chunk_index + 1

        current_chunk_lines = []
        current_size = 0
        idx = chunk_index
        for line in lines:
            line_size = len(line.split())
            if self.max_chunk_size and (current_size + line_size) > self.max_chunk_size and current_chunk_lines:
                chunk_data = self._format_chunk_content(path, current_chunk_lines, idx)
                self._write_chunk(chunk_data.encode("utf-8"), idx)
                idx += 1
                current_chunk_lines = []
                current_size = 0
            current_chunk_lines.append(line)
            current_size += line_size

        if current_chunk_lines:
            chunk_data = self._format_chunk_content(path, current_chunk_lines, idx)
            self._write_chunk(chunk_data.encode("utf-8"), idx)
            idx += 1

        return idx

    def _format_chunk_content(self, path, lines, idx):
        h = [
            "="*80,
            f"CHUNK {idx + 1}",
            "="*80,
            "",
            "="*40,
            f"File: {path}",
            "="*40,
            ""
        ]
        return "\n".join(h + lines) + "\n"

    def _chunk_python_file_ast(self, path, text, chunk_index):
        import ast
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            chunk_data = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{text}"
            self._write_chunk(chunk_data.encode("utf-8"), chunk_index)
            return chunk_index + 1

        lines = text.splitlines()

        node_boundaries = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node_type = "Function"
                label = f"{node_type}: {node.name}"
            elif isinstance(node, ast.ClassDef):
                label = f"Class: {node.name}"
            else:
                continue
            start = node.lineno
            end = getattr(node, 'end_lineno', start)
            node_boundaries.append((start, end, label))

        node_boundaries.sort(key=lambda x: x[0])

        expanded_blocks = []
        prev_end = 1
        for (start, end, label) in node_boundaries:
            if start > prev_end:
                expanded_blocks.append((prev_end, start - 1, "GLOBAL CODE"))
            expanded_blocks.append((start, end, label))
            prev_end = end + 1
        if prev_end <= len(lines):
            expanded_blocks.append((prev_end, len(lines), "GLOBAL CODE"))

        code_blocks = []
        for (start, end, label) in expanded_blocks:
            snippet = lines[start - 1 : end]
            block_text = f"{label} (lines {start}-{end})\n" + "\n".join(snippet)
            code_blocks.append(block_text)

        current_lines = []
        current_count = 0

        for block in code_blocks:
            block_size = len(block.splitlines())

            if not self.max_chunk_size:
                current_lines.append(block)
                current_count += block_size
                continue

            if block_size > self.max_chunk_size:
                # flush whatever wuz in current_lines
                if current_lines:
                    chunk_data = "\n\n".join(current_lines)
                    final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_data}"
                    self._write_chunk(final_text.encode("utf-8"), chunk_index)
                    chunk_index += 1
                    current_lines = []
                    current_count = 0

                big_block_data = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{block}"
                self._write_chunk(big_block_data.encode("utf-8"), chunk_index)
                chunk_index += 1
                # done, skip to the next block
                continue

            if current_count + block_size > self.max_chunk_size and current_lines:
                chunk_data = "\n\n".join(current_lines)
                final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_data}"
                self._write_chunk(final_text.encode("utf-8"), chunk_index)
                chunk_index += 1

                current_lines = []
                current_count = 0

            current_lines.append(block)
            current_count += block_size

        if current_lines:
            chunk_data = "\n\n".join(current_lines)
            final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_data}"
            self._write_chunk(final_text.encode("utf-8"), chunk_index)
            chunk_index += 1

        return chunk_index


    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
