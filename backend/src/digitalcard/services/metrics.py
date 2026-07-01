from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock


@dataclass
class MetricBucket:
    attempts: int = 0
    successes: int = 0


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = 0
        self._errors = 0
        self._durations: deque[float] = deque(maxlen=5000)
        self._business: defaultdict[str, MetricBucket] = defaultdict(MetricBucket)

    def record(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._requests += 1
            self._durations.append(duration_ms)
            if status_code >= 500:
                self._errors += 1
            metric = self._business_metric(method, path)
            if metric:
                bucket = self._business[metric]
                bucket.attempts += 1
                if status_code < 400:
                    bucket.successes += 1

    @staticmethod
    def _business_metric(method: str, path: str) -> str | None:
        if method == "POST" and path.endswith("/publish") and "/tenant/cards/" in path:
            return "card_publish"
        if method == "GET" and path.startswith("/api/v1/public/cards/"):
            suffix = path.removeprefix("/api/v1/public/cards/")
            if "/" not in suffix:
                return "public_card"
        if method == "POST" and path.endswith("/leads") and "/public/cards/" in path:
            return "lead_submit"
        return None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            durations = sorted(self._durations)
            p95_index = max(0, int(len(durations) * 0.95) - 1)
            business = {
                name: {
                    "attempts": bucket.attempts,
                    "successes": bucket.successes,
                    "success_rate": round(bucket.successes / bucket.attempts, 4)
                    if bucket.attempts
                    else None,
                }
                for name, bucket in self._business.items()
            }
            return {
                "requests": self._requests,
                "errors": self._errors,
                "error_rate": round(self._errors / self._requests, 4) if self._requests else 0,
                "p95_duration_ms": round(durations[p95_index], 2) if durations else 0,
                "business": business,
            }

    def reset(self) -> None:
        with self._lock:
            self._requests = 0
            self._errors = 0
            self._durations.clear()
            self._business.clear()


runtime_metrics = RuntimeMetrics()
