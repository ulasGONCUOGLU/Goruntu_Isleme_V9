"""
ZoneCounter birim testleri — YOLO / video / arayüz gerekmez.
Çalıştır:  python -m pytest -q
"""

import numpy as np
import pytest
import supervision as sv

from core.zones import ZoneCounter

A = {"id": 1, "name": "A", "points": [(0, 0), (100, 0), (100, 100), (0, 100)]}
B = {"id": 2, "name": "B", "points": [(200, 0), (300, 0), (300, 100), (200, 100)]}
C = {"id": 3, "name": "C", "points": [(400, 0), (500, 0), (500, 100), (400, 100)]}


def det(x, tid=1, cls="car", y2=50.0):
    """x'te, 40 px genişliğinde tek tespit (alt-orta nokta: x+20, y2)."""
    return sv.Detections(
        xyxy=np.array([[x, 10, x + 40, y2]], dtype=float),
        tracker_id=np.array([tid]),
        class_id=np.array([0]),
        data={"class_name": np.array([cls])},
    )


def multi(items):
    """items: [(x, tid, cls)]"""
    xyxy = np.array([[x, 10, x + 40, 50.0] for x, _, _ in items], dtype=float)
    return sv.Detections(
        xyxy=xyxy,
        tracker_id=np.array([t for _, t, _ in items]),
        class_id=np.zeros(len(items), dtype=int),
        data={"class_name": np.array([c for _, _, c in items])},
    )


@pytest.fixture
def zc():
    z = ZoneCounter(min_frames_in_zone=1)
    z.set_areas([A, B])
    return z


def test_simple_transition_counted_once(zc):
    zc.update(det(10))
    ev = zc.update(det(220))
    assert [(e.from_area, e.to_area) for e in ev] == [("A", "B")]
    zc.update(det(225))
    zc.update(det(230))
    assert zc.snapshot().transitions[("A", "B")] == 1


def test_gap_between_areas_keeps_state(zc):
    """Alanlar arasındaki boşlukta (hiçbir alanda değil) durum kaybolmamalı."""
    zc.update(det(10))
    for x in (120, 140, 160, 180):            # boşluk
        zc.update(det(x))
    zc.update(det(220))
    assert zc.snapshot().transitions[("A", "B")] == 1


def test_frame_skip_jump_is_counted(zc):
    """Çizgi sayımının kaçırdığı durum: araç iki karede A'dan B'ye 'atlar'."""
    zc.update(det(10))
    zc.update(det(230))                       # arada hiç kare yok
    assert zc.snapshot().transitions[("A", "B")] == 1


def test_debounce_prevents_border_flicker_double_count():
    z = ZoneCounter(min_frames_in_zone=2)
    z.set_areas([A, B])
    z.update(det(10)); z.update(det(10))      # A onaylandı
    z.update(det(220))                        # B'de 1 kare (yetersiz)
    z.update(det(10))                         # tekrar A → aday sıfırlanır
    z.update(det(220))
    assert z.snapshot().transitions[("A", "B")] == 0
    z.update(det(222)); z.update(det(224))    # B'de ardışık 2+ kare → onay
    assert z.snapshot().transitions[("A", "B")] == 1


def test_back_and_forth_counts_both_directions(zc):
    zc.update(det(10)); zc.update(det(220)); zc.update(det(10))
    snap = zc.snapshot()
    assert snap.transitions[("A", "B")] == 1
    assert snap.transitions[("B", "A")] == 1


def test_per_class_counts(zc):
    zc.update(multi([(10, 1, "car"), (10, 2, "truck"), (10, 3, "car")]))
    zc.update(multi([(220, 1, "car"), (220, 2, "truck"), (220, 3, "car")]))
    snap = zc.snapshot()
    assert snap.transitions[("A", "B")] == 3
    assert snap.transitions_by_class[("A", "B")] == {"car": 2, "truck": 1}


def test_zone_visits_unique_per_track(zc):
    zc.update(det(10)); zc.update(det(220)); zc.update(det(10)); zc.update(det(220))
    snap = zc.snapshot()
    assert snap.zone_visits == {"A": 1, "B": 1}      # aynı araç aynı alanı tekrar sayılmaz


def test_first_zone_entry_is_not_a_transition(zc):
    ev = zc.update(det(220))
    assert ev == []
    assert zc.snapshot().total_transitions == 0


def test_detections_without_tracker_id_are_ignored(zc):
    d = det(10)
    d.tracker_id = None
    assert zc.update(d) == []
    assert zc.update(sv.Detections.empty()) == []


