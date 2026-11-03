"""
FPS karşılaştırması: .pt / ONNX / OpenVINO / TensorRT ve izleyici türleri.

Kullanım:
  python tools/benchmark.py --video v.mp4 --models a/best.pt a/best.onnx --frames 150
  python tools/benchmark.py --video v.mp4 --models a/best.pt --tracker bytetrack --tracker botsort

Çıktı: model × izleyici başına ortalama FPS ve kare başı ms (ilk 5 kare ısınma, hariç).
"""

import argparse
import time

import cv2

import _common  # noqa: F401  (sys.path ayarı; core importlarından ÖNCE gelmeli)
from core.config import Settings
from core.detection import DetectionEngine


def bench(video, model, tracker, frames, mode):
    s = Settings.load()
    s.tracker, s.mode = tracker, mode
    eng = DetectionEngine(s)
    eng.configure(s)
    eng.load(model)
    eng.reset_tracker()
    cap = cv2.VideoCapture(video)
    times, n = [], 0
    while n < frames:
        ok, f = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            eng.reset_tracker()
            continue
        t = time.perf_counter()
        eng.infer(f)
        dt = time.perf_counter() - t
        n += 1
        if n > 5:
            times.append(dt)
    cap.release()
    avg = sum(times) / len(times)
    return 1.0 / avg, avg * 1000, eng.device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tracker", action="append", choices=["bytetrack", "botsort"])
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--mode", default="balanced", choices=["fast", "balanced", "quality"])
    a = ap.parse_args()

    print(f"{'model':45s} {'izleyici':10s} {'cihaz':8s} {'FPS':>7s} {'ms/kare':>9s}")
    for m in a.models:
        for t in (a.tracker or ["bytetrack"]):
            try:
                fps, ms, dev = bench(a.video, m, t, a.frames, a.mode)
                print(f"{m[-45:]:45s} {t:10s} {dev:8s} {fps:7.1f} {ms:9.1f}")
            except Exception as e:
                print(f"{m[-45:]:45s} {t:10s} HATA: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
