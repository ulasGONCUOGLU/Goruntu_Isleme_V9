"""Ayar doğrulama ve alan JSON testleri (GORUNTU_DATA_DIR geçici klasöre alınır)."""

import importlib

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GORUNTU_DATA_DIR", str(tmp_path))
    import core.paths, core.logger, core.database, core.config
    for m in (core.paths, core.logger, core.database, core.config):
        importlib.reload(m)
    core.database.init_db()
    return core


def test_settings_roundtrip_and_derived(env):
    from core.config import Settings
    s = Settings()
    s.count_conf, s.tracker, s.mode, s.realtime_sync = 0.4, "botsort", "quality", True
    s.save()
    t = Settings.load()
    assert (t.count_conf, t.tracker, t.mode, t.realtime_sync) == (0.4, "botsort", "quality", True)
    assert t.detect_conf == 0.3 and t.imgsz == 960
    assert Settings(count_conf=0.2).detect_conf == 0.2      # detect_conf, count_conf'u asla aşmaz


def test_settings_validation_clamps_bad_values(env):
    from core.config import Settings
    s = Settings(count_conf=5, tracker="yok", mode="x", min_frames_in_zone=0, fps_limit=0)
    s.validate()
    assert s.count_conf == 0.99 and s.tracker == "bytetrack" and s.mode == "balanced"
    assert s.min_frames_in_zone == 1 and s.fps_limit == 1


def test_areas_json_roundtrip_and_rescale(tmp_path):
    from core.areas import load_areas, save_areas
    areas = [{"id": 1, "name": "Giriş Şeridi", "points": [(0, 0), (100, 0), (100, 50)]}]
    f = tmp_path / "a.json"
    save_areas(f, areas, (1280, 720))
    same = load_areas(f, (1280, 720))
    assert same[0]["name"] == "Giriş Şeridi" and same[0]["points"][1] == (100, 0)
    half = load_areas(f, (640, 360))
    assert half[0]["points"][1] == (50, 0) and half[0]["points"][2] == (50, 25)


def test_database_counts_roundtrip(env):
    from core.database import connect, save_counts
    from core.zones import CountSnapshot
    snap = CountSnapshot(
        transitions={("A", "B"): 3},
        transitions_by_class={("A", "B"): {"car": 2, "bus": 1}},
        zone_visits_by_class={"A": {"car": 2}},
    )
    with connect() as conn:
        rid = conn.execute("INSERT INTO video_records (name, video_path) VALUES ('t','')").lastrowid
        save_counts(conn, rid, snap)
        assert conn.execute("SELECT count FROM transition_counts").fetchall() == [(3,)]
        assert sorted(conn.execute("SELECT class_name,count FROM transition_class_counts").fetchall()) \
            == [("bus", 1), ("car", 2)]
