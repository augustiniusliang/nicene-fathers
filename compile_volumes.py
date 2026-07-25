from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile all TeX files under volumes/ with xelatex using 5 threads."
    )
    parser.add_argument("--jobs", type=int, default=5, help="Number of parallel worker threads.")
    parser.add_argument("--passes", type=int, default=2, help="Number of xelatex passes per file.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Repository root. Defaults to the directory containing this script.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to the combined log file. Defaults to a timestamped file in the repo root.",
    )
    return parser.parse_args()


class TeeLogger:
    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._log_path.open("w", encoding="utf-8", buffering=1)
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._log_path

    def write(self, message: str) -> None:
        if not message.endswith("\n"):
            message += "\n"
        with self._lock:
            sys.stdout.write(message)
            sys.stdout.flush()
            self._handle.write(message)
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            self._handle.close()


def discover_tex_files(root: Path) -> list[Path]:
    volumes_dir = root / "volumes"
    if not volumes_dir.is_dir():
        raise FileNotFoundError(f"Missing volumes directory: {volumes_dir}")
    return sorted(volumes_dir.glob("**/*.tex"))


def run_xelatex(tex_path: Path, passes: int, logger: TeeLogger) -> tuple[bool, str]:
    work_dir = tex_path.parent
    tex_name = tex_path.name
    display_name = tex_path.relative_to(work_dir.parent)

    for current_pass in range(1, passes + 1):
        command = [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            tex_name,
        ]
        logger.write(f"[{display_name}] pass {current_pass}/{passes} start")

        try:
            process = subprocess.Popen(
                command,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError:
            return False, "xelatex was not found on PATH"

        assert process.stdout is not None
        for line in process.stdout:
            logger.write(f"[{display_name}] {line.rstrip()}")

        return_code = process.wait()
        logger.write(f"[{display_name}] pass {current_pass}/{passes} end (exit {return_code})")
        if return_code != 0:
            return False, f"xelatex failed on pass {current_pass} with exit code {return_code}"

    return True, ""


def main() -> int:
    args = parse_args()
    root = args.root.resolve()

    xelatex_path = shutil.which("xelatex")
    if xelatex_path is None:
        print("xelatex was not found on PATH.", file=sys.stderr)
        return 1

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log_file or (root / f"xelatex_volumes_{timestamp}.log")
    logger = TeeLogger(log_path)

    try:
        tex_files = discover_tex_files(root)
        if not tex_files:
            logger.write(f"No .tex files found under {root / 'volumes'}")
            return 0

        logger.write(f"Found {len(tex_files)} TeX files under {root / 'volumes'}")
        logger.write(f"Using xelatex at: {xelatex_path}")
        logger.write(f"Writing combined log to: {log_path}")
        logger.write(f"Using {args.jobs} worker threads and {args.passes} passes per file")

        failures: list[tuple[Path, str]] = []
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_map = {executor.submit(run_xelatex, tex_path, args.passes, logger): tex_path for tex_path in tex_files}
            for future in as_completed(future_map):
                tex_path = future_map[future]
                success, message = future.result()
                if success:
                    logger.write(f"[{tex_path.relative_to(root)}] finished successfully")
                else:
                    failures.append((tex_path, message))
                    logger.write(f"[{tex_path.relative_to(root)}] failed: {message}")

        logger.write(f"Completed: {len(tex_files) - len(failures)} succeeded, {len(failures)} failed")
        if failures:
            logger.write("Failed files:")
            for tex_path, message in failures:
                logger.write(f"  {tex_path.relative_to(root)}: {message}")
            return 1

        return 0
    finally:
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())