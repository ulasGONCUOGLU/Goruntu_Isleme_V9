import tkinter as tk
from tkinter import messagebox
import os
import cv2
from PIL import Image, ImageTk

from core.paths import VIDEO_DIR


class FilesContainer:
    """Dosyalar sayfası - kayıtlı videoları küçük önizleme ile listeler."""

    def __init__(self, parent_frame, colors, open_video_callback):
        """
        Args:
            parent_frame: Ana sağ paneldeki frame.
            colors: main.py içindeki renk paleti dict'i.
            open_video_callback: Seçilen videoyu Video panelinde açacak fonksiyon.
        """
        self.parent_frame = parent_frame
        self.colors = colors
        self.open_video_callback = open_video_callback

        # Kayıtlı videoların olduğu klasör
        self.video_dir = str(VIDEO_DIR)

        # Tkinter Image referanslarını saklamak için
        self.thumbnails = {}

        self.setup_ui()
        self.load_videos()

    def setup_ui(self):
        """UI bileşenlerini oluştur."""
        main_container = tk.Frame(self.parent_frame, bg=self.colors["bg_dark"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Başlık ve yenile butonu
        header = tk.Frame(main_container, bg=self.colors["bg_medium"])
        header.pack(fill=tk.X, pady=(0, 10))

        title = tk.Label(
            header,
            text="📁 Kayıtlı Videolar",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["bg_medium"],
            fg=self.colors["text"],
            pady=10,
        )
        title.pack(side=tk.LEFT, padx=15)

        refresh_btn = tk.Button(
            header,
            text="🔄 Yenile",
            font=("Segoe UI", 10),
            bg=self.colors["accent"],
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            command=self.load_videos,
        )
        refresh_btn.pack(side=tk.RIGHT, padx=15, pady=5)

        # Scrollable alan (canvas + scrollbar)
        list_container = tk.Frame(main_container, bg=self.colors["bg_dark"])
        list_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            list_container, bg=self.colors["bg_dark"], highlightthickness=0
        )
        scrollbar = tk.Scrollbar(
            list_container, orient="vertical", command=self.canvas.yview
        )
        self.inner_frame = tk.Frame(self.canvas, bg=self.colors["bg_dark"])

        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

    def load_videos(self):
        """Klasörden videoları yükle ve listeyi oluştur."""
        # Eski öğeleri temizle
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self.thumbnails.clear()

        if not os.path.exists(self.video_dir):
            os.makedirs(self.video_dir, exist_ok=True)

        # Sadece video uzantılarını al
        video_files = [
            f
            for f in os.listdir(self.video_dir)
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
        ]

        if not video_files:
            no_data = tk.Label(
                self.inner_frame,
                text="Henüz kayıtlı video bulunamadı.",
                font=("Segoe UI", 12),
                bg=self.colors["bg_dark"],
                fg=self.colors["text"],
                pady=20,
            )
            no_data.pack()
            return

        # Grid şeklinde göster (3 sütun)
        columns = 3
        thumb_width, thumb_height = 200, 120

        for idx, filename in enumerate(sorted(video_files)):
            row = idx // columns
            col = idx % columns
            full_path = os.path.join(self.video_dir, filename)

            item_frame = tk.Frame(
                self.inner_frame,
                bg=self.colors["bg_medium"],
                bd=1,
                relief=tk.SOLID,
                padx=5,
                pady=5,
            )
            item_frame.grid(row=row, column=col, padx=10, pady=10, sticky="n")

            thumb = self._create_thumbnail(full_path, thumb_width, thumb_height)
            if thumb is not None:
                thumb_label = tk.Label(
                    item_frame, image=thumb, bg=self.colors["bg_medium"]
                )
                thumb_label.pack()
                # Referansı sakla
                self.thumbnails[full_path] = thumb
            else:
                thumb_label = tk.Label(
                    item_frame,
                    text="Önizleme yok",
                    font=("Segoe UI", 10),
                    bg=self.colors["bg_medium"],
                    fg=self.colors["text"],
                    width=thumb_width // 10,
                    height=thumb_height // 20,
                )
                thumb_label.pack()

            name_label = tk.Label(
                item_frame,
                text=filename,
                font=("Segoe UI", 9),
                bg=self.colors["bg_medium"],
                fg=self.colors["text"],
                wraplength=thumb_width,
            )
            name_label.pack(pady=(5, 0))

            # Çift tıklama ile videoyu aç
            for widget in (item_frame, thumb_label, name_label):
                widget.bind(
                    "<Double-Button-1>",
                    lambda e, p=full_path: self.open_video(p),
                )

    def _create_thumbnail(self, video_path, width, height):
        """Videonun ilk karesinden küçük bir önizleme resmi üret."""
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((width, height))
            photo = ImageTk.PhotoImage(img)
            return photo
        except Exception:
            return None

    def open_video(self, video_path):
        """Seçilen videoyu Video panelinde açmak için callback'i çağır."""
        if not callable(self.open_video_callback):
            messagebox.showerror(
                "Hata",
                "Video açma işlevi tanımlı değil.",
            )
            return
        self.open_video_callback(video_path)

