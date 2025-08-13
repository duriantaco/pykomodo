import os
import fnmatch

class PriorityRule:
    def __init__(self, pattern, score):
        self.pattern = pattern
        self.score = score

class PyCConfig:
    def __init__(self):
        self.max_size = 0
        self.token_mode = False
        self.output_dir = None
        self.stream = False
        
        self.ignore_patterns = []
        self.unignore_patterns = [] 
        self.priority_rules = []
        self.binary_exts = []

    def add_ignore_pattern(self, pattern):
        self.ignore_patterns.append(pattern)

    def add_unignore_pattern(self, pattern):
        self.unignore_patterns.append(pattern)

    def add_priority_rule(self, pattern, score):
        self.priority_rules.append(PriorityRule(pattern, score))

    def should_ignore(self, path):
        for pat in self.unignore_patterns:
            if fnmatch.fnmatch(path, pat):
                return False

        for pat in self.ignore_patterns:
            if fnmatch.fnmatch(path, pat):
                return True

        return False

    def calculate_priority(self, path):
        highest = 0
        for rule in self.priority_rules:
            if fnmatch.fnmatch(path, rule.pattern):
                if rule.score > highest:
                    highest = rule.score
        return highest

    def is_binary_file(self, path):
        _, ext = os.path.splitext(path)
        ext = ext.lstrip(".").lower()
        is_binary = False
        for b in self.binary_exts:
            if ext == b.lower():
                is_binary = True
                break

        if is_binary:
            return True

        try:
            with open(path, "rb") as f:
                chunk = f.read(512)
        except OSError:
            return True

        if b"\0" in chunk:
            return True

        return False

    def read_file_contents(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            return data.decode("utf-8", errors="replace")
        except OSError:
            return "<NULL>"

    def count_tokens(self, text):
        return len(text.split())

    def make_c_string(self, text):
        if text is None:
            return "<NULL>"
        return text

    def __repr__(self):
        return (f"PyCConfig(max_size={self.max_size}, token_mode={self.token_mode}, "
                f"output_dir={self.output_dir!r}, stream={self.stream}, "
                f"ignore_patterns={self.ignore_patterns}, "
                f"unignore_patterns={self.unignore_patterns}, "
                f"priority_rules={[ (r.pattern, r.score) for r in self.priority_rules ]}, "
                f"binary_exts={self.binary_exts})")
