from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .camera_source import CameraSource, FileCameraSource
from .geofence import filter_detections_for_camera
from .models import CameraConfig, CameraMetrics, DetectionResult, FramePacket, StreamStatus


DetectorCallable = Callable[[list[Any]], tuple[list[list[dict[str, Any]]], float]]


class StreamWorker:
    def __init__(
        self,
        config: CameraConfig,
        frame_queue: queue.Queue[FramePacket],
        metrics: CameraMetrics,
        stop_event: threading.Event,
        source_factory: Callable[[CameraConfig], CameraSource] | None = None,
    ):
        self.config = config
        self.frame_queue = frame_queue
        self.metrics = metrics
        self.stop_event = stop_event
        self.source_factory = source_factory or (lambda cfg: FileCameraSource(cfg.source, loop=cfg.loop))
        self.thread = threading.Thread(target=self._run, name=f"capture-{config.camera_id}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def join(self, timeout: float | None = None) -> None:
        self.thread.join(timeout=timeout)

    def _run(self) -> None:
        source = self.source_factory(self.config)
        frame_id = 0
        last_eligible = 0.0
        self.metrics.started_at = perf_counter()
        self.metrics.status = "starting"
        try:
            source.open()
            self.metrics.status = "running"
            while not self.stop_event.is_set():
                ok, frame = source.read()
                if not ok:
                    self.metrics.decode_failures += 1
                    self.metrics.status = "ended"
                    break
                now = perf_counter()
                self.metrics.captured += 1
                frame_id += 1
                if self.config.sampling_fps:
                    min_interval = 1.0 / max(0.001, float(self.config.sampling_fps))
                    if last_eligible and now - last_eligible < min_interval:
                        self.metrics.configured_skips += 1
                        continue
                    last_eligible = now
                self.metrics.eligible += 1
                packet = FramePacket(
                    camera_id=self.config.camera_id,
                    frame_id=frame_id,
                    timestamp=time.time(),
                    frame=frame,
                    source_fps=float(getattr(source, "source_fps", 0.0) or 0.0),
                    capture_time=now,
                )
                self._submit_latest(packet)
        except Exception as exc:
            self.metrics.status = "failed"
            self.metrics.last_error = str(exc)
        finally:
            source.close()
            self.metrics.ended_at = perf_counter()
            if self.metrics.status == "running":
                self.metrics.status = "stopped"

    def _submit_latest(self, packet: FramePacket) -> None:
        try:
            self.frame_queue.put_nowait(packet)
            self.metrics.submitted += 1
        except queue.Full:
            try:
                self.frame_queue.get_nowait()
                self.metrics.overload_drops += 1
            except queue.Empty:
                pass
            self.frame_queue.put_nowait(packet)
            self.metrics.submitted += 1
        self.metrics.queue_depth_samples.append(self.frame_queue.qsize())


class MultiCameraStreamManager:
    def __init__(
        self,
        cameras: list[CameraConfig],
        detector: Any,
        alert_policy_factory: Callable[[], Any] | None = None,
        escalation_manager: Any | None = None,
        queue_size: int = 2,
        micro_batch: bool = True,
        source_factory: Callable[[CameraConfig], CameraSource] | None = None,
    ):
        self.cameras = {camera.camera_id: camera for camera in cameras if camera.enabled}
        self.detector = detector
        self.alert_policies = {
            camera_id: alert_policy_factory() if alert_policy_factory else None for camera_id in self.cameras
        }
        self.escalation_manager = escalation_manager
        self.queues = {camera_id: queue.Queue(maxsize=queue_size) for camera_id in self.cameras}
        self.metrics = {camera_id: CameraMetrics() for camera_id in self.cameras}
        self.latest_results: dict[str, DetectionResult] = {}
        self.active_alerts: list[dict[str, Any]] = []
        self.active_escalations: list[dict[str, Any]] = []
        self.micro_batch = micro_batch
        self.source_factory = source_factory
        self.stop_event = threading.Event()
        self.result_lock = threading.Lock()
        self.workers: list[StreamWorker] = []
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, name="sed1-inference-scheduler", daemon=True)

    def start(self) -> None:
        self.stop_event.clear()
        self.workers = [
            StreamWorker(
                self.cameras[camera_id],
                self.queues[camera_id],
                self.metrics[camera_id],
                self.stop_event,
                source_factory=self.source_factory,
            )
            for camera_id in self.cameras
        ]
        for worker in self.workers:
            worker.start()
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, name="sed1-inference-scheduler", daemon=True)
        self.scheduler_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        for worker in self.workers:
            worker.join(timeout=timeout)
        self.scheduler_thread.join(timeout=timeout)
        ended = perf_counter()
        for metric in self.metrics.values():
            if metric.ended_at is None:
                metric.ended_at = ended
            if metric.status in {"running", "starting"}:
                metric.status = "stopped"

    def restart(self) -> None:
        self.stop()
        self.start()

    def statuses(self) -> list[StreamStatus]:
        statuses = []
        for camera_id, camera in self.cameras.items():
            metric = self.metrics[camera_id]
            statuses.append(
                StreamStatus(
                    camera_id=camera_id,
                    name=camera.name,
                    enabled=camera.enabled,
                    status=metric.status,
                    captured=metric.captured,
                    eligible=metric.eligible,
                    processed=metric.processed,
                    overload_drops=metric.overload_drops,
                    drop_rate_pct=metric.unexpected_drop_rate,
                    processed_fps=metric.processed_fps,
                    queue_depth=self.queues[camera_id].qsize(),
                    last_error=metric.last_error,
                )
            )
        return statuses

    def _scheduler_loop(self) -> None:
        while not self.stop_event.is_set() or any(not q.empty() for q in self.queues.values()):
            packets = self._next_fair_batch()
            if not packets:
                time.sleep(0.005)
                continue
            frames = [packet.frame for packet in packets]
            started = perf_counter()
            detections_by_frame, inference_elapsed = self.detector.predict_batch(frames)
            total_elapsed = perf_counter() - started
            per_frame_inference = inference_elapsed / max(1, len(packets))
            for packet, detections in zip(packets, detections_by_frame):
                self._route_result(packet, detections, per_frame_inference, total_elapsed / max(1, len(packets)))

    def _next_fair_batch(self) -> list[FramePacket]:
        packets: list[FramePacket] = []
        for camera_id in self.cameras:
            try:
                packets.append(self.queues[camera_id].get_nowait())
            except queue.Empty:
                continue
            if not self.micro_batch:
                break
        return packets

    def _route_result(
        self,
        packet: FramePacket,
        detections: list[dict[str, Any]],
        inference_time: float,
        processing_time: float,
    ) -> None:
        camera = self.cameras[packet.camera_id]
        geofenced, matches = filter_detections_for_camera(detections, camera, frame=packet.frame)
        policy = self.alert_policies.get(packet.camera_id)
        calibrated = geofenced
        alerts: list[dict[str, Any]] = []
        escalations: list[dict[str, Any]] = []
        if policy is not None:
            policy_result = policy.process_frame(geofenced, frame_index=packet.frame_id, timestamp_sec=packet.timestamp)
            calibrated = policy_result.get("calibrated_detections", [])
            alerts = policy_result.get("alerts", [])
            for alert in alerts:
                alert["camera_id"] = packet.camera_id
                alert["camera_name"] = camera.name
        if self.escalation_manager is not None and policy is not None:
            active_violations = self._confirmed_violations(policy, calibrated)
            escalations = [
                event.to_dict()
                for event in self.escalation_manager.process_frame(
                    packet.camera_id,
                    active_violations,
                    timestamp=packet.timestamp,
                )
            ]
        latency = perf_counter() - packet.capture_time
        result = DetectionResult(
            camera_id=packet.camera_id,
            frame_id=packet.frame_id,
            timestamp=packet.timestamp,
            detections=detections,
            calibrated_detections=calibrated,
            alerts=alerts,
            escalations=escalations,
            geofence_matches=matches,
            inference_time=inference_time,
            processing_time=processing_time,
            end_to_end_latency=latency,
        )
        metric = self.metrics[packet.camera_id]
        metric.processed += 1
        metric.inference_times.append(inference_time)
        metric.processing_times.append(processing_time)
        metric.latencies.append(latency)
        metric.queue_depth_samples.append(self.queues[packet.camera_id].qsize())
        with self.result_lock:
            self.latest_results[packet.camera_id] = result
            self.active_alerts.extend(alerts)
            if self.escalation_manager is not None:
                self.active_escalations = self.escalation_manager.active_events()

    @staticmethod
    def _confirmed_violations(policy: Any, calibrated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        active = getattr(getattr(policy, "manager", None), "active", {})
        active_classes = {class_name for class_name, is_active in active.items() if is_active}
        if not active_classes:
            return []
        best_by_class: dict[str, dict[str, Any]] = {}
        for det in calibrated:
            class_name = str(det.get("class_name", det.get("class", ""))).strip().lower().replace("_", " ").replace("-", " ")
            if class_name not in active_classes:
                continue
            current = best_by_class.get(class_name)
            if current is None or float(det.get("confidence", 0.0)) > float(current.get("confidence", 0.0)):
                out = dict(det)
                out["source"] = "cme2_confirmed"
                best_by_class[class_name] = out
        return list(best_by_class.values())


def default_model_path(project_root: str | Path) -> Path:
    return Path(project_root) / "Backend" / "best.pt"


