# hpc-slurm

SLURM guides, GPU monitoring tools, job array patterns, and example scripts for HPC clusters.

## Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `utilities/gpu_monitor.py` | GPU cluster dashboard | `python3 utilities/gpu_monitor.py [--free] [--type X] [--compact] [--condo] [--json]` |
| `utilities/gpu_find.py` | Find best GPU slot for a workload | `python3 utilities/gpu_find.py [--gpus N] [--vram GB] [--suggest] [--condo]` |

## Notes

- GPU tools run locally and query the cluster via SSH (`drn2@jubail.abudhabi.nyu.edu`)
- SSH must be configured with key-based auth (BatchMode=yes)
- The `--json` flag on gpu_monitor.py is used by gpu_find.py — keep them in sync
