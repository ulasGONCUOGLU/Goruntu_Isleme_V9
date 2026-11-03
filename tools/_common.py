"""tools/ altındaki komut satırı araçlarının ortak yardımcıları (arayüzsüz)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.annotate import FrameAnnotator  # noqa: E402
from core.config import Settings  # noqa: E402
from core.detection import DetectionEngine  # noqa: E402
from core.zones import ZoneCounter  # noqa: E402


def load_area_file(path) -> list[dict]:
    from core.areas import load_areas
    return load_areas(path)


def build_pipeline(model_path: str, areas: list[dict], settings: Settings | None = None):
    s = settings or Settings.load()
    eng = DetectionEngine(s)
    eng.configure(s)
    eng.load(model_path)
    zc = ZoneCounter(s.min_frames_in_zone)
    zc.set_areas(areas)
    ann = FrameAnnotator(s.trace_length)
    ann.set_classes(eng.names)
    return s, eng, zc, ann


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
