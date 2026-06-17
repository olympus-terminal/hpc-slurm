#!/usr/bin/env python3
"""
Jubail HPC GPU Node Monitor

Queries SLURM via SSH to display GPU node capacity, allocation, and job info.
Runs locally — all cluster data gathered over a single SSH session.

Usage:
    python gpu_monitor.py                  # full dashboard
    python gpu_monitor.py --type a100-80g  # filter by GPU type
    python gpu_monitor.py --free           # only nodes with free GPUs
    python gpu_monitor.py --user drn2      # highlight user's jobs
    python gpu_monitor.py --json           # machine-readable output
    python gpu_monitor.py --compact        # one-line-per-node summary
    python gpu_monitor.py --jobs           # all running/pending jobs sorted by runtime
    python gpu_monitor.py --users          # GPU allocation per user
    python gpu_monitor.py --condo          # a2s2 condo nodes only
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional


SSH_HOST = "drn2@jubail.abudhabi.nyu.edu"

GPU_SPECS = {
    "v100":     {"vram_gb": 32,  "generation": "Volta",   "tier": 3},
    "a100":     {"vram_gb": 40,  "generation": "Ampere",  "tier": 2},  # default for 40g feature
    "a100-80g": {"vram_gb": 80,  "generation": "Ampere",  "tier": 1},
    "h100":     {"vram_gb": 80,  "generation": "Hopper",  "tier": 0},
    "h200":     {"vram_gb": 141, "generation": "Hopper",  "tier": 0},
}

CONDO_NODES = {
    "cn260", "cn261", "cn269", "cn274", "cn275",
}

A2S2_NODES = {"cn275", "cn276"}


@dataclass
class GpuNode:
    name: str
    partition: str
    gpu_type: str
    gpu_total: int
    gpu_used: int
    gpu_indices_used: list = field(default_factory=list)
    state: str = ""
    cpus_alloc: int = 0
    cpus_idle: int = 0
    cpus_other: int = 0
    cpus_total: int = 0
    mem_total_mb: int = 0
    mem_alloc_mb: int = 0
    features: str = ""
    jobs: list = field(default_factory=list)

    @property
    def gpu_free(self) -> int:
        return self.gpu_total - self.gpu_used

    @property
    def vram_gb(self) -> int:
        if "141g" in self.features:
            return 141
        if "80g" in self.features:
            return 80
        if "h100" in self.features:
            return 80
        if "40g" in self.features:
            return 40
        if "v100" in self.features:
            return 32
        return GPU_SPECS.get(self.gpu_type, {}).get("vram_gb", 0)

    @property
    def effective_gpu_type(self) -> str:
        if self.gpu_type == "a100" and self.vram_gb == 80:
            return "a100-80g"
        return self.gpu_type

    @property
    def mem_total_gb(self) -> float:
        return self.mem_total_mb / 1024

    @property
    def mem_alloc_gb(self) -> float:
        return self.mem_alloc_mb / 1024

    @property
    def mem_free_gb(self) -> float:
        return (self.mem_total_mb - self.mem_alloc_mb) / 1024

    @property
    def is_condo_only(self) -> bool:
        return self.name in CONDO_NODES

    @property
    def is_a2s2(self) -> bool:
        return self.name in A2S2_NODES

    @property
    def tier(self) -> int:
        return GPU_SPECS.get(self.effective_gpu_type, {}).get("tier", 99)


@dataclass
class GpuJob:
    job_id: str
    user: str
    name: str
    partition: str
    state: str
    time: str
    node: str
    gpus_requested: int
    gpu_type_requested: str = ""
    cpus: int = 0


def ssh_command(cmd: str) -> str:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST, cmd],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"SSH error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def fetch_cluster_data() -> str:
    combined_cmd = (
        "echo '===SINFO==='; "
        "sinfo -p nvidia,condo -N -O 'NodeList:|,Partition:|,Gres:|,GresUsed:|,StateLong:|,CPUsState:|,Memory:|,AllocMem:|,Features:|' 2>/dev/null; "
        "echo '===SQUEUE==='; "
        "squeue -p nvidia,condo -o '%.10i|%.12P|%.30j|%.10u|%.2t|%.12M|%.6D|%.5C|%b|%N' --noheader 2>/dev/null; "
        "echo '===END==='"
    )
    return ssh_command(combined_cmd)


def parse_gres(gres_str: str) -> tuple[str, int]:
    m = re.match(r"gpu:(\w+):(\d+)", gres_str)
    if m:
        return m.group(1), int(m.group(2))
    m = re.match(r"gpu:(\d+)", gres_str)
    if m:
        return "unknown", int(m.group(1))
    return "unknown", 0


def parse_gres_used(gres_used_str: str) -> tuple[int, list[int]]:
    m = re.match(r"gpu:\w+:(\d+)\(IDX:([\d,N/A-]+)\)", gres_used_str)
    if m:
        count = int(m.group(1))
        idx_str = m.group(2)
        indices = []
        if idx_str != "N/A":
            for part in idx_str.split(","):
                if "-" in part:
                    lo, hi = part.split("-")
                    indices.extend(range(int(lo), int(hi) + 1))
                else:
                    indices.append(int(part))
        return count, indices
    m = re.match(r"gpu:\w+:(\d+)", gres_used_str)
    if m:
        return int(m.group(1)), []
    m = re.match(r"gpu:(\d+)", gres_used_str)
    if m:
        return int(m.group(1)), []
    return 0, []


def parse_cpus(cpus_str: str) -> tuple[int, int, int, int]:
    parts = cpus_str.strip().split("/")
    if len(parts) == 4:
        return int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    return 0, 0, 0, 0


def parse_job_gres(tres_str: str) -> tuple[int, str]:
    m = re.match(r"gpu:(\w+):(\d+)", tres_str.strip())
    if m:
        return int(m.group(2)), m.group(1)
    m = re.match(r"gpu:(\d+)", tres_str.strip())
    if m:
        return int(m.group(1)), ""
    return 0, ""


def parse_cluster_data(raw: str) -> tuple[dict[str, GpuNode], list[GpuJob]]:
    sections = raw.split("===SINFO===")
    if len(sections) < 2:
        print("Failed to parse cluster data", file=sys.stderr)
        sys.exit(1)
    rest = sections[1]
    sinfo_raw, squeue_raw = rest.split("===SQUEUE===")

    nodes: dict[str, GpuNode] = {}
    seen_partitions: dict[str, set] = {}

    for line in sinfo_raw.strip().splitlines()[1:]:  # skip header
        fields = [f.strip() for f in line.split("|")]
        if len(fields) < 9:
            continue

        name = fields[0]
        partition = fields[1]
        gres = fields[2]
        gres_used = fields[3]
        state = fields[4]
        cpus = fields[5]
        mem_total = fields[6]
        mem_alloc = fields[7]
        features = fields[8]

        if name in seen_partitions:
            seen_partitions[name].add(partition)
            if name in nodes:
                if partition == "nvidia" and nodes[name].partition == "condo":
                    nodes[name].partition = "nvidia,condo"
                elif partition == "condo" and nodes[name].partition == "nvidia":
                    nodes[name].partition = "nvidia,condo"
            continue
        seen_partitions[name] = {partition}

        gpu_type, gpu_total = parse_gres(gres)
        gpu_used, gpu_indices = parse_gres_used(gres_used)
        cpus_a, cpus_i, cpus_o, cpus_t = parse_cpus(cpus)

        node = GpuNode(
            name=name,
            partition=partition,
            gpu_type=gpu_type,
            gpu_total=gpu_total,
            gpu_used=gpu_used,
            gpu_indices_used=gpu_indices,
            state=state,
            cpus_alloc=cpus_a,
            cpus_idle=cpus_i,
            cpus_other=cpus_o,
            cpus_total=cpus_t,
            mem_total_mb=int(mem_total) if mem_total.isdigit() else 0,
            mem_alloc_mb=int(mem_alloc) if mem_alloc.isdigit() else 0,
            features=features,
        )
        nodes[name] = node

    jobs: list[GpuJob] = []
    for line in squeue_raw.strip().splitlines():
        if "===END===" in line:
            break
        fields = [f.strip() for f in line.split("|")]
        if len(fields) < 10:
            continue
        gpus_req, gpu_type_req = parse_job_gres(fields[8])
        job = GpuJob(
            job_id=fields[0].strip(),
            partition=fields[1].strip(),
            name=fields[2].strip(),
            user=fields[3].strip(),
            state=fields[4].strip(),
            time=fields[5].strip(),
            node=fields[9].strip(),
            gpus_requested=gpus_req,
            gpu_type_requested=gpu_type_req,
            cpus=int(fields[7]) if fields[7].strip().isdigit() else 0,
        )
        jobs.append(job)
        if job.state == "R" and job.node in nodes:
            nodes[job.node].jobs.append(job)

    return nodes, jobs


# ── Terminal colors ──────────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    RESET = "\033[0m"

    @staticmethod
    def disable():
        for attr in dir(C):
            if attr.isupper() and not attr.startswith("_"):
                setattr(C, attr, "")


def gpu_bar(used: int, total: int, width: int = 20) -> str:
    if total == 0:
        return " " * width
    filled = int((used / total) * width)
    empty = width - filled
    if used == total:
        color = C.RED
    elif used == 0:
        color = C.GREEN
    else:
        color = C.YELLOW
    return f"{color}{'█' * filled}{'░' * empty}{C.RESET}"


def mem_bar(used_mb: int, total_mb: int, width: int = 10) -> str:
    if total_mb == 0:
        return " " * width
    filled = int((used_mb / total_mb) * width)
    empty = width - filled
    ratio = used_mb / total_mb
    if ratio > 0.9:
        color = C.RED
    elif ratio > 0.5:
        color = C.YELLOW
    else:
        color = C.GREEN
    return f"{color}{'█' * filled}{'░' * empty}{C.RESET}"


def format_node_detail(node: GpuNode, highlight_user: Optional[str] = None) -> str:
    etype = node.effective_gpu_type.upper()
    vram = f"{node.vram_gb}GB"

    state_color = C.GREEN if node.state == "idle" else (C.YELLOW if node.state == "mixed" else C.RED)
    state_str = f"{state_color}{node.state:<10}{C.RESET}"

    gbar = gpu_bar(node.gpu_used, node.gpu_total, 12)
    mbar = mem_bar(node.mem_alloc_mb, node.mem_total_mb, 8)

    tags = []
    if node.is_a2s2:
        tags.append(f"{C.MAGENTA}a2s2{C.RESET}")
    if node.is_condo_only:
        tags.append(f"{C.CYAN}condo{C.RESET}")

    tag_str = " ".join(tags)
    if tag_str:
        tag_str = f" [{tag_str}]"

    header = (
        f"  {C.BOLD}{node.name:<8}{C.RESET} "
        f"{etype:<10} {vram:<6} "
        f"{gbar} {node.gpu_used}/{node.gpu_total}  "
        f"{node.cpus_alloc:>3}/{node.cpus_total:<3}  "
        f"{mbar} {node.mem_alloc_gb:>6.0f}/{node.mem_total_gb:<6.0f}GB  "
        f"{state_str}{tag_str}"
    )

    lines = [header]
    if node.jobs:
        for job in node.jobs:
            user_color = C.MAGENTA + C.BOLD if (highlight_user and job.user == highlight_user) else ""
            user_reset = C.RESET if user_color else ""
            lines.append(
                f"           {C.DIM}├─{C.RESET} "
                f"{job.job_id:<10} "
                f"{user_color}{job.user:<10}{user_reset} "
                f"gpu:{job.gpus_requested}  "
                f"{job.time:<14} "
                f"{job.name[:35]}"
            )

    return "\n".join(lines)


def print_dashboard(nodes: dict[str, GpuNode], jobs: list[GpuJob], args):
    node_list = list(nodes.values())

    if args.type:
        t = args.type.lower().replace("-", "").replace("_", "")
        node_list = [n for n in node_list if n.effective_gpu_type.replace("-", "") == t
                     or n.gpu_type == t]
    if args.free:
        node_list = [n for n in node_list if n.gpu_free > 0]
    if args.condo:
        node_list = [n for n in node_list if n.is_condo_only or n.is_a2s2]

    node_list.sort(key=lambda n: (n.tier, n.vram_gb * -1, n.name))

    groups: dict[str, list[GpuNode]] = {}
    for n in node_list:
        key = f"{n.effective_gpu_type.upper()} ({n.vram_gb}GB)"
        groups.setdefault(key, []).append(n)

    total_gpus = sum(n.gpu_total for n in node_list)
    total_used = sum(n.gpu_used for n in node_list)
    total_free = total_gpus - total_used
    running = [j for j in jobs if j.state == "R"]
    pending = [j for j in jobs if j.state == "PD"]

    print()
    print(f"  {C.BOLD}Jubail GPU Cluster Status{C.RESET}")
    print(f"  {'─' * 60}")
    print(
        f"  GPUs: {C.GREEN}{total_free} free{C.RESET} / "
        f"{C.YELLOW}{total_used} allocated{C.RESET} / "
        f"{total_gpus} total   "
        f"Jobs: {len(running)} running, {len(pending)} pending"
    )
    print(f"  {'─' * 60}")

    for group_name, group_nodes in groups.items():
        g_total = sum(n.gpu_total for n in group_nodes)
        g_used = sum(n.gpu_used for n in group_nodes)
        g_free = g_total - g_used
        print()
        print(
            f"  {C.BOLD}{C.CYAN}{group_name}{C.RESET}  "
            f"({g_free}/{g_total} GPUs free, {len(group_nodes)} nodes)"
        )
        print(f"  {'─' * 90}")
        print(
            f"  {C.DIM}{'NODE':<9}"
            f"{'TYPE':<11}{'VRAM':<7}"
            f"{'GPU':<18}      "
            f"{'CPU':<8} "
            f"{'MEM':<18}       "
            f"{'STATE'}{C.RESET}"
        )
        for n in group_nodes:
            print(format_node_detail(n, highlight_user=args.user))
        print()

    if args.user:
        my_running = [j for j in running if j.user == args.user]
        my_pending = [j for j in pending if j.user == args.user]
        if my_running or my_pending:
            print(f"  {C.BOLD}Your jobs ({args.user}){C.RESET}")
            print(f"  {'─' * 60}")
            for j in my_running:
                print(
                    f"  {C.GREEN}R{C.RESET} {j.job_id:<10} {j.node:<8} "
                    f"gpu:{j.gpus_requested}  {j.time:<14} {j.name[:40]}"
                )
            for j in my_pending:
                reason = j.node if j.node else "waiting"
                print(
                    f"  {C.YELLOW}PD{C.RESET} {j.job_id:<10} {'':8} "
                    f"gpu:{j.gpus_requested}  {'':14} {j.name[:40]}  ({reason})"
                )
            print()


def print_compact(nodes: dict[str, GpuNode], args):
    node_list = list(nodes.values())
    if args.type:
        t = args.type.lower().replace("-", "").replace("_", "")
        node_list = [n for n in node_list if n.effective_gpu_type.replace("-", "") == t
                     or n.gpu_type == t]
    if args.free:
        node_list = [n for n in node_list if n.gpu_free > 0]
    if args.condo:
        node_list = [n for n in node_list if n.is_condo_only or n.is_a2s2]

    node_list.sort(key=lambda n: (n.tier, n.vram_gb * -1, n.name))

    print(f"{'NODE':<8} {'GPU_TYPE':<10} {'VRAM':>5} {'USED':>4}/{'':<4} {'FREE':>4} {'STATE':<10} {'CPU_USE':>7} {'MEM_GB':>8} {'TAGS'}")
    print("─" * 85)
    for n in node_list:
        tags = []
        if n.is_a2s2:
            tags.append("a2s2")
        if n.is_condo_only:
            tags.append("condo")
        print(
            f"{n.name:<8} {n.effective_gpu_type.upper():<10} {n.vram_gb:>4}G "
            f"{n.gpu_used:>4}/{n.gpu_total:<4} {n.gpu_free:>4} "
            f"{n.state:<10} "
            f"{n.cpus_alloc:>3}/{n.cpus_total:<3} "
            f"{n.mem_alloc_gb:>5.0f}/{n.mem_total_gb:<5.0f} "
            f"{','.join(tags)}"
        )


def parse_time_to_minutes(time_str: str) -> float:
    time_str = time_str.strip()
    days = 0
    if "-" in time_str:
        d, time_str = time_str.split("-", 1)
        days = int(d)
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return days * 1440 + int(h) * 60 + int(m) + int(s) / 60
    if len(parts) == 2:
        m, s = parts
        return days * 1440 + int(m) + int(s) / 60
    return 0


def print_jobs(nodes: dict[str, GpuNode], jobs: list[GpuJob], args):
    job_list = [j for j in jobs if j.state == "R"]

    if args.type:
        t = args.type.lower().replace("-", "").replace("_", "")
        typed_nodes = {n.name for n in nodes.values()
                       if n.effective_gpu_type.replace("-", "") == t or n.gpu_type == t}
        job_list = [j for j in job_list if j.node in typed_nodes]

    job_list.sort(key=lambda j: parse_time_to_minutes(j.time), reverse=True)

    node_gpu_type = {}
    for n in nodes.values():
        node_gpu_type[n.name] = (n.effective_gpu_type.upper(), n.vram_gb)

    print()
    print(f"  {C.BOLD}Running Jobs{C.RESET}  ({len(job_list)} jobs)")
    print(f"  {'─' * 95}")
    print(
        f"  {C.DIM}{'JOB ID':<12} {'USER':<12} {'NODE':<8} {'GPU TYPE':<10} "
        f"{'GPUS':>4}  {'CPUS':>4}  {'RUNTIME':<16} {'NAME'}{C.RESET}"
    )
    print(f"  {'─' * 95}")

    for j in job_list:
        gpu_t, vram = node_gpu_type.get(j.node, ("?", 0))
        user_color = C.MAGENTA + C.BOLD if (args.user and j.user == args.user) else ""
        user_reset = C.RESET if user_color else ""
        print(
            f"  {j.job_id:<12} "
            f"{user_color}{j.user:<12}{user_reset} "
            f"{j.node:<8} {gpu_t:<10} "
            f"{j.gpus_requested:>4}  {j.cpus:>4}  "
            f"{j.time:<16} {j.name[:40]}"
        )

    pending = [j for j in jobs if j.state == "PD"]
    if pending:
        print()
        print(f"  {C.BOLD}Pending Jobs{C.RESET}  ({len(pending)} jobs)")
        print(f"  {'─' * 95}")
        print(
            f"  {C.DIM}{'JOB ID':<12} {'USER':<12} {'':8} {'GPU REQ':<10} "
            f"{'GPUS':>4}  {'CPUS':>4}  {'':16} {'NAME'}{C.RESET}"
        )
        print(f"  {'─' * 95}")
        for j in pending:
            user_color = C.MAGENTA + C.BOLD if (args.user and j.user == args.user) else ""
            user_reset = C.RESET if user_color else ""
            gpu_req = j.gpu_type_requested.upper() if j.gpu_type_requested else "any"
            print(
                f"  {j.job_id:<12} "
                f"{user_color}{j.user:<12}{user_reset} "
                f"{'':8} {gpu_req:<10} "
                f"{j.gpus_requested:>4}  {j.cpus:>4}  "
                f"{'':16} {j.name[:40]}"
            )

    print()


def print_users(nodes: dict[str, GpuNode], jobs: list[GpuJob], args):
    running = [j for j in jobs if j.state == "R"]
    pending = [j for j in jobs if j.state == "PD"]

    if args.type:
        t = args.type.lower().replace("-", "").replace("_", "")
        typed_nodes = {n.name for n in nodes.values()
                       if n.effective_gpu_type.replace("-", "") == t or n.gpu_type == t}
        running = [j for j in running if j.node in typed_nodes]

    node_gpu_type = {}
    for n in nodes.values():
        node_gpu_type[n.name] = n.effective_gpu_type.upper()

    users: dict[str, dict] = {}
    for j in running:
        if j.user not in users:
            users[j.user] = {
                "gpus": 0, "jobs": 0, "gpu_types": set(),
                "nodes": set(), "longest_min": 0, "longest_str": "",
                "pending": 0,
            }
        u = users[j.user]
        u["gpus"] += j.gpus_requested
        u["jobs"] += 1
        u["nodes"].add(j.node)
        gpu_t = node_gpu_type.get(j.node, "?")
        u["gpu_types"].add(gpu_t)
        t_min = parse_time_to_minutes(j.time)
        if t_min > u["longest_min"]:
            u["longest_min"] = t_min
            u["longest_str"] = j.time.strip()

    for j in pending:
        if j.user not in users:
            users[j.user] = {
                "gpus": 0, "jobs": 0, "gpu_types": set(),
                "nodes": set(), "longest_min": 0, "longest_str": "",
                "pending": 0,
            }
        users[j.user]["pending"] += 1

    user_list = sorted(users.items(), key=lambda x: x[1]["gpus"], reverse=True)

    total_gpus = sum(n.gpu_total for n in nodes.values())
    total_used = sum(u["gpus"] for _, u in user_list)

    print()
    print(f"  {C.BOLD}GPU Usage by User{C.RESET}  ({len(user_list)} users)")
    print(f"  {'─' * 95}")
    print(
        f"  {C.DIM}{'USER':<12} {'GPUS':>4}  {'SHARE':>6}  {'JOBS':>4}  {'PEND':>4}  "
        f"{'GPU TYPES':<20} {'NODES':<14} {'LONGEST RUN'}{C.RESET}"
    )
    print(f"  {'─' * 95}")

    for username, u in user_list:
        share = (u["gpus"] / total_gpus * 100) if total_gpus else 0
        gpu_types = ",".join(sorted(u["gpu_types"]))
        node_str = ",".join(sorted(u["nodes"]))
        if len(node_str) > 13:
            node_str = f"{len(u['nodes'])} nodes"

        user_color = C.MAGENTA + C.BOLD if (args.user and username == args.user) else ""
        user_reset = C.RESET if user_color else ""

        share_color = C.RED if share > 20 else (C.YELLOW if share > 10 else "")
        share_reset = C.RESET if share_color else ""

        print(
            f"  {user_color}{username:<12}{user_reset} "
            f"{u['gpus']:>4}  "
            f"{share_color}{share:>5.1f}%{share_reset}  "
            f"{u['jobs']:>4}  "
            f"{u['pending']:>4}  "
            f"{gpu_types:<20} "
            f"{node_str:<14} "
            f"{u['longest_str']}"
        )

    print()


def print_json(nodes: dict[str, GpuNode], jobs: list[GpuJob]):
    output = {
        "nodes": {},
        "summary": {},
        "jobs": {"running": [], "pending": []},
    }
    for name, n in nodes.items():
        output["nodes"][name] = {
            "gpu_type": n.effective_gpu_type,
            "vram_gb": n.vram_gb,
            "gpu_total": n.gpu_total,
            "gpu_used": n.gpu_used,
            "gpu_free": n.gpu_free,
            "gpu_indices_used": n.gpu_indices_used,
            "state": n.state,
            "cpus_total": n.cpus_total,
            "cpus_alloc": n.cpus_alloc,
            "cpus_idle": n.cpus_idle,
            "mem_total_gb": round(n.mem_total_gb, 1),
            "mem_alloc_gb": round(n.mem_alloc_gb, 1),
            "mem_free_gb": round(n.mem_free_gb, 1),
            "partition": n.partition,
            "is_condo_only": n.is_condo_only,
            "is_a2s2": n.is_a2s2,
            "jobs": [{"id": j.job_id, "user": j.user, "name": j.name,
                       "gpus": j.gpus_requested, "time": j.time} for j in n.jobs],
        }

    total_gpus = sum(n.gpu_total for n in nodes.values())
    total_used = sum(n.gpu_used for n in nodes.values())
    output["summary"] = {
        "total_gpus": total_gpus,
        "used_gpus": total_used,
        "free_gpus": total_gpus - total_used,
        "nodes_total": len(nodes),
        "nodes_with_free_gpus": sum(1 for n in nodes.values() if n.gpu_free > 0),
    }

    for j in jobs:
        entry = {"id": j.job_id, "user": j.user, "name": j.name,
                 "partition": j.partition, "gpus": j.gpus_requested,
                 "time": j.time, "node": j.node, "cpus": j.cpus}
        if j.state == "R":
            output["jobs"]["running"].append(entry)
        elif j.state == "PD":
            output["jobs"]["pending"].append(entry)

    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Jubail HPC GPU Node Monitor")
    parser.add_argument("--type", "-t", help="Filter by GPU type (v100, a100, a100-80g, h100, h200)")
    parser.add_argument("--free", "-f", action="store_true", help="Only show nodes with free GPUs")
    parser.add_argument("--user", "-u", default="drn2", help="Highlight user's jobs (default: drn2)")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--compact", "-c", action="store_true", help="Compact one-line-per-node output")
    parser.add_argument("--jobs", action="store_true", help="Job-focused view: all running/pending jobs")
    parser.add_argument("--users", action="store_true", help="User summary: GPU allocation per user")
    parser.add_argument("--condo", action="store_true", help="Only show condo-only / a2s2 nodes")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        C.disable()

    raw = fetch_cluster_data()
    nodes, jobs = parse_cluster_data(raw)

    if args.json:
        print_json(nodes, jobs)
    elif args.jobs:
        print_jobs(nodes, jobs, args)
    elif args.users:
        print_users(nodes, jobs, args)
    elif args.compact:
        print_compact(nodes, args)
    else:
        print_dashboard(nodes, jobs, args)


if __name__ == "__main__":
    main()
