# JUBAIL HPC - BEST PRACTICES GUIDE

**NYU Abu Dhabi High Performance Computing**
**User:** drn2
**Last Updated:** 2026-01-20

---

## 🚨 CRITICAL CONCEPTS - READ FIRST

### 1. HOME Directory is TINY - Use /scratch

**THE MOST IMPORTANT RULE:**

```
❌ NEVER USE: /home/drn2/
✅ ALWAYS USE: /scratch/drn2/newhome/
```

**Why:** `/home/drn2` has only ~10GB quota. All software, conda environments, and project data MUST live in `/scratch/drn2/`.

### 2. Interactive Aliases (Login Node)

After logging in, ALWAYS run these aliases before working:

```bash
ho      # Sets HOME=/scratch/drn2/newhome
mamba   # Loads modules (gcc/cuda) and activates ML/AI conda environment
```

**These are defined in `~/.bashrc` and are REQUIRED for interactive work.**

### 3. All Projects Live in /scratch

```
/scratch/drn2/
├── newhome/              # HOME directory replacement
├── software/             # Conda environments
├── tmp/                  # Temporary files
└── PROJECTS/             # All project directories
    ├── algaGPT-TARA-archive/
    ├── TARA-LA4SR/
    └── YOUR-PROJECT-HERE/
```

---

## 📁 File System Structure

### Complete Directory Layout

```
/scratch/drn2/
│
├── newhome/                           # YOUR HOME (NOT /home/drn2!)
│   ├── miniconda3/                    # Miniconda installation
│   │   └── etc/profile.d/conda.sh    # Source this for conda
│   ├── .bashrc                        # Shell configuration
│   ├── .local/                        # Python user packages (pip --user)
│   └── .ssh/                          # SSH keys
│
├── software/
│   ├── conda-mamba_1/                 # ML/AI conda environment (main)
│   └── other_envs/                    # Other conda environments
│
├── tmp/                               # Temp files (set TMPDIR here)
│
└── PROJECTS/                          # All research projects
    ├── PROJECT_NAME/
    │   ├── data/
    │   ├── scripts/
    │   ├── results/
    │   └── logs/
    └── ...
```

### Local vs HPC Path Mapping

**For ANY project, maintain parallel structures:**

| Local Machine | HPC (Jubail) |
|--------------|--------------|
| `/media/drn2/External/PROJECT_NAME/` | `/scratch/drn2/PROJECTS/PROJECT_NAME/` |
| Development, testing, analysis | Heavy computation, batch jobs |

---

## 🐍 Python Environment Detection Pattern

**EVERY Python script that may run on HPC must detect environment at startup:**

### Template for Environment Detection

```python
#!/usr/bin/env python3
import os
import socket
from pathlib import Path

def get_base_dir():
    """Detect environment and return appropriate base directory"""
    hostname = socket.gethostname()

    # Check if running on HPC
    if 'cn' in hostname or 'dn' in hostname or 'gpu' in hostname or 'jubail' in hostname:
        # Running on Jubail HPC compute/GPU nodes (cn* = compute, dn* = data)
        return Path("/scratch/drn2/PROJECTS/YOUR_PROJECT_NAME")
    else:
        # Running locally
        return Path("/media/drn2/External/YOUR_PROJECT_NAME")

# Use this at the start of every script
BASE_DIR = get_base_dir()
data_path = BASE_DIR / "data" / "input.tsv"
results_path = BASE_DIR / "results" / "output.tsv"
```

### Alternative: String-based Pattern

```python
import socket

hostname = socket.gethostname()
if 'cn' in hostname or 'gpu' in hostname or 'jubail' in hostname:
    BASE_DIR = "/scratch/drn2/PROJECTS/YOUR_PROJECT"
else:
    BASE_DIR = "/media/drn2/External/YOUR_PROJECT"

# Use BASE_DIR for all file paths
input_file = f"{BASE_DIR}/data/input.tsv"
output_file = f"{BASE_DIR}/results/output.tsv"
```

---

## 🖥️ SLURM Batch Script Template

### Standard Template for Any Project

