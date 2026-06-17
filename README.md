<p align="center">
  <img src="assets/banner.png" alt="job-arrays banner" width="100%">
</p>

# job-arrays

SLURM job array patterns, HPC best practices, and example scripts for Jubail HPC.

## Guides

| Document | Description |
|----------|-------------|
| [JUBAIL_BEST_PRACTICES.md](JUBAIL_BEST_PRACTICES.md) | Comprehensive Jubail HPC guide — environment setup, SLURM templates, debugging |
| [JUBAIL_QUICK_REFERENCE.md](JUBAIL_QUICK_REFERENCE.md) | One-page cheat sheet for common commands |
| [SLURM_RESUBMISSION_GUIDE.md](SLURM_RESUBMISSION_GUIDE.md) | Walltime-aware auto-resubmission, retry manifests, per-worker isolation |
| [CC-bestPract-HPC-ML.md](CC-bestPract-HPC-ML.md) | ML/AI-specific HPC patterns — checkpointing, array indexing, modulo arithmetic |

## Examples

| Directory | Contents |
|-----------|----------|
| [examples/assembly/](examples/assembly/) | Genome assembly (hifiasm, QUAST, BAM conversion) |
| [examples/alignment/](examples/alignment/) | Read mapping & SAM processing (bowtie2, StringTie) |
| [examples/annotation/](examples/annotation/) | Protein annotation, contamination filtering (DIAMOND, InterProScan, TransDecoder) |
| [examples/data-prep/](examples/data-prep/) | FASTA processing, file list generation, sequence retrieval |
| [examples/ml-inference/](examples/ml-inference/) | GPU inference arrays (ESM, multi-checkpoint combinatorial runs) |
| [examples/ml-training/](examples/ml-training/) | Model training (Mamba/LoRA) and checkpoint management |

## Utilities

| Script | Description |
|--------|-------------|
| [utilities/gpu_monitor.py](utilities/gpu_monitor.py) | GPU cluster dashboard — node capacity, allocation, jobs, with color-coded bars |
| [utilities/gpu_find.py](utilities/gpu_find.py) | Find the best available GPU slot for a workload (by count, VRAM, condo preference) |
| [utilities/get-job-info.sh](utilities/get-job-info.sh) | Extract job metadata and sbatch contents from a SLURM job ID |
| [utilities/getNode.sh](utilities/getNode.sh) | Look up which compute nodes ran a job |
