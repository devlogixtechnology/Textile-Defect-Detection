from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceSample:
    elapsed_seconds: float
    timestamp: float
    cpu_percent: float | None = None
    process_cpu_percent: float | None = None
    system_memory_percent: float | None = None
    process_rss_mb: float | None = None
    thread_count: int | None = None
    gpu_util_percent: float | None = None
    gpu_memory_used_mb: float | None = None
    gpu_memory_total_mb: float | None = None
    gpu_memory_allocated_mb: float | None = None
    gpu_memory_reserved_mb: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ResourceMonitor:
    def __init__(self, interval_seconds: float = 1.0, enable_gpu: bool = True):
        self.interval_seconds = interval_seconds
        self.enable_gpu = enable_gpu
        self.samples: list[ResourceSample] = []
        self.exceptions: list[str] = []
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="sed3-resource-monitor", daemon=True)
        self._started_at = 0.0
        try:
            import psutil  # type: ignore

            self.psutil = psutil
            self.process = psutil.Process()
            self.process.cpu_percent(interval=None)
        except Exception as exc:
            self.psutil = None
            self.process = None
            self.exceptions.append(f"psutil unavailable: {exc}")

    def start(self) -> None:
        self._started_at = time.perf_counter()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="sed3-resource-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=max(2.0, self.interval_seconds * 2))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.samples.append(self.sample())
            self._stop_event.wait(self.interval_seconds)

    def sample(self) -> ResourceSample:
        elapsed = time.perf_counter() - self._started_at if self._started_at else 0.0
        sample = ResourceSample(elapsed_seconds=elapsed, timestamp=time.time())
        if self.psutil is not None and self.process is not None:
            try:
                sample.cpu_percent = float(self.psutil.cpu_percent(interval=None))
                sample.process_cpu_percent = float(self.process.cpu_percent(interval=None))
                sample.system_memory_percent = float(self.psutil.virtual_memory().percent)
                sample.process_rss_mb = float(self.process.memory_info().rss / (1024 * 1024))
                sample.thread_count = int(self.process.num_threads())
            except Exception as exc:
                self.exceptions.append(f"psutil sample failed: {exc}")
        if self.enable_gpu:
            self._sample_gpu(sample)
        return sample

    def _sample_gpu(self, sample: ResourceSample) -> None:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                sample.gpu_memory_allocated_mb = float(torch.cuda.memory_allocated(0) / (1024 * 1024))
                sample.gpu_memory_reserved_mb = float(torch.cuda.memory_reserved(0) / (1024 * 1024))
        except Exception as exc:
            self.exceptions.append(f"torch gpu sample failed: {exc}")
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                first = result.stdout.strip().splitlines()[0]
                util, mem_used, mem_total = [part.strip() for part in first.split(",")[:3]]
                sample.gpu_util_percent = float(util)
                sample.gpu_memory_used_mb = float(mem_used)
                sample.gpu_memory_total_mb = float(mem_total)
        except FileNotFoundError:
            sample.gpu_util_percent = None
            sample.gpu_memory_used_mb = sample.gpu_memory_allocated_mb
        except Exception as exc:
            self.exceptions.append(f"nvidia-smi sample failed: {exc}")

