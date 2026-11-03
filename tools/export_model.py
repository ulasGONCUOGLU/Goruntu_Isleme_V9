"""
Komut satırından model dönüştürme.
  python tools/export_model.py dosyalar/Model/x/weights/best.pt --format onnx
  python tools/export_model.py best.pt --format openvino
  python tools/export_model.py best.pt --format engine --half      # NVIDIA + TensorRT
"""

import argparse

import _common  # noqa: F401  (sys.path ayarı; core importlarından ÖNCE gelmeli)
from core.exporter import FORMATS, export_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pt")
    ap.add_argument("--format", choices=list(FORMATS), default="onnx")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--half", action="store_true")
    a = ap.parse_args()
    print(export_model(a.pt, a.format, a.imgsz, a.half))


if __name__ == "__main__":
    main()
