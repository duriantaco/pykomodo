import os
import fnmatch
import re
import concurrent.futures
from typing import Optional, List, Tuple
import fitz

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

class ParallelChunker:
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
        if not any("site-packages" in pattern or "venv" in pattern for pattern in user_unignore or []):
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
    
    def _get_text_content(self, path, content_bytes):
        if path.endswith(".pdf"):
            try:
                doc = fitz.open(path)
                text = ""
                for page in doc:
                    text += page.get_text("text")
                return text
            except Exception as e:
                print(f"Error extracting text from PDF {path}: {e}")
                return ""
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
    
    def _read_ignore_file(self, directory):
        """Read .pykomodo-ignore file in the given directory and add patterns to ignore_patterns."""
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
                except Exception as e:
                    print(f"Error reading {filename} file: {e}")

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
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if self.file_type:
                        _, ext = os.path.splitext(full_path)
                        if ext.lower() != f".{self.file_type}":
                            continue
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

    def process_directories(self, dirs: List[str]) -> None:
        for directory in dirs:
            self._read_ignore_file(directory)
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

    def process_file(self, file_path: str, custom_chunk_size: Optional[int] = None, force_process: bool = False) -> None:
        """
        Process a single file and create chunks from it.
        
        Args:
            file_path: Path to the file to process
            custom_chunk_size: Optional custom chunk size for this specific file, overriding the global setting
            force_process: If True, process the file even if it would normally be ignored
        """
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

    def _improved_pdf_chunking(self, path, idx):
        """
        Process a PDF file with improved text formatting for academic papers.
        Uses multiple extraction methods to get the best text representation.
        
        Args:
            path: Path to the PDF file
            idx: Starting chunk index
            
        Returns:
            Updated chunk index
        """
        try:
            doc = fitz.open(path)
            
            all_pages_content = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                text_as_text = page.get_text("text")  
                text_as_html = page.get_text("html")  
                text_as_dict = page.get_text("dict") 

                if "<p>" in text_as_html:
                    import re
                    paragraphs = re.findall(r'<p>(.*?)</p>', text_as_html, re.DOTALL)
                    processed_text = []
                    
                    for p in paragraphs:
                        clean_p = re.sub(r'<.*?>', ' ', p)
                        clean_p = re.sub(r'&[a-zA-Z]+;', ' ', clean_p)
                        clean_p = re.sub(r'\s+', ' ', clean_p).strip()
                        if clean_p:
                            processed_text.append(clean_p)
                    
                    page_text = "\n\n".join(processed_text)
                
                elif len(text_as_dict.get("blocks", [])) > 0:
                    blocks = sorted(text_as_dict["blocks"], key=lambda b: b["bbox"][1])
                    processed_text = []
                    
                    for block in blocks:
                        if "lines" not in block:
                            continue
                        
                        block_lines = []
                        for line in block["lines"]:
                            if "spans" not in line:
                                continue
                            
                            line_text = " ".join(span["text"] for span in line["spans"] if "text" in span)
                            if line_text.strip():
                                block_lines.append(line_text)
                        
                        if block_lines:
                            processed_text.append(" ".join(block_lines))
                    
                    page_text = "\n\n".join(processed_text)
                
                else:
                    lines = text_as_text.split('\n')
                    paragraphs = []
                    current_paragraph = []
                    
                    for line in lines:
                        line = line.strip()
                        words = line.split()
                        if len(words) <= 2 and not line.endswith('.') and not line.endswith(':'):
                            current_paragraph.append(line)
                        else:
                            if current_paragraph:
                                paragraphs.append(" ".join(current_paragraph))
                                current_paragraph = []
                            if line:
                                paragraphs.append(line)
                    
                    if current_paragraph:
                        paragraphs.append(" ".join(current_paragraph))
                    
                    page_text = "\n\n".join(paragraphs)
                
                page_content = f"--- Page {page_num + 1} ---\n\n{page_text}"
                all_pages_content.append(page_content)
            
            full_document = "\n\n".join(all_pages_content)
            
            paragraphs = full_document.split("\n\n")
            current_chunk = []
            current_size = 0
            
            for paragraph in paragraphs:
                if not paragraph.strip():
                    continue
                    
                para_size = len(paragraph.split())
                
                if current_size + para_size > self.max_chunk_size and current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_text}"
                    self._write_chunk(final_text.encode("utf-8"), idx)
                    idx += 1
                    current_chunk = []
                    current_size = 0
                
                current_chunk.append(paragraph)
                current_size += para_size
            
            if current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_text}"
                self._write_chunk(final_text.encode("utf-8"), idx)
                idx += 1
            
            return idx
        
        except Exception as e:
            print(f"Error processing PDF {path}: {e}")
            t = (
                "="*80 + "\n"
                + f"CHUNK {idx + 1}\n"
                + "="*80 + "\n\n"
                + "="*40 + "\n"
                + f"File: {path}\n"
                + "="*40 + "\n"
                + f"[Error processing PDF: {str(e)}]\n"
            )
            self._write_chunk(t.encode("utf-8"), idx)
            return idx + 1

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
        try:
            doc = fitz.open(path)
            paragraphs = []
            for page in doc:
                text = page.get_text("text")
                page_paras = text.split("\n\n")
                paragraphs.extend([para.strip() for para in page_paras if para.strip()])
            return paragraphs
        except Exception as e:
            print(f"Error extracting paragraphs from PDF {path}: {e}")
            return []

    def _chunk_by_equal_parts(self) -> None:
        text_blocks = []
        for (path, content_bytes, _) in self.loaded_files:
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
        chunk_contents = [[] for _ in range(n_chunks)]
        chunk_sizes = [0] * n_chunks
        for block in text_blocks:
            min_idx = 0
            min_size = chunk_sizes[0]
            for i in range(1, n_chunks):
                if chunk_sizes[i] < min_size:
                    min_size = chunk_sizes[i]
                    min_idx = i
            chunk_contents[min_idx].append(block)
            chunk_sizes[min_idx] += block[2]
        for i, chunk in enumerate(chunk_contents):
            if chunk:
                self._write_equal_chunk([(path, text) for path, text, _ in chunk], i)
    
    def _write_equal_chunk(self, chunk_data, chunk_num):
        txt = "="*80 + "\n" + f"CHUNK {chunk_num + 1} OF {self.equal_chunks}\n" + "="*80 + "\n\n"
        for path, text in chunk_data:
            txt += "="*40 + "\n" + f"File: {path}\n" + "="*40 + "\n" + text + "\n"
        self._write_chunk(txt.encode("utf-8"), chunk_num)

    def _chunk_by_size(self):
        idx = 0
        for (path, content_bytes, _) in self.loaded_files:
            text = self._get_text_content(path, content_bytes)
            if not text:
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

            if path.endswith(".pdf"):
                idx = self._improved_pdf_chunking(path, idx)
            else:
                lines = text.splitlines()
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
                    if line.strip():
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

    def _chunk_by_semantic(self):
        chunk_index = 0
        for (path, content_bytes, priority) in self.loaded_files:
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False