class PriorityRule:
    def __init__(self, pattern, score):
        self.pattern = pattern
        self.score = score

class KomodoConfig:
    max_size = 10 * 1024 * 1024
    token_mode = False
    output_dir = None
    stream = False
    ignore_patterns = None
    priority_rules = None
    binary_extensions = None