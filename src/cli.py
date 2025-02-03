# cli.py
import sys
import argparse

from src.core.multi_dirs_chunker import ParallelChunker

def main():
    parser = argparse.ArgumentParser(
        description="Chunk and optionally produce a single-file aggregator output for text-based files."
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=["."],
        help="One or more directories to scan. Defaults to current directory if none."
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="Ignore patterns (e.g., *.log, .git/**) to skip."
    )
    parser.add_argument(
        "--unignore",
        nargs="*",
        default=[],
        help="Unignore patterns to override ignore rules."
    )
    parser.add_argument(
        "--binary-extensions",
        nargs="*",
        default=["exe","dll","so"],
        help="File extensions treated as binary (skipped)."
    )
    parser.add_argument(
        "--priority-rule",
        action="append",
        default=[],
        help="Add a priority rule in the format 'pattern,score'. "
             "Can be repeated. Example: --priority-rule='.*\\.py,10' --priority-rule='.*\\.rs,20'"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=10*1024*1024,
        help="Max chunk size in bytes (if token_mode=False) or max tokens (if token_mode=True)."
    )
    parser.add_argument(
        "--token-mode",
        action="store_true",
        help="If set, interpret max-size as a token count rather than bytes."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for chunk-*.txt or whole-chunk-output.txt. If omitted and stream=False, uses current dir."
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="If set, write all output to stdout instead of creating files."
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=4,
        help="Number of worker threads for parallel file reading."
    )
    parser.add_argument(
        "--whole_chunk-mode",
        action="store_true",
        help="If set, produce a single-file aggregator output (whole_chunk_mode-output.txt) "
             "instead of multiple chunk-N.txt files."
    )

    args = parser.parse_args()

    priority_rules = []
    for rule_str in args.priority_rule:
        splitted = rule_str.split(",", 1)
        if len(splitted) != 2:
            print(f"[Error] Priority rule must be in 'pattern,score' format: '{rule_str}'", file=sys.stderr)
            sys.exit(1)

        pattern = splitted[0].strip()
        try:
            score = int(splitted[1].strip())
        except ValueError:
            print(f"[Error] Score must be an integer in rule: '{rule_str}'", file=sys.stderr)
            sys.exit(1)

        priority_rules.append((pattern, score))

    chunker = ParallelChunker(
        user_ignore=args.ignore,
        user_unignore=args.unignore,
        binary_extensions=args.binary_extensions,
        priority_rules=priority_rules,
        max_size=args.max_size,
        token_mode=args.token_mode,
        output_dir=args.output_dir,
        stream=args.stream,
        num_threads=args.num_threads,
        whole_chunk_mode=args.whole_chunk_mode
    )

    chunker.process_directories(args.dirs)

    chunker.close()


if __name__ == "__main__":
    main()
