#!/usr/bin/env python3
"""
Find the best available GPU slot on Jubail HPC for a given workload.

Usage:
    python gpu_find.py                         # any 1 GPU
    python gpu_find.py --gpus 2                # 2 GPUs on one node
    python gpu_find.py --vram 80               # 1 GPU with >=80GB VRAM
    python gpu_find.py --gpus 4 --vram 80      # 4x 80GB+ GPUs
    python gpu_find.py --suggest               # print sbatch flags for best match
"""

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Find best GPU slot on Jubail HPC")
    parser.add_argument("--gpus", "-g", type=int, default=1, help="Number of GPUs needed (default: 1)")
    parser.add_argument("--vram", "-v", type=int, default=0, help="Minimum VRAM in GB (default: any)")
    parser.add_argument("--suggest", "-s", action="store_true", help="Print sbatch flags for best match")
    parser.add_argument("--condo", action="store_true", help="Prefer a2s2 condo nodes")
    args = parser.parse_args()

    result = subprocess.run(
        ["python3", os.path.join(SCRIPT_DIR, "gpu_monitor.py"), "--json"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)
    candidates = []

    for name, node in data["nodes"].items():
        if node["gpu_free"] < args.gpus:
            continue
        if node["vram_gb"] < args.vram:
            continue

        score = 0
        if args.condo and node["is_a2s2"]:
            score += 1000
        score += node["vram_gb"] * 10
        if "h200" in node["gpu_type"]:
            score += 500
        elif "h100" in node["gpu_type"]:
            score += 400
        elif "80g" in node["gpu_type"] or node["vram_gb"] >= 80:
            score += 300
        score -= node["gpu_free"] - args.gpus

        candidates.append((score, name, node))

    candidates.sort(key=lambda x: -x[0])

    if not candidates:
        print(f"No nodes found with {args.gpus} free GPU(s) and >={args.vram}GB VRAM")
        sys.exit(1)

    print(f"{'RANK':<5} {'NODE':<8} {'GPU_TYPE':<10} {'VRAM':>5} {'FREE':>5} {'STATE':<10} {'TAGS'}")
    print("─" * 60)
    for i, (score, name, node) in enumerate(candidates[:10], 1):
        tags = []
        if node["is_a2s2"]:
            tags.append("a2s2")
        if node["is_condo_only"]:
            tags.append("condo")
        print(
            f"{i:<5} {name:<8} {node['gpu_type'].upper():<10} "
            f"{node['vram_gb']:>4}G {node['gpu_free']:>5} "
            f"{node['state']:<10} {','.join(tags)}"
        )

    if args.suggest:
        best_name = candidates[0][1]
        best = candidates[0][2]
        print()
        print("Suggested sbatch flags:")
        print("─" * 40)

        if best["is_a2s2"]:
            print(f"#SBATCH --partition=condo")
            print(f"#SBATCH -q a2s2")
        elif best["is_condo_only"]:
            print(f"#SBATCH --partition=condo")
        else:
            print(f"#SBATCH --partition=nvidia")

        print(f"#SBATCH --gres=gpu:{args.gpus}")

        if args.vram >= 80 and not best["is_a2s2"]:
            print(f"#SBATCH --constraint=80g")

        print(f"#SBATCH --nodelist={best_name}")
        print(f"#SBATCH --time=96:00:00")


if __name__ == "__main__":
    main()
