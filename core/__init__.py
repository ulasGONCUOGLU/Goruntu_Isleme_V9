"""
core/
─────
Arayüzden bağımsız çekirdek katman (V9).

  paths       : Tüm dosya/klasör yolları tek yerde (çalışma dizininden bağımsız)
  logger      : print yerine logging
  database    : Ortak SQLite katmanı + şema sürümlemesi
  config      : Tüm eşikler/ayarlar tek yerde (Settings)
  detection   : YOLO + izleme (DetectionEngine) → supervision.Detections
  zones       : Alan bazlı geçiş sayımı (supervision.PolygonZone)
  annotate    : Kutu / iz / alan çizimi (supervision)
  player      : Video okuma + işleme thread'i (UI'ye kuyrukla veri verir)
  areas       : Alanları JSON'a kaydet / yükle
  text        : Türkçe karakter destekli yazı çizimi
  exporter    : .pt → ONNX / OpenVINO / TensorRT dönüştürme

Bu paket tkinter'e BAĞIMLI DEĞİLDİR; tools/ altındaki komut satırı
araçları ve testler de aynı kodu kullanır.
"""