```bash
#!/bin/bash
#SBATCH --job-name=project_task
#SBATCH --partition=compute          # or 'nvidia' for GPU
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=28
#SBATCH --mem=90G
#SBATCH --time=48:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

# ============================================
# CRITICAL ENVIRONMENT SETUP
# ============================================

# 1. Set HOME to newhome (NEVER use /home/drn2!)
export HOME=/scratch/drn2/newhome

# 2. Set temporary directory
export TMPDIR=/scratch/drn2/tmp
mkdir -p $TMPDIR

# 3. Set Python user base
export PYTHONUSERBASE=/scratch/drn2/newhome/.local

# 4. Clear problematic environment variables
unset NETWORKX_BACKEND_CONFIG
unset NX_BACKEND_CONFIG

# 5. Load required modules
module load gcc/13.2.0
# module load cuda/12.2.0  # Uncomment for GPU jobs

# 6. Activate conda environment
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
conda activate /scratch/drn2/software/conda-mamba_1

# ============================================
# JOB INFORMATION
# ============================================
echo "============================================"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Started: $(date)"
echo "============================================"
echo ""

# ============================================
# CHANGE TO PROJECT DIRECTORY
# ============================================
cd /scratch/drn2/PROJECTS/YOUR_PROJECT || exit 1

# ============================================
# RUN YOUR SCRIPT
# ============================================
python scripts/your_script.py

# ============================================
# JOB COMPLETION
# ============================================
echo ""
echo "============================================"
echo "Completed: $(date)"
echo "============================================"
```

### GPU-Specific Template

```bash
#!/bin/bash
#SBATCH --job-name=gpu_task
#SBATCH --partition=nvidia           # GPU partition
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=28
#SBATCH --gres=gpu:4                 # Request 4 GPUs
#SBATCH --mem=90G
#SBATCH --time=48:00:00
#SBATCH --output=logs/slurm_gpu_%j.out
#SBATCH --error=logs/slurm_gpu_%j.err

# Environment setup (same as above)
export HOME=/scratch/drn2/newhome
export TMPDIR=/scratch/drn2/tmp
export PYTHONUSERBASE=/scratch/drn2/newhome/.local
mkdir -p $TMPDIR

unset NETWORKX_BACKEND_CONFIG
unset NX_BACKEND_CONFIG

# Load modules (include CUDA for GPU)
module load gcc/13.2.0 cuda/12.2.0

source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
conda activate /scratch/drn2/software/conda-mamba_1

# GPU info
echo "GPUs allocated:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

cd /scratch/drn2/PROJECTS/YOUR_PROJECT || exit 1
python scripts/gpu_script.py
```

### Array Job Template

```bash
#!/bin/bash
#SBATCH --job-name=array_job
#SBATCH --partition=compute
#SBATCH --array=1-10                 # Run tasks 1 through 10
#SBATCH --cpus-per-task=28
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

# Environment setup
export HOME=/scratch/drn2/newhome
export TMPDIR=/scratch/drn2/tmp
export PYTHONUSERBASE=/scratch/drn2/newhome/.local
mkdir -p $TMPDIR

unset NETWORKX_BACKEND_CONFIG
unset NX_BACKEND_CONFIG

module load gcc/13.2.0
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
conda activate /scratch/drn2/software/conda-mamba_1

echo "============================================"
echo "Job ID: $SLURM_ARRAY_JOB_ID"
echo "Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Node: $(hostname)"
echo "Started: $(date)"
echo "============================================"

cd /scratch/drn2/PROJECTS/YOUR_PROJECT || exit 1

# Use SLURM_ARRAY_TASK_ID to select which task to run
python scripts/process_task.py --task-id $SLURM_ARRAY_TASK_ID
```

---

## 🎯 Partition Selection Guide

### Available Partitions

| Partition | Use Case | Max Time | Resources | Notes |
|-----------|----------|----------|-----------|-------|
| **nvidia** | GPU-intensive tasks | 48 hours | V100, A100, H100 GPUs | For deep learning, GPU acceleration |
| **compute** | CPU parallel jobs | 48 hours | Multi-core CPUs (28+ cores) | For parallel CPU tasks |
| **dalma** | General purpose | 48 hours | Standard CPUs | Legacy, use 'compute' instead |

