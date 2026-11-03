"""
Sayım doğruluk testi (arayüzsüz).

Elle saydığın referans değerlerle sistemin sayımını karşılaştırır ve
"kare atlama" senaryosunu simüle eder: --skip N verilirse her N. kare
işlenir (arada kalan kareler hiç görülmez). Aynı koşulda bir ÇİZGİ
sayacı (supervision.LineZone) da çalıştırılır; böylece alan bazlı
yaklaşımın neden daha güvenli olduğu ölçülebilir.

Kullanım:
  python tools/count_accuracy.py --video v.mp4 --model dosyalar/Model/x/weights/best.pt \
      --areas dosyalar/alanlar/sablon.json --truth truth.json --skip 1 --skip 5 --skip 10

truth.json (elle sayım):
  {"Giriş->Çıkış": 12, "Çıkış->Giriş": 3}
  (--truth verilmezse yalnızca sistem sayımı yazdırılır.)
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

from _common import build_pipeline, load_area_file


def run(video, model, areas, skip, with_line):
    s, eng, zc, _ = build_pipeline(model, areas)
    eng.reset_tracker()
    cap = cv2.VideoCapture(video)

    line = None
    if with_line and len(areas) >= 2:
        # Çizgi: ilk iki alanın merkezlerini birleştiren doğru
        c = [np.mean(np.array(a["points"]), axis=0) for a in areas[:2]]
        mid = (c[0] + c[1]) / 2
        v = c[1] - c[0]
        n = np.array([-v[1], v[0]]) / (np.linalg.norm(v) + 1e-9)
        p1, p2 = mid - n * 2000, mid + n * 2000
        line = sv.LineZone(start=sv.Point(*p1), end=sv.Point(*p2),
                           triggering_anchors=(sv.Position.BOTTOM_CENTER,))

    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if (i - 1) % skip:
            continue
        det = eng.infer(frame)
        zc.update(det, frame_step=skip)
        if line is not None and len(det):
            line.trigger(det)
    cap.release()

    snap = zc.snapshot()
    res = {f"{a}->{b}": n for (a, b), n in snap.transitions.items()}
    if line is not None:
        res["_cizgi_toplam"] = line.in_count + line.out_count
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--areas", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--skip", type=int, action="append", help="her N. kareyi işle (birden çok verilebilir)")
    ap.add_argument("--no-line", action="store_true")
    a = ap.parse_args()

    areas = load_area_file(a.areas)
    truth = json.loads(Path(a.truth).read_text(encoding="utf-8")) if a.truth else None
    total_truth = sum(truth.values()) if truth else None

    for skip in (a.skip or [1]):
        res = run(a.video, a.model, areas, skip, not a.no_line)
        print(f"\n=== skip={skip} (her {skip}. kare işlendi) ===")
        for k, v in res.items():
            if k.startswith("_"):
                continue
            line = f"  {k:30s} sistem={v}"
            if truth and k in truth:
                line += f"  gerçek={truth[k]}  fark={v - truth[k]:+d}"
            print(line)
        sys_total = sum(v for k, v in res.items() if not k.startswith("_"))
        print(f"  {'TOPLAM (alan bazlı)':30s} {sys_total}" + (f"   gerçek={total_truth}" if truth else ""))
        if "_cizgi_toplam" in res:
            print(f"  {'TOPLAM (orta çizgi; farklı tanım)':30s} {res['_cizgi_toplam']}")


if __name__ == "__main__":
    main()
