"""Immutable data shared by detection, tracking and product dispatch."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """One observation in one image; it does not identify a fruit across frames."""

    # Pixel coordinates on the original image, before inference resizing.
    xyxy: tuple[float, float, float, float]
    class_id: int
    label: str
    confidence: float


@dataclass(frozen=True)
class TrackedDetection:
    """A detection assigned to a fruit by the tracker.

    track_id stays unique during one pipeline run and is not a UART sequence.
    observed_at is the source frame's monotonic timestamp, in seconds.
    """

    track_id: int
    detection: Detection
    observed_at: float


@dataclass(frozen=True)
class CrossingEvent:
    """A fruit first observed crossing the decision line in the allowed direction.

    The crossing stage emits at most one event per track_id during a run.
    label/confidence are the decision at crossing, independent of later frames.
    crossed_at is the confirming frame's monotonic timestamp, in seconds;
    it estimates the crossing time, not the time the UART command was sent.
    """

    track_id: int
    label: str
    confidence: float
    crossed_at: float
