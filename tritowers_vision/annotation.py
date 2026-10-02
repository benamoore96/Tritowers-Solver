"""Private annotation contracts and JSON round-tripping.

Coordinates are normalized to [0, 1] so labels remain independent of image size.
This module deliberately has no solver imports or card inference.
"""

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable

from .schema import CaptureMetadata, QualityFlags, RightsRecord, Skin, SlotObservation, SlotState, UIState

SCHEMA_VERSION = "0.3.0"
RANKS = {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}
SUITS = {"C", "D", "H", "S"}
REQUIRED_SLOT_IDS = tuple([f"tableau-{index:02d}" for index in range(1, 29)] + ["waste", "stock"])


class AnnotationError(ValueError):
    pass


def _point(value: Iterable[float]) -> tuple[float, float]:
    try:
        x, y = value
    except (TypeError, ValueError) as error:
        raise AnnotationError("Each point must contain exactly two coordinates.") from error
    x, y = float(x), float(y)
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise AnnotationError("Coordinates must be normalized to [0, 1].")
    return x, y


def _polygon(value: Iterable[Iterable[float]]) -> tuple[tuple[float, float], ...]:
    points = tuple(_point(point) for point in value)
    if len(points) < 4:
        raise AnnotationError("A polygon requires at least four points.")
    area = abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points)))) / 2
    if area <= 1e-6:
        raise AnnotationError("Polygon is degenerate.")
    return points


def _box(value: Iterable[float]) -> tuple[int, int, int, int]:
    try:
        x, y, width, height = (int(item) for item in value)
    except (TypeError, ValueError) as error:
        raise AnnotationError("A box must be four integers: x, y, width, height.") from error
    if min(x, y) < 0 or width <= 0 or height <= 0:
        raise AnnotationError("A box must have nonnegative origin and positive size.")
    return x, y, width, height


def _slot(value: dict[str, Any]) -> SlotObservation:
    try:
        state = SlotState(value.get("state", SlotState.UNKNOWN.value))
        rank = value.get("rank") or None
        suit = value.get("suit") or None
        confidence = float(value.get("confidence", 0.0))
        slot = SlotObservation(
            slot_id=str(value["slot_id"]),
            polygon=_polygon(value["polygon"]),
            box=_box(value["box"]),
            state=state,
            rank=rank,
            suit=suit,
            confidence=confidence,
            adjudication=value.get("adjudication") or None,
        )
    except (KeyError, ValueError) as error:
        raise AnnotationError(f"Invalid slot annotation: {error}") from error
    if rank is not None and rank not in RANKS:
        raise AnnotationError(f"Unsupported rank: {rank}")
    if suit is not None and suit not in SUITS:
        raise AnnotationError(f"Unsupported suit: {suit}")
    if not 0.0 <= confidence <= 1.0:
        raise AnnotationError("Slot confidence must be in [0, 1].")
    return slot


@dataclass(frozen=True)
class AnnotationDocument:
    annotation_id: str
    image_sha256: str
    skin: Skin
    ui_state: UIState
    manual_screen_corners: tuple[tuple[float, float], ...]
    slots: tuple[SlotObservation, ...]
    metadata: CaptureMetadata
    quality: QualityFlags = QualityFlags()
    readable: bool = False
    rejection_reason: str | None = None
    adjudication: str | None = None
    schema_version: str = SCHEMA_VERSION

    def validate(self, require_complete_slots: bool = True) -> None:
        if not self.annotation_id.strip():
            raise AnnotationError("annotation_id is required.")
        if len(self.image_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.image_sha256.lower()):
            raise AnnotationError("image_sha256 must be a 64-character hexadecimal digest.")
        _polygon(self.manual_screen_corners)
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise AnnotationError("Slot IDs must be unique.")
        unknown = set(slot_ids) - set(REQUIRED_SLOT_IDS)
        if unknown:
            raise AnnotationError(f"Unknown slot IDs: {sorted(unknown)}")
        if require_complete_slots and set(slot_ids) != set(REQUIRED_SLOT_IDS):
            missing = sorted(set(REQUIRED_SLOT_IDS) - set(slot_ids))
            raise AnnotationError(f"Missing required slots: {missing}")
        if self.readable and self.rejection_reason:
            raise AnnotationError("A readable frame cannot also have a rejection reason.")
        if not self.metadata.session_id or not self.metadata.machine_id:
            raise AnnotationError("Pseudonymous session_id and machine_id are required.")
        if not self.metadata.rights.permission_basis:
            raise AnnotationError("A rights permission_basis is required.")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["skin"] = self.skin.value
        value["ui_state"] = self.ui_state.value
        for index, slot in enumerate(self.slots):
            value["slots"][index]["state"] = slot.state.value
        return value

    def to_json(self, indent: int = 2) -> str:
        self.validate()
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AnnotationDocument":
        try:
            metadata_value = value["metadata"]
            rights = RightsRecord(**metadata_value.get("rights", {}))
            metadata = CaptureMetadata(**{**metadata_value, "rights": rights})
            quality = QualityFlags(**value.get("quality", {}))
            document = cls(
                annotation_id=value["annotation_id"],
                image_sha256=value["image_sha256"],
                skin=Skin(value.get("skin", Skin.UNKNOWN.value)),
                ui_state=UIState(value.get("ui_state", UIState.UNKNOWN.value)),
                manual_screen_corners=_polygon(value["manual_screen_corners"]),
                slots=tuple(_slot(slot) for slot in value.get("slots", [])),
                metadata=metadata,
                quality=quality,
                readable=bool(value.get("readable", False)),
                rejection_reason=value.get("rejection_reason") or None,
                adjudication=value.get("adjudication") or None,
                schema_version=value.get("schema_version", SCHEMA_VERSION),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise AnnotationError(f"Invalid annotation document: {error}") from error
        document.validate()
        return document

    @classmethod
    def from_json(cls, payload: str) -> "AnnotationDocument":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise AnnotationError(f"Invalid JSON: {error.msg}") from error
        if not isinstance(value, dict):
            raise AnnotationError("Annotation JSON must be an object.")
        return cls.from_dict(value)


def blank_slot_config() -> list[dict[str, Any]]:
    """Return deterministic placeholders to be replaced by manual polygons/boxes."""
    return [{"slot_id": slot_id, "polygon": [], "box": [], "state": SlotState.UNKNOWN.value, "rank": None, "suit": None, "confidence": 0.0, "adjudication": None} for slot_id in REQUIRED_SLOT_IDS]
