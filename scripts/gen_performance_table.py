#!/usr/bin/env python3
"""
Generate a markdown table showing query performance for real and synthetic data.

This script runs CQ evaluations on both datasets, captures timing information,
collects hardware details, and outputs a formatted markdown table.
"""

from __future__ import annotations

import argparse
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None


def get_hardware_info() -> str:
    """Collect hardware information."""
    info_lines = []
    
    # CPU
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                model_match = re.search(r"model name\s*:\s*(.+)", cpuinfo)
                if model_match:
                    info_lines.append(f"CPU: {model_match.group(1).strip()}")
                cores = cpuinfo.count("processor\t:")
                if cores:
                    info_lines.append(f"CPU Cores: {cores}")
        except Exception:
            pass
        
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
                mem_match = re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo)
                if mem_match:
                    mem_gb = int(mem_match.group(1)) / (1024 * 1024)
                    info_lines.append(f"Memory: {mem_gb:.1f} GB")
        except Exception:
            pass
    elif platform.system() == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True
            )
            info_lines.append(f"CPU: {result.stdout.strip()}")
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.ncpu"],
                capture_output=True,
                text=True,
                check=True
            )
            info_lines.append(f"CPU Cores: {result.stdout.strip()}")
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                check=True
            )
            mem_gb = int(result.stdout.strip()) / (1024**3)
            info_lines.append(f"Memory: {mem_gb:.1f} GB")
        except Exception:
            pass
    
    # Use psutil if available for cross-platform info
    if psutil:
        try:
            if not info_lines:
                info_lines.append(f"CPU: {platform.processor() or 'Unknown'}")
            if not any("CPU Cores" in line for line in info_lines):
                info_lines.append(f"CPU Cores: {psutil.cpu_count(logical=True)}")
            if not any("Memory" in line for line in info_lines):
                mem_gb = psutil.virtual_memory().total / (1024**3)
                info_lines.append(f"Memory: {mem_gb:.1f} GB")
        except Exception:
            pass
    
    # OS
    info_lines.append(f"OS: {platform.system()} {platform.release()}")
    
    # Python version
    info_lines.append(f"Python: {platform.python_version()}")
    
    return " | ".join(info_lines)


def parse_timing_from_output(output: str) -> Dict[str, float]:
    """Parse timing information from mcbo-run-eval output.
    
    Returns dict mapping CQ name (e.g., 'cq1') to time in seconds.
    """
    timings = {}
    # Pattern: "  [1/8] cq1.rq... ✓ 161 rows (4.7s)"
    pattern = r"\[(\d+)/\d+\]\s+(\w+)\.rq\.\.\.\s+[✓⚠]\s+\d+\s+rows\s+\(([\d.]+)s\)"
    
    for match in re.finditer(pattern, output):
        cq_name = match.group(2).lower()
        time_sec = float(match.group(3))
        timings[cq_name] = time_sec
    
    return timings


def run_eval(data_dir: Path) -> Dict[str, float]:
    """Run evaluation on a dataset and return timing information."""
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist, skipping...", file=sys.stderr)
        return {}
    
    graph_file = data_dir / "graph.ttl"
    if not graph_file.exists():
        print(f"Graph file {graph_file} does not exist, skipping...", file=sys.stderr)
        return {}
    
    print(f"Running evaluation on {data_dir}...", file=sys.stderr)
    
    try:
        result = subprocess.run(
            ["mcbo-run-eval", "--data-dir", str(data_dir)],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent
        )
        output = result.stdout + result.stderr
        timings = parse_timing_from_output(output)
        return timings
    except subprocess.CalledProcessError as e:
        print(f"Error running evaluation on {data_dir}:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return {}
    except FileNotFoundError:
        print(f"Error: mcbo-run-eval not found. Make sure the package is installed.", file=sys.stderr)
        return {}


def format_time(seconds: Optional[float]) -> str:
    """Format time as 'X.XX s' or '—' if None."""
    if seconds is None:
        return "—"
    return f"{seconds:.2f} s"


def main():
    parser = argparse.ArgumentParser(
        description="Generate query performance table"
    )
    parser.add_argument(
        "--real-dir",
        type=Path,
        default=Path(".data"),
        help="Real data directory (default: .data)"
    )
    parser.add_argument(
        "--synthetic-dir",
        type=Path,
        default=Path("data.sample"),
        help="Synthetic data directory (default: data.sample)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file (default: stdout)"
    )
    args = parser.parse_args()
    
    # Run evaluations
    real_timings = run_eval(args.real_dir) if args.real_dir.exists() else {}
    synthetic_timings = run_eval(args.synthetic_dir) if args.synthetic_dir.exists() else {}
    
    # Get hardware info
    hardware_info = get_hardware_info()
    
    # Generate table
    cqs = [f"cq{i}" for i in range(1, 9)]
    
    lines = []
    lines.append("| Competency Question | Real Data (723 processes) | Synthetic Data (10 processes) |")
    lines.append("| ------------------- | ------------------------- | ----------------------------- |")
    
    for cq in cqs:
        cq_upper = cq.upper()
        real_time = real_timings.get(cq)
        synthetic_time = synthetic_timings.get(cq)
        lines.append(
            f"| {cq_upper}                 | {format_time(real_time):<24} | {format_time(synthetic_time):<28} |"
        )
    
    # Add hardware info
    lines.append("")
    lines.append("### Execution Environmnet:")
    lines.append("")
    lines.append(hardware_info)
    
    output_text = "\n".join(lines)
    
    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Performance table written to {args.output}", file=sys.stderr)
    else:
        print(output_text)


if __name__ == "__main__":
    main()