### Resource Guidelines

**CPU Jobs:**
- `--cpus-per-task=28` (full node)
- `--mem=90G` (safe default)
- `--mem=180G` (for memory-intensive tasks)

**GPU Jobs:**
- `--gres=gpu:1` (single GPU)
- `--gres=gpu:4` (4 GPUs for distributed training)
- `--cpus-per-task=28` (full CPU access)
- `--mem=90G` (GPU jobs often need lots of RAM)

**Array Jobs:**
- Use for processing multiple files/parameters
- `--array=1-100` (100 tasks)
- `--array=1-100%10` (max 10 running simultaneously)

---

## 🔧 Module System

### Available Modules

```bash
# List all available modules
module avail

# List loaded modules
module list

# Load a module
module load gcc/13.2.0
module load cuda/12.2.0

# Unload a module
module unload cuda/12.2.0
```

### Standard Modules for ML/AI Work

```bash
module load gcc/13.2.0      # GNU compiler (required for many packages)
module load cuda/12.2.0     # CUDA (required for GPU work)
```

---

## 🐍 Conda Environment Management

### Using Existing Environment

```bash
# Source conda
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh

# Activate main ML environment
conda activate /scratch/drn2/software/conda-mamba_1

# Check what's installed
conda list
pip list
```

### Creating New Environment for a Project

```bash
# Create new environment
conda create -p /scratch/drn2/software/my_new_env python=3.11

# Activate it
conda activate /scratch/drn2/software/my_new_env

# Install packages
conda install numpy pandas scipy matplotlib
pip install specific-package
```

### Installing Packages

```bash
# Activate environment first
conda activate /scratch/drn2/software/conda-mamba_1

# Install with conda (preferred)
conda install xgboost scikit-learn

# Install with pip (if not in conda)
pip install shap

# Check for conflicts
pip check
```

### Known Package Issues (From Experience)

**NumPy Version Conflicts:**
- Some packages (like numba/shap) require NumPy 2.0 or less
- If you get "Numba needs NumPy 2.0 or less", downgrade:
  ```bash
  pip install "numpy<2.1"
  ```

**NetworkX Configuration Bug:**
- NetworkX 3.6.1 has `nx-loopback` syntax error
- **Workaround:** Unset env vars in SLURM scripts (already in template)
- **Alternative:** Use older NetworkX version:
  ```bash
  pip install "networkx<3.6"
  ```

---

## 📊 Job Management

### Submitting Jobs

```bash
# Submit single job
sbatch script.sbatch

# Submit array job
sbatch --array=1-10 script.sbatch

# Submit with specific array tasks
sbatch --array=1,3,5,7,9 script.sbatch

# Submit dependent job (waits for job 12345 to complete)
sbatch --dependency=afterok:12345 script.sbatch

# Submit dependent job (runs if previous fails)
sbatch --dependency=afterany:12345 script.sbatch
```

### Monitoring Jobs

```bash
# Check your jobs
squeue -u drn2

# Check specific job
squeue -j 12345

# Detailed format
squeue -u drn2 --format="%.10i %.12P %.20j %.8u %.2t %.10M %.6D %R"

# Check partition status
sinfo -p nvidia
sinfo -p compute

# Job accounting (after completion)
sacct -j 12345
sacct -j 12345 --format=JobID,State,ExitCode,Elapsed,MaxRSS,MaxVMSize
```

### Managing Jobs

```bash
# Cancel specific job
scancel 12345

# Cancel array job task
scancel 12345_5

# Cancel all your jobs
scancel -u drn2

# Cancel all pending jobs
scancel -u drn2 --state=PENDING

# Hold a job (prevent it from running)
scontrol hold 12345

# Release a held job
scontrol release 12345
```

---

## 📝 Log Files and Debugging

### Log File Naming

**Single jobs:**
- `--output=logs/slurm_%j.out` → `slurm_12345.out`
- `--error=logs/slurm_%j.err` → `slurm_12345.err`