def test_three_areas_chain(zc):
    zc.set_areas([A, B, C])
    zc.update(det(10)); zc.update(det(220)); zc.update(det(420))
    t = zc.snapshot().transitions
    assert t[("A", "B")] == 1 and t[("B", "C")] == 1 and t[("A", "C")] == 0


def test_set_areas_preserves_existing_pairs_and_drops_removed(zc):
    zc.update(det(10)); zc.update(det(220))
    zc.set_areas([A, B, C])                           # alan eklendi → eski sayım korunur
    assert zc.snapshot().transitions[("A", "B")] == 1
    zc.set_areas([A, C])                              # B silindi → B'li çiftler düşer
    snap = zc.snapshot()
    assert ("A", "B") not in snap.transitions and ("A", "C") in snap.transitions


def test_reset_counts_and_tracking_state(zc):
    zc.update(det(10)); zc.update(det(220))
    zc.reset_counts()
    assert zc.snapshot().total_transitions == 0
    zc.reset_tracking_state()
    zc.update(det(220))                               # ID 1 yeniden başlıyor → geçiş değil
    assert zc.snapshot().total_transitions == 0


def test_foot_point_is_used_not_box_center():
    """Kutunun merkezi A'da ama alt-orta noktası A dışında → A'da sayılmamalı."""
    z = ZoneCounter(1)
    z.set_areas([A, B])
    d = sv.Detections(xyxy=np.array([[10, 60, 50, 160.0]]), tracker_id=np.array([1]),
                      class_id=np.array([0]), data={"class_name": np.array(["car"])})
    z.update(d)                                       # merkez y=110 değil; alt y=160 → A dışı
    assert z.zone_current()["A"] == 0


def test_stale_state_is_purged():
    z = ZoneCounter(1)
    z.set_areas([A, B])
    z.update(det(10, tid=7))
    for _ in range(ZoneCounter.STALE_AFTER + ZoneCounter.PURGE_EVERY + 5):
        z.update(sv.Detections.empty())
    z.update(det(10, tid=8))                          # purge tetiklenebilsin diye
    z._frame_no = (z._frame_no // ZoneCounter.PURGE_EVERY + 1) * ZoneCounter.PURGE_EVERY - 1
    z.update(det(10, tid=8))
    assert 7 not in z._last_zone


def test_debounce_counts_video_frames_not_processed_frames():
    """Kare atlanırsa (frame_step>1) 'iki kare bekle' kuralı geçerli geçişi kaçırmamalı."""
    z = ZoneCounter(min_frames_in_zone=2)
    z.set_areas([A, B])
    z.update(det(10), frame_step=25)          # A onaylandı (25 video karesi)
    z.update(det(220), frame_step=25)         # B tek işlenen kare ama 25 video karesi
    assert z.snapshot().transitions[("A", "B")] == 1


def test_debounce_still_blocks_flicker_at_normal_speed():
    z = ZoneCounter(min_frames_in_zone=3)
    z.set_areas([A, B])
    for _ in range(3):
        z.update(det(10))
    z.update(det(220)); z.update(det(10))     # tek karelik titreme
    assert z.snapshot().total_transitions == 0


def test_swept_path_counts_zone_skipped_between_frames():
    """İşlenen iki kare arasında dar orta alanı tamamen atlayan araç yine de sayılır."""
    z = ZoneCounter(min_frames_in_zone=1)
    z.set_areas([A, B, C])
    z.update(det(10))                         # A
    z.update(det(420), frame_step=5)          # B'yi hiç görmeden C'ye sıçradı
    t = z.snapshot().transitions
    assert t[("A", "B")] == 1 and t[("B", "C")] == 1 and t[("A", "C")] == 0


def test_swept_path_not_applied_after_long_disappearance():
    z = ZoneCounter(min_frames_in_zone=1)
    z.set_areas([A, B, C])
    z.update(det(10))
    z.update(det(420), frame_step=ZoneCounter.MAX_BRIDGE + 50)   # çok uzun kayıp → köprü yok
    t = z.snapshot().transitions
    assert t[("A", "B")] == 0 and t[("A", "C")] == 1


def test_swept_path_ignores_zones_not_on_the_path():
    z = ZoneCounter(min_frames_in_zone=1)
    z.set_areas([A, B, C])
    z.update(det(10))
    z.update(det(150), frame_step=2)          # boşluğa çıktı; B/C yolda değil
    assert z.snapshot().total_transitions == 0
