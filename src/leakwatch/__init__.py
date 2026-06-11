"""leakwatch: see every tracker, broker, and fingerprinting trick watching you."""

from leakwatch.classify import classify_host, classify_hosts
from leakwatch.model import ScanResult, TrackerHit, Verdict
from leakwatch.score import compute_verdict

__version__ = "0.6.0"
__all__ = [
    "ScanResult",
    "TrackerHit",
    "Verdict",
    "classify_host",
    "classify_hosts",
    "compute_verdict",
]
