import os
import fnmatch
import re
import concurrent.futures
from typing import Optional, List, Tuple
from pykomodo.tree_generator import TreeGenerator
from pykomodo.pdf_processor import PDFProcessor
import ast

BUILTIN_IGNORES = [
    "**/.git/**",
    "**/.svn/**",
    "**/.hg/**",
    "**/.idea/**",
    "**/.vscode/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/.pytest_cache/**",
    "**/.coverage",
    "**/.tox/**",
    "**/.eggs/**",
    "**/Cython/Debugger/**",    
    "**/*.egg-info/**",
    "**/build/**",
    "**/dist/**",
    "**/venv/**",
    "**/.venv/**",
    "**/env/**",
    "**/ENV/**",
    "**/virtualenv/**",
    "**/site-packages/**",
    "**/pip/**",
    "**/.DS_Store",
    "**/Thumbs.db",
    "**/node_modules/**",
    "**/*.env",
    "**/.env", 
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg",
    "**/*.gif",
    "**/*.webp",
    "**/*.bmp",
    "**/*.mp3",
    "**/*.mp4",
    "**/tmp/**",
    "**/temp/**",
    "**/var/folders/**",
    "**/test/data/**",
    "**/tests/data/**",
    "**/test_data/**",
    "**/tests_data/**",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "target",
    "venv"
]

class PriorityRule:
    def __init__(self, pattern, score):
        self.pattern = pattern
        self.score = score
    
class ChunkWriterInterface:
    def __init__(self, chunker):
        self.chunker = chunker
    
    def write_chunk(self, content_bytes, chunk_num):
        self.chunker._write_chunk(content_bytes, chunk_num)

