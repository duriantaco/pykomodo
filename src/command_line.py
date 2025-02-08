import sys
import argparse
import os
from src.multi_dirs_chunker import ParallelChunker

def main():
    parser = argparse.ArgumentParser(description="Chunk and produce aggregator output for text-based files.")
    parser.add_argument("dirs", nargs="*", default=["."])
    parser.add_argument("--ignore", nargs="*", default=[])
    parser.add_argument("--unignore", nargs="*", default=[])
    parser.add_argument("--binary-extensions", nargs="*", default=["exe", "dll", "so"])
    parser.add_argument("--priority-rule", action="append", default=[])
    parser.add_argument("--max-size", type=int, default=10*1024*1024)
    parser.add_argument("--token-mode", action="store_true")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--whole-chunk-mode", action="store_true", dest="whole_chunk_mode")
    parser.add_argument("--max-tokens-per-chunk", type=int, default=None)
    parser.add_argument("--num-token-chunks", type=int, default=None)
    args = parser.parse_args()

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    prules = []
    for r in args.priority_rule:
        s = r.split(",", 1)
        if len(s) != 2:
            print(f"[Error] Priority rule must be 'pattern,score': {r}", file=sys.stderr)
            sys.exit(1)
        pat, scr = s
        try:
            score = int(scr.strip())
        except ValueError:
            print(f"[Error] Score must be int: {r}", file=sys.stderr)
            sys.exit(1)
        prules.append((pat.strip(), score))

    chunker = ParallelChunker(
        user_ignore=args.ignore,
        user_unignore=args.unignore,
        binary_extensions=args.binary_extensions,
        priority_rules=prules,
        max_size=args.max_size,
        token_mode=args.token_mode,
        output_dir=args.output_dir,
        stream=args.stream,
        num_threads=args.num_threads,
        whole_chunk_mode=args.whole_chunk_mode,
        max_tokens_per_chunk=args.max_tokens_per_chunk,
        num_token_chunks=args.num_token_chunks
    )
    chunker.process_directories(args.dirs)
    chunker.close()

if __name__ == "__main__":
    main()
