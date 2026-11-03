import tkinter as tk
from tkinter import ttk, filedialog
import os
import re
import sys
import threading
import queue

from core.paths import MODEL_TRAIN_DIR


class AITrainContainer:
    """
    AI Train (AI Eğitimi) paneli.
    İçerik daha sonra burada geliştirilecek.
    """

    def __init__(self, parent_frame, colors):
        self.parent_frame = parent_frame
        self.colors = colors
        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._selected_data_yaml: str | None = None
        self._selected_model_name: str | None = None

        self.frame = tk.Frame(parent_frame, bg=colors['bg_dark'])
        self.frame.pack(fill=tk.BOTH, expand=True)

        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self):
        header = tk.Frame(self.frame, bg=self.colors['bg_medium'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🧪  AI Eğitimi",
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            padx=20
        ).pack(side=tk.LEFT, pady=15)

        body = tk.Frame(self.frame, bg=self.colors['bg_dark'])
        body.pack(fill=tk.BOTH, expand=True)

        # Üst kontrol alanı
        controls = tk.Frame(body, bg=self.colors['bg_dark'])
        controls.pack(fill=tk.X, padx=30, pady=(25, 10))

        self.select_btn = tk.Button(
            controls,
            text="🧪  AI Eğitim Paketini Seçiniz",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['accent'],
            fg='white',
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2',
            command=self._select_dataset_yaml
        )
        self.select_btn.pack(side=tk.LEFT)

        self.train_btn = tk.Button(
            controls,
            text="▶  Eğitimi Başlat",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['bg_light'],
            fg=self.colors['text'],
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2',
            state=tk.DISABLED,
            command=self._start_training
        )
        self.train_btn.pack(side=tk.LEFT, padx=(12, 0))

        self.status_var = tk.StringVar(value="Durum: veri seti seçilmedi")
        tk.Label(
            controls,
            textvariable=self.status_var,
            font=('Segoe UI', 10),
            bg=self.colors['bg_dark'],
            fg='#888888',
            padx=14
        ).pack(side=tk.LEFT)

        # Seçim özeti
        self.selection_var = tk.StringVar(value="Seçilen: —")
        tk.Label(
            body,
            textvariable=self.selection_var,
            font=('Segoe UI', 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            anchor='w',
            justify=tk.LEFT
        ).pack(fill=tk.X, padx=30, pady=(0, 10))

        # Log alanı
        log_wrapper = tk.Frame(body, bg=self.colors['bg_dark'])
        log_wrapper.pack(fill=tk.BOTH, expand=True, padx=30, pady=(10, 25))

        self.log_text = tk.Text(
            log_wrapper,
            bg=self.colors['bg_medium'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief=tk.FLAT,
            wrap='word',
            font=('Consolas', 10)
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_wrapper, orient='vertical', command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self._log("Hazır. 'AI Eğitim Paketini Seçiniz' ile data.yaml seçin.\n")

    # ────────────────────────────────────────────────────────────
    # Seçim / isim okuma
    # ────────────────────────────────────────────────────────────

    def _select_dataset_yaml(self):
        path = filedialog.askopenfilename(
            title="Roboflow veri seti data.yaml seçiniz",
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if not path:
            return

        path = os.path.normpath(path)
        data_dir = os.path.dirname(path)
        model_name = self._parse_model_name_from_readme(data_dir)

        self._selected_data_yaml = path
        self._selected_model_name = model_name

        self.selection_var.set(
            f"Seçilen data.yaml: {path}\nModel adı (README'den): {model_name}\nÇıktı klasörü: {os.path.join(str(MODEL_TRAIN_DIR), model_name)}"
        )
        self.status_var.set("Durum: hazır (eğitim başlatılabilir)")
        self.train_btn.configure(state=tk.NORMAL)

    def _parse_model_name_from_readme(self, data_dir: str) -> str:
        """
        README.roboflow.txt dosyasının ilk 2 satırından model ismini çeker.
        Örnek: "Car Detection - v4 Car Detection 4"
        Çıktı : "Car_Detection_v4_Car_Detection_4"
        """
        readme_path = os.path.join(data_dir, "README.roboflow.txt")

        if not os.path.exists(readme_path):
            self._log(f"[UYARI] README.roboflow.txt bulunamadı: {readme_path}\n")
            self._log("[UYARI] Varsayılan isim kullanılıyor: yolo11_model\n")
            return "yolo11_model"

        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            self._log(f"[UYARI] README okunamadı ({e}). Varsayılan isim kullanılıyor.\n")
            return "yolo11_model"

        first_two_lines = " ".join(line.strip() for line in lines[:2]).strip()
        if not first_two_lines:
            self._log("[UYARI] README.roboflow.txt boş. Varsayılan isim kullanılıyor.\n")
            return "yolo11_model"

        clean_name = re.sub(r"[^\w\s]", "", first_two_lines)
        clean_name = re.sub(r"\s+", "_", clean_name.strip())

        self._log(f"[BİLGİ] README'den okunan isim : '{first_two_lines}'\n")
        self._log(f"[BİLGİ] Kullanılacak model adı : '{clean_name}'\n")
        return clean_name

    # ────────────────────────────────────────────────────────────
    # Eğitim
    # ────────────────────────────────────────────────────────────

    def _start_training(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return
        if not self._selected_data_yaml or not self._selected_model_name:
            return

        self._log("\nEğitim başlatılıyor...\n")
        self.status_var.set("Durum: eğitim çalışıyor...")
        self.select_btn.configure(state=tk.DISABLED)
        self.train_btn.configure(state=tk.DISABLED)

        self._worker_thread = threading.Thread(target=self._training_worker, daemon=True)
        self._worker_thread.start()

    def _training_worker(self):
        data_path = self._selected_data_yaml
        model_name = self._selected_model_name
        if not data_path or not model_name:
            return

        try:
            from ultralytics import YOLO  # lazy import
            import torch
        except Exception as e:
            self._log(f"[HATA] ultralytics/torch import edilemedi: {e}\n")
            self._log("Kurulum için: pip install ultralytics torch\n")
            self._log_queue.put("\n__TRAIN_DONE__\n")
            return

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._log(f"Kullanılan cihaz: {device}\n")

        output_root = str(MODEL_TRAIN_DIR)
        os.makedirs(output_root, exist_ok=True)

        # YOLOv11 modelini yükle (nano)
        model = YOLO("yolo11n.pt")

        training_args = {
            "data": data_path,
            "epochs": 100,
            "imgsz": 640,
            "batch": 16,
            "device": device,
            "workers": 4,
            "patience": 20,
            "save": True,
            "save_period": 10,
            "cache": True,
            # Çıktıları doğrudan dosyalar/Model altına at
            "project": output_root,
            "name": model_name,
            "exist_ok": True,
            "pretrained": True,
            "optimizer": "AdamW",
            "lr0": 0.01,
            "lrf": 0.01,
            "momentum": 0.937,
            "weight_decay": 0.0005,
            "warmup_epochs": 3,
            "warmup_momentum": 0.8,
            "warmup_bias_lr": 0.1,
            "box": 7.5,
            "cls": 0.5,
            "dfl": 1.5,
            "label_smoothing": 0.0,
            "nbs": 64,
            "hsv_h": 0.015,
            "hsv_s": 0.7,
            "hsv_v": 0.4,
            "degrees": 0.0,
            "translate": 0.1,
            "scale": 0.5,
            "shear": 0.0,
            "perspective": 0.0,
            "flipud": 0.0,
            "fliplr": 0.5,
            "mosaic": 1.0,
            "mixup": 0.0,
            "copy_paste": 0.0,
        }

        self._log("\nEğitim parametreleri:\n")
        self._log(f"  Veri seti   : {data_path}\n")
        self._log(f"  Model adı   : {model_name}\n")
        self._log(f"  Çıktı       : {os.path.join(output_root, model_name)}\n")
        self._log(f"  Epoch       : {training_args['epochs']}\n")
        self._log(f"  Batch       : {training_args['batch']}\n")
        self._log(f"  İmaj boyutu : {training_args['imgsz']}\n\n")

        try:
            with self._redirect_std_streams():
                results = model.train(**training_args)

            self._log("\nEğitim tamamlandı!\n")
            try:
                self._log(f"Çıktı klasörü : {results.save_dir}\n")
                self._log(f"En iyi model  : {results.save_dir}/weights/best.pt\n")
                self._log(f"Son model     : {results.save_dir}/weights/last.pt\n")
            except Exception:
                pass

            self._log("\nModel değerlendiriliyor...\n")
            with self._redirect_std_streams():
                metrics = model.val(data=data_path)

            try:
                self._log(f"mAP50    : {metrics.box.map50:.4f}\n")
                self._log(f"mAP50-95 : {metrics.box.map:.4f}\n")
            except Exception:
                pass

        except Exception as e:
            self._log(f"\n[HATA] Eğitim sırasında hata oluştu: {e}\n")

        self._log_queue.put("\n__TRAIN_DONE__\n")

    # ────────────────────────────────────────────────────────────
    # Log / stdout yakalama
    # ────────────────────────────────────────────────────────────

    def _log(self, text: str):
        self._log_queue.put(text)

    class _QueueWriter:
        def __init__(self, q: "queue.Queue[str]"):
            self.q = q

        def write(self, s: str):
            if s:
                self.q.put(s)

        def flush(self):
            pass

    class _StdRedirect:
        def __init__(self, q: "queue.Queue[str]"):
            self.q = q
            self._old_out = None
            self._old_err = None

        def __enter__(self):
            self._old_out = sys.stdout
            self._old_err = sys.stderr
            writer = AITrainContainer._QueueWriter(self.q)
            sys.stdout = writer
            sys.stderr = writer
            return self

        def __exit__(self, exc_type, exc, tb):
            sys.stdout = self._old_out
            sys.stderr = self._old_err

    def _redirect_std_streams(self):
        return AITrainContainer._StdRedirect(self._log_queue)

    def _poll_log_queue(self):
        # \r içeren progress çıktıları aynı satırı günceller; \n gelince alt satıra geçer
        try:
            while True:
                chunk = self._log_queue.get_nowait()
                if chunk == "\n__TRAIN_DONE__\n":
                    self.status_var.set("Durum: tamamlandı")
                    self.select_btn.configure(state=tk.NORMAL)
                    # data seçili kaldıysa tekrar eğitim başlatılabilir
                    self.train_btn.configure(state=tk.NORMAL if self._selected_data_yaml else tk.DISABLED)
                    continue

                self._append_console_chunk(chunk)
        except queue.Empty:
            pass
        self.frame.after(60, self._poll_log_queue)

    def _append_console_chunk(self, chunk: str):
        # Text widget düzenleme: kullanıcı yazamasın
        self.log_text.configure(state=tk.NORMAL)

        # Parçayı \r'lere göre işle: \r = aynı satırı replace
        parts = chunk.split("\r")
        for i, part in enumerate(parts):
            if i == 0:
                # ilk parça normal append
                self.log_text.insert(tk.END, part)
            else:
                # replace current line with "part"
                # Her zaman son satırı güncelle (progress bar gibi)
                line_start = self.log_text.index("end-1c linestart")
                line_end = self.log_text.index("end-1c lineend")
                self.log_text.delete(line_start, line_end)
                self.log_text.insert(line_start, part)

        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def cleanup(self):
        pass