**Array jobs:**
- `--output=logs/slurm_%A_%a.out` → `slurm_12345_3.out`
  - `%A` = array job ID
  - `%a` = array task ID

### Checking Logs

```bash
# Watch live output
tail -f logs/slurm_12345.out

# Check last 50 lines
tail -50 logs/slurm_12345.err

# Search for errors
grep -i "error\|exception\|failed" logs/slurm_*.err

# Check all recent error logs
ls -lhtr logs/*.err | tail -10
```

### Common Error Messages

**"No such file or directory: /home/drn2/..."**
→ Fix: Check SLURM script sets `export HOME=/scratch/drn2/newhome`

**"FileNotFoundError" for input files**
→ Fix: Python script needs environment detection (see template above)

**"ModuleNotFoundError: No module named 'xgboost'"**
→ Fix: Install package in conda environment

**"conda: command not found"**
→ Fix: SLURM script must source conda.sh before activating

**Job state "DependencyNeverSatisfied"**
→ Fix: Dependent job failed, check logs of previous job

---

## 🔄 Data Transfer Between Local and HPC

### Rsync (Recommended)

```bash
# Local to HPC
rsync -Pvrt /media/drn2/External/PROJECT/ drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/PROJECT/

# HPC to Local
rsync -Pvrt drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/PROJECT/ /media/drn2/External/PROJECT/

# Specific directories
rsync -Pvrt --include='*/' --include='*.tsv' --exclude='*' drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/PROJECT/results/ results/
```

**Options explained:**
- `-P` = show progress and allow resume
- `-v` = verbose
- `-r` = recursive
- `-t` = preserve timestamps

### SCP (For Small Files)

```bash
# Local to HPC
scp file.txt drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/PROJECT/

# HPC to Local
scp drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/PROJECT/results.tsv .
```

---

## 🧪 Interactive Testing Workflow

### Best Practice Testing Sequence

**1. Test locally first:**
```bash
# On local machine
cd /media/drn2/External/PROJECT/
python scripts/analysis.py
```

**2. Test on HPC interactively:**
```bash
# SSH to HPC
ssh drn2@jubail.abudhabi.nyu.edu

# Run aliases
ho
mamba

# Request interactive session
srun --pty --partition=compute --cpus-per-task=4 --mem=16G --time=1:00:00 bash

# Load environment manually
export HOME=/scratch/drn2/newhome
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
conda activate /scratch/drn2/software/conda-mamba_1

# Navigate and test
cd /scratch/drn2/PROJECTS/PROJECT/
python scripts/analysis.py

# Exit interactive session
exit
```

**3. Submit batch job:**
```bash
# From login node
cd /scratch/drn2/PROJECTS/PROJECT/
sbatch scripts/run_analysis.sbatch
```

**4. Monitor first job carefully:**
```bash
# Watch for immediate errors
squeue -u drn2
tail -f logs/slurm_*.out
```

---

## ✅ Pre-Submission Checklist

Before submitting ANY job, verify:

### Script Checks
- [ ] Python script has environment detection (hostname check)
- [ ] All file paths use BASE_DIR variable
- [ ] Script tested locally
- [ ] Script tested interactively on HPC

### SLURM Script Checks
- [ ] `export HOME=/scratch/drn2/newhome` present
- [ ] `export TMPDIR=/scratch/drn2/tmp` present
- [ ] `unset NETWORKX_BACKEND_CONFIG` present (if using networkx)
- [ ] Conda sourced from `/scratch/drn2/newhome/miniconda3/...`
- [ ] Correct partition selected (nvidia for GPU, compute for CPU)
- [ ] Appropriate resources requested (CPUs, memory, time)
- [ ] Log directories exist: `mkdir -p logs`

### Data Checks
- [ ] Input files exist on HPC (rsync completed)
- [ ] Output directories created: `mkdir -p results figures`
- [ ] Sufficient scratch space available

---

## 🚨 Common Mistakes - Learn From Our Pain

### ❌ MISTAKE 1: Using /home paths

**Wrong:**
```bash
source /home/drn2/miniconda3/etc/profile.d/conda.sh
export PYTHONUSERBASE=/home/drn2/.local
```