class ParallelChunker:
    DIR_IGNORE_NAMES = [
        "venv",
        ".venv",
        "env",
        "node_modules",
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        ".pytest_cache",
        ".tox",
        ".eggs",
        "build",
        "dist"
    ]
    def __init__(
        self,
        equal_chunks: Optional[int] = None,
        max_chunk_size: Optional[int] = None,
        output_dir: str = "chunks",
        user_ignore: Optional[List[str]] = None,
        user_unignore: Optional[List[str]] = None,
        binary_extensions: Optional[List[str]] = None,
        priority_rules: Optional[List[Tuple[str,int]]] = None,
        num_threads: int = 4,
        dry_run: bool = False,
        semantic_chunking: bool = False,
        file_type: Optional[str] = None,
        verbose: bool = False
        ) -> None:
        
        if equal_chunks is not None and max_chunk_size is not None:
            raise ValueError("Cannot specify both equal_chunks and max_chunk_size")
        if equal_chunks is None and max_chunk_size is None:
            raise ValueError("Must specify either equal_chunks or max_chunk_size")
        self.dir_ignore_names = self.DIR_IGNORE_NAMES
        self.equal_chunks = equal_chunks
        self.max_chunk_size = max_chunk_size
        self.output_dir = output_dir
        self.num_threads = num_threads
        self.dry_run = dry_run 
        self.semantic_chunking = semantic_chunking
        self.file_type = file_type.lower() if file_type else None
        self.verbose = verbose

        if user_ignore is None:
            user_ignore = []
        if user_unignore is None:
            user_unignore = []

        self.ignore_patterns = BUILTIN_IGNORES[:]
        self.ignore_patterns.extend(user_ignore)
        self.unignore_patterns = list(user_unignore)
        found_venv = False
        if user_unignore:
            for pattern in user_unignore:
                if "site-packages" in pattern or "venv" in pattern:
                    found_venv = True
                    break

        if not found_venv:
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
        self.tree_generator = TreeGenerator()

        pdf_chunk_size = 1000
        if max_chunk_size:
            pdf_chunk_size = max_chunk_size

        self.pdf_processor = PDFProcessor(pdf_chunk_size)

    def _get_text_content(self, path, content_bytes):
        if path.endswith(".pdf"):
            return self.pdf_processor.extract_text_from_pdf(path)
        else:
            text = content_bytes.decode("utf-8", errors="replace")
            text = self._filter_api_keys(text)
            return text

    def is_absolute_pattern(self, pattern):
        if pattern.startswith("/"):
            return True
        if re.match(r"^[a-zA-Z]:\\", pattern):
            return True
        return False
    
    def _contains_api_key(self, line: str) -> bool:
        pattern = r'[\'"].*[a-zA-Z0-9_-]{20,}.*[\'"]'
        return bool(re.search(pattern, line))

    def _filter_api_keys(self, text: str) -> str:
        lines = text.splitlines()
        filtered_lines = []
        for line in lines:
            contains_key = self._contains_api_key(line)
            if contains_key:
                filtered_lines.append("[API_KEY_REDACTED]")
            else:
                filtered_lines.append(line)
        result = "\n".join(filtered_lines)
        return result

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
        if self.is_absolute_pattern(pattern):
            target = abs_path
        else:
            target = rel_path

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
    
    def _read_ignore_file(self, directory):
        for filename in ['.pykomodo-ignore', '.gitignore']:
            ignore_file_path = os.path.join(directory, filename)
            if os.path.exists(ignore_file_path):
                try:
                    with open(ignore_file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                if filename == '.gitignore' and '**' not in line:
                                    if not line.startswith('/'):
                                        line = f"**/{line}"
                                    if line.endswith('/'):
                                        line = f"{line}**"
                                self.ignore_patterns.append(line)
                except:
                    print(f"Error reading {filename}")

    def should_ignore_file(self, path):
        abs_path = os.path.abspath(path)
        root = self.current_walk_root or os.path.dirname(abs_path)
        rel_path = os.path.relpath(abs_path, start=root).replace("\\", "/")
        for pat in self.ignore_patterns:
            if self._matches_pattern(abs_path, rel_path, pat):
                for unignore_pat in self.unignore_patterns:
                    if self._matches_pattern(abs_path, rel_path, unignore_pat):
                        return False  
                return True  
        
        return False

    def is_binary_file(self, path):
        ext = path.split(".")[-1].lower()
        if ext in {"py", "pdf"}:
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
                new_dirs = []
                for d in dirs:
                    if d not in self.dir_ignore_names:
                        new_dirs.append(d)
                dirs[:] = new_dirs
                
                for filename in files:
                    full_path = os.path.join(root, filename)
                    
                    if self.file_type:
                        if not filename.lower().endswith(f".{self.file_type}"):
                            continue

                    if os.path.commonprefix([os.path.abspath(self.output_dir), os.path.abspath(full_path)]) == os.path.abspath(self.output_dir):
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

    def process_directories(self, dirs: List[str]) -> None:
        if dirs:
            self.current_walk_root = os.path.abspath(dirs[0])
        
        self.tree_generator.reset()
        
        for directory in dirs:
            self._read_ignore_file(directory)
        
        all_paths = self._collect_paths(dirs)
        self.loaded_files.clear()
        
        if self.dry_run:
            self._handle_dry_run(all_paths)
            return
        
        self._load_files_parallel(all_paths)
        self.loaded_files.sort(key=lambda x: (-x[2], x[0]))
        self._process_chunks()
    
    def _handle_dry_run(self, paths):
        print("[DRY-RUN] The following files would be processed (in priority order):")
        
        files = []
        for path in paths:
            priority = self.calculate_priority(path)
            files.append((path, priority))
        
        files.sort(key=lambda x: -x[1])
        
        for path, priority in files:
            print(f"  - {path} (priority={priority})")

    def _load_files_parallel(self, all_paths):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads)
        futures = {}
        
        for path in all_paths:
            future = executor.submit(self._load_file_data, path)
            futures[future] = path
        
        for future in concurrent.futures.as_completed(futures):
            path, content, priority = future.result()
            
            if content and not self.is_binary_file(path):
                self.loaded_files.append((path, content, priority))
        
        executor.shutdown()

    def process_file(self, file_path: str, custom_chunk_size: Optional[int] = None, force_process: bool = False) -> None:
        if not os.path.isfile(file_path):
            raise ValueError(f"File not found: {file_path}")
            
        if self.should_ignore_file(file_path) and not force_process and not self.dry_run:
            print(f"Skipping ignored file: {file_path}")
            return
            
        if self.dry_run:
            priority = self.calculate_priority(file_path)
            print(f"[DRY-RUN] Would process file: {file_path} (priority={priority})")
            return
            
        if self.is_binary_file(file_path) and not file_path.endswith(".pdf") and not force_process:
            print(f"Skipping binary file: {file_path}")
            return
            
        path, content, priority = self._load_file_data(file_path)
        if content is None:
            print(f"Error loading file: {file_path}")
            return
            
        self.loaded_files = [(path, content, priority)]
        
        original_max_chunk_size = None
        if custom_chunk_size is not None and not self.equal_chunks:
            original_max_chunk_size = self.max_chunk_size
            self.max_chunk_size = custom_chunk_size
            
        try:
            self._process_chunks()
        finally:
            if original_max_chunk_size is not None:
                self.max_chunk_size = original_max_chunk_size

    def process_directory(self, directory):
        self.process_directories([directory])

    def _split_tokens(self, content_bytes):
        return content_bytes.decode("utf-8", errors="replace").split()
        
    def _write_chunk(self, content_bytes, chunk_num):
        os.makedirs(self.output_dir, exist_ok=True)
        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
        
        try:
            tree_header = ""
            if chunk_num == 0 and self.current_walk_root:
                tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)   

            if type(content_bytes) == bytes:
                chunk_content = content_bytes.decode('utf-8', errors='replace')
            else:
                chunk_content = str(content_bytes)
            
            final_content = tree_header + chunk_content
            
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(final_content)
                
        except Exception:
            print(f"Error writing chunk {chunk_num}")
            try:
                with open(chunk_path, "wb") as f:
                    f.write(content_bytes)
            except:
                pass

    def pdf_chunking(self, path, idx):
        chunk_writer = ChunkWriterInterface(self)
        return self.pdf_processor.process_pdf_for_chunking(path, idx, chunk_writer)

    def _process_chunks(self):
        if not self.loaded_files:
            return
        if self.semantic_chunking:
            self._chunk_by_semantic()
        elif self.equal_chunks:
            self._chunk_by_equal_parts()
        else:
            self._chunk_by_size()
    
    def _extract_pdf_paragraphs(self, path):
        return self.pdf_processor.extract_pdf_paragraphs(path)

    def _chunk_by_equal_parts(self) -> None:
        text_blocks = []
        for path, content_bytes, _ in self.loaded_files:
            if path.endswith(".pdf"):
                paragraphs = self._extract_pdf_paragraphs(path)
                for para in paragraphs:
                    s = len(para.split())
                    if s > 0:
                        text_blocks.append((path, para, s))

            else:
                text = self._get_text_content(path, content_bytes)
                if text:
                    s = len(text.split())
                    text_blocks.append((path, text, s))

        if not text_blocks:
            return
        
        n_chunks = self.equal_chunks
        text_blocks.sort(key=lambda x: -x[2])  

        chunks = [[] for _ in range(n_chunks)]
        chunk_sizes = [0] * n_chunks

        for block in text_blocks:
            min_idx = 0
            min_size = chunk_sizes[0]
            for i in range(1, n_chunks):
                if chunk_sizes[i] < min_size:
                    min_size = chunk_sizes[i]
                    min_idx = i
            chunks[min_idx].append(block)
            chunk_sizes[min_idx] += block[2]

        for i, chunk in enumerate(chunks):
            if chunk:
                self._write_equal_chunk([(path, text) for path, text, _ in chunk], i)
    
    def _write_equal_chunk(self, chunk_data, chunk_num):
        tree_header = ""
        if chunk_num == 0 and self.current_walk_root:
            tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)
        
        txt = tree_header
        txt += "="*80 + "\n" + f"CHUNK {chunk_num + 1} OF {self.equal_chunks}\n" + "="*80 + "\n\n"

        for path, text in chunk_data:
            txt += "="*40 + "\n" + f"File: {path}\n" + "="*40 + "\n" + text + "\n"
        
        os.makedirs(self.output_dir, exist_ok=True)
        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
        with open(chunk_path, "w", encoding="utf-8") as f:
            f.write(txt)

    def _build_chunk_header(self, num, file_path):
        return [
            "="*80,
            f"CHUNK {num}",
            "="*80,
            "",
            "="*40,
            f"File: {file_path}",
            "="*40,
            ""
        ]

    def _write_file_chunk(self, path, lines, chunk_num):
        header = self._build_chunk_header(chunk_num, path)
        chunk_data = "\n".join(header + lines) + "\n"
        self._write_chunk(chunk_data.encode("utf-8"), chunk_num - 1)

    def _chunk_by_size(self):
        chunk_num = 1
        
        for path, content_bytes, _ in self.loaded_files:
            text = self._get_text_content(path, content_bytes)
            
            if not text:
                header = self._build_chunk_header(chunk_num, path)
                data = "\n".join(header + ["[Empty File]"]) + "\n"
                self._write_chunk(data.encode("utf-8"), chunk_num - 1)
                chunk_num += 1
                continue

            if path.endswith(".pdf"):
                next_idx = self.pdf_chunking(path, chunk_num - 1)
                chunk_num = next_idx + 1
                continue

            lines = text.splitlines()
            current_lines = []
            word_count = 0
            
            for line in lines:
                if not line.strip():
                    current_lines.append(line)
                    continue
                    
                words = len(line.split())
                
                if word_count + words > self.max_chunk_size and current_lines:
                    self._write_file_chunk(path, current_lines, chunk_num)
                    chunk_num += 1
                    current_lines = []
                    word_count = 0
                
                current_lines.append(line)
                word_count += words
            
            if current_lines:
                self._write_file_chunk(path, current_lines, chunk_num)
                chunk_num += 1

    def _chunk_by_semantic(self):
        chunk_index = 0
        for path, content_bytes in self.loaded_files:
            text = self._get_text_content(path, content_bytes)
            if not text and not path.endswith(".pdf"):
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

        lines = []
        current_size = 0
        idx = chunk_index

        for line in lines:
            line_size = len(line.split())
            if self.max_chunk_size and (current_size + line_size) > self.max_chunk_size and lines:
                chunk_data = self._format_chunk_content(path, lines, idx)
                self._write_chunk(chunk_data.encode("utf-8"), idx)
                idx += 1
                lines = []
                current_size = 0

            lines.append(line)
            current_size += line_size

        if lines:
            chunk_data = self._format_chunk_content(path, lines, idx)
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

    def __exit__(self):
        self.close()
        return False