**Correct:**
```bash
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
export PYTHONUSERBASE=/scratch/drn2/newhome/.local
```

### ❌ MISTAKE 2: Hardcoded local paths in Python

**Wrong:**
```python
data_file = "/media/drn2/External/PROJECT/data/input.tsv"
```

**Correct:**
```python
import socket
hostname = socket.gethostname()
if 'cn' in hostname or 'dn' in hostname or 'gpu' in hostname:
    data_file = "/scratch/drn2/PROJECTS/PROJECT/data/input.tsv"
else:
    data_file = "/media/drn2/External/PROJECT/data/input.tsv"
```

### ❌ MISTAKE 3: Wrong partition name

**Wrong:**
```bash
#SBATCH --partition=gpu
```

**Correct:**
```bash
#SBATCH --partition=nvidia
```

### ❌ MISTAKE 4: Not creating log directories

**Result:** Job fails immediately with "cannot open file logs/slurm_12345.out"

**Fix:**
```bash
# Before submitting
mkdir -p logs results figures
```

### ❌ MISTAKE 5: Assuming conda is in PATH

**Wrong:**
```bash
conda activate myenv
```

**Correct:**
```bash
source /scratch/drn2/newhome/miniconda3/etc/profile.d/conda.sh
conda activate /scratch/drn2/software/conda-mamba_1
```

---

### ❌ MISTAKE 6: Letting your app pick the GPU by index (false "low GPU usage" kills)

Jubail's monitor will **kill a GPU job it believes used the GPU < ~2 hours**
(email subject: *"Low GPU usage for job ... in last 2 hours"*). A genuinely
busy job can still get killed because of a **GPU index-scheme mismatch**:

- SLURM allocates a GPU by its **global** index and the usage monitor keys on
  that index (it reports e.g. `GPUIdx: 1 AveUtil: 0.00`).
- But **inside the job's cgroup**, that same card is remapped to **logical
  index 0** — `nvidia-smi` shows only `index 0`, and `CUDA_VISIBLE_DEVICES=0`.

If your app trusts "device 0" / a bare index, the two numbering schemes can
disagree and the monitor reads 0% on a card that is actually pegged at 100%.
(Real case: ALGAE_SENATE ollama job `16337473_0` ran an H100 flat-out for 13h
and was still killed for `AveUtil: 0.00`.)

**Diagnose** — inside the job, these disagree when the bug is present:
```bash
echo "SLURM_JOB_GPUS=$SLURM_JOB_GPUS"          # global index the monitor watches
nvidia-smi --query-gpu=index,uuid --format=csv # cgroup-local index (usually 0)
```

**Fix — pin to the allocated GPU by UUID (unambiguous under any scheme):**
```bash
# Place AFTER `module load cuda/...`, BEFORE launching your GPU process.
GPU_UUID=$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -1 | tr -d ' ')
if [[ -n "$GPU_UUID" ]]; then
    export CUDA_VISIBLE_DEVICES="$GPU_UUID"
    echo "[job] pinned to GPU UUID=$GPU_UUID (SLURM_JOB_GPUS=${SLURM_JOB_GPUS:-unset})"
fi
```

**Also recommended — a utilization heartbeat** so you have proof-of-busy if the
monitor disagrees again (and early warning if a GPU is *genuinely* idle):
```bash
( while true; do
    echo "$(date -u +%FT%TZ) $(nvidia-smi --query-gpu=index,utilization.gpu,memory.used \
            --format=csv,noheader,nounits | paste -sd';')" >> logs/gpuutil_${SLURM_JOB_ID}.log
    sleep 300
  done ) &
HEARTBEAT_PID=$!
# remember to `kill "$HEARTBEAT_PID"` in your cleanup/trap
```

> Note: pinning by UUID is what `MainGPU`/`CUDA_VISIBLE_DEVICES` ultimately
> resolve to anyway, so it never *hurts* — make it the default in every GPU
> sbatch, not just ones that have already been flagged.

---

## 🔍 Debugging Failed Jobs

### Step-by-Step Debugging Process

**1. Check job status:**
```bash
sacct -j 12345 --format=JobID,State,ExitCode,Elapsed
```

**2. Read error log:**
```bash
cat logs/slurm_12345.err
```

**3. Read output log:**
```bash
cat logs/slurm_12345.out
```

**4. Common issues and fixes:**

| Error Message | Cause | Fix |
|--------------|-------|-----|
| "No such file" /home/drn2 | Wrong HOME | Add `export HOME=/scratch/drn2/newhome` |
| FileNotFoundError on input | Wrong paths | Add environment detection to Python |
| ModuleNotFoundError | Package missing | Install in conda environment |
| "conda: command not found" | Conda not sourced | Source conda.sh before activate |
| "Permission denied" | File permissions | Check file ownership/permissions |
| Job "OUT_OF_MEMORY" | Insufficient RAM | Increase `--mem=` or optimize code |
| Job "TIMEOUT" | Exceeded time limit | Increase `--time=` or optimize code |
| Email: "Low GPU usage ... killed" (but job *was* busy) | GPU index mismatch (cgroup idx 0 vs global `SLURM_JOB_GPUS`) | Pin `CUDA_VISIBLE_DEVICES` to the GPU UUID — see MISTAKE 6 |

**5. Test interactively:**
```bash
srun --pty --partition=compute --cpus-per-task=4 --mem=16G --time=1:00:00 bash
# Then manually run the failing script
```

---

## 📋 Quick Reference Commands

### Essential Aliases (Login Node)
```bash
ho      # export HOME=/scratch/drn2/newhome
mamba   # Load modules + activate ML conda env
```

### Job Commands
```bash
sbatch script.sbatch                    # Submit job
squeue -u drn2                          # Check your jobs
scancel 12345                           # Cancel job
tail -f logs/slurm_12345.out           # Watch output
sacct -j 12345                          # Job accounting
sinfo -p nvidia                         # Check GPU availability
```

### File Transfer
```bash
# Upload to HPC
rsync -Pvrt local_dir/ drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/project/

# Download from HPC
rsync -Pvrt drn2@jubail.abudhabi.nyu.edu:/scratch/drn2/PROJECTS/project/results/ local_results/
```

### Environment Check
```bash
echo $HOME                              # Should be /scratch/drn2/newhome
which conda                             # Should show newhome path
hostname                                # Check if on compute/GPU node
module list                             # Show loaded modules
conda info --envs                       # List conda environments
```

---

## 🎓 Advanced Tips

### Efficient Resource Usage

**1. Estimate resources needed:**
```bash
# Test with small dataset interactively
srun --pty --partition=compute --cpus-per-task=4 --mem=16G --time=1:00:00 bash
# Monitor memory usage during test
/usr/bin/time -v python script.py
```

**2. Use array jobs for multiple tasks:**
- More efficient than separate jobs
- Better queue priority
- Easier to monitor

**3. Use job dependencies for workflows:**
```bash
JOB1=$(sbatch --parsable step1.sbatch)
JOB2=$(sbatch --parsable --dependency=afterok:$JOB1 step2.sbatch)
JOB3=$(sbatch --parsable --dependency=afterok:$JOB2 step3.sbatch)
```

### Monitoring Resource Usage

```bash
# Check memory and CPU usage of running job
ssh cn201  # Replace with your node
top -u drn2

# Or use sstat for running jobs
sstat -j 12345 --format=JobID,MaxRSS,MaxVMSize,AveCPU
```

---

## 📞 Getting Help

### HPC Support

**Email:** nyuad.it.help@nyu.edu
**Subject line:** "Jubail HPC - [your issue]"

### Useful Documentation

```bash
# On login node
man sbatch
man squeue
man sacct

# Or online
https://sites.google.com/nyu.edu/nyu-hpc/
```

---

## 🎯 Summary: The Two Golden Rules

1. **NEVER use /home/drn2** → Always use `/scratch/drn2/newhome/`
2. **ALWAYS detect environment in Python** → Local vs HPC paths

**Follow these rules and use the templates above, and you'll avoid 90% of problems!**
