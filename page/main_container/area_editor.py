"""
page/main_container/area_editor.py
──────────────────────────────────
Alan (poligon) çizme / düzenleme / silme / kaydetme mantığı.

video.py'den ayrıldı: bu sınıf Tk widget'ı çizmez; yalnızca durumu yönetir
(`drawing_mode`, `current_polygon`) ve alan listesini ZoneCounter'a işler.
Canvas'a çizim ve tıklama koordinatı dönüşümü video.py tarafından verilir.

V8'den farklar:
  * Alan seçimi ID yazdırmak yerine liste penceresiyle yapılır.
  * Alan isimleri benzersiz olmak zorundadır (sayımlar isimle tutulur).
  * Alanlar JSON olarak kaydedilip yüklenebilir (uygulama kapanınca kaybolmaz).
  * Son noktayı geri alma eklendi.
"""

from tkinter import filedialog, messagebox, simpledialog

from core.areas import load_areas, save_areas
from core.logger import get_logger
from core.paths import AREAS_DIR
from core.zones import ZoneCounter
from page.main_container.dialogs import AreaPickerDialog

log = get_logger("areas")


class AreaEditor:
    def __init__(self, root, colors, counter: ZoneCounter, *, get_frame_size,
                 notify, on_changed, redraw_overlay):
        """
        get_frame_size : () -> (w, h)   açık videonun çözünürlüğü (yoksa (0, 0))
        notify         : (mesaj) -> None
        on_changed     : () -> None     alan listesi değişti (görüntü + panel yenilensin)
        redraw_overlay : () -> None     çizim modundaki poligon yeniden çizilsin
        """
        self.root = root
        self.colors = colors
        self.counter = counter
        self.get_frame_size = get_frame_size
        self.notify = notify
        self.on_changed = on_changed
        self.redraw_overlay = redraw_overlay

        self.drawing_mode = False
        self.current_polygon: list[tuple[int, int]] = []
        self.editing_area_id: int | None = None

    # ── yardımcılar ────────────────────────────────────────────────
    @property
    def areas(self) -> list[dict]:
        return self.counter.areas

    def _has_video(self) -> bool:
        w, h = self.get_frame_size()
        return w > 0 and h > 0

    def _name_taken(self, name: str, ignore_id: int | None) -> bool:
        return any(a["name"] == name and a["id"] != ignore_id for a in self.areas)

    def _pick(self, title: str, action: str) -> int | None:
        areas = self.areas
        if not areas:
            messagebox.showwarning("Uyarı", "Henüz alan yok!")
            return None
        return AreaPickerDialog(self.root, self.colors, areas, title, action).result

    def reset_drawing(self) -> None:
        self.drawing_mode = False
        self.current_polygon = []
        self.editing_area_id = None

    # ── canvas olayları (koordinatlar video pikseli olarak gelir) ──
    def on_click(self, x: int, y: int) -> None:
        if not self.drawing_mode:
            return
        self.current_polygon.append((int(x), int(y)))
        self.redraw_overlay()

    def on_right_click(self) -> None:
        if self.drawing_mode:
            self.current_polygon = []
            self.redraw_overlay()

    def undo_point(self) -> None:
        if self.drawing_mode and self.current_polygon:
            self.current_polygon.pop()
            self.redraw_overlay()

    # ── komutlar ───────────────────────────────────────────────────
    def add_area(self) -> None:
        if not self._has_video():
            messagebox.showwarning("Uyarı", "Önce bir video yükleyin!")
            return
        self.drawing_mode = True
        self.current_polygon = []
        self.editing_area_id = None
        self.notify("Çizim modu: sol tık = nokta, sağ tık = sıfırla, ✓ Tamamla = bitir")

    def edit_area(self) -> None:
        area_id = self._pick("Düzenlenecek alanı seçin", "Düzenle")
        if area_id is None:
            return
        for a in self.areas:
            if a["id"] == area_id:
                self.editing_area_id = area_id
                self.current_polygon = list(a["points"])
                self.drawing_mode = True
                self.redraw_overlay()
                self.on_changed()
                self.notify(f"Alan düzenleniyor: {a['name']}  (sağ tık = baştan çiz)")
                return

    def delete_area(self) -> None:
        area_id = self._pick("Silinecek alanı seçin", "Sil")
        if area_id is None:
            return
        self.counter.set_areas([a for a in self.areas if a["id"] != area_id])
        self.on_changed()
        self.notify("Alan silindi")

    def finish_area(self) -> None:
        if not self.drawing_mode:
            messagebox.showwarning("Uyarı", "Önce çizim modunu başlatın!")
            return
        if len(self.current_polygon) < 3:
            messagebox.showwarning("Uyarı", "En az 3 nokta gerekli!")
            return

        areas = self.areas
        current_name = next((a["name"] for a in areas if a["id"] == self.editing_area_id), "")
        name = simpledialog.askstring("Alan İsmi", "Alan ismini girin:",
                                      initialvalue=current_name, parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        if self._name_taken(name, self.editing_area_id):
            messagebox.showwarning("Uyarı", f"'{name}' adında bir alan zaten var.\n"
                                            "Sayımlar alan adıyla tutulduğu için isimler benzersiz olmalı.")
            return

        if self.editing_area_id is not None:
            for a in areas:
                if a["id"] == self.editing_area_id:
                    a["points"], a["name"] = list(self.current_polygon), name
        else:
            new_id = max((a["id"] for a in areas), default=0) + 1
            areas.append({"id": new_id, "name": name, "points": list(self.current_polygon)})

        self.counter.set_areas(areas)
        self.reset_drawing()
        self.on_changed()
        self.notify(f"Alan kaydedildi: {name}")

    # ── dosya ──────────────────────────────────────────────────────
    def save_to_file(self) -> None:
        areas = self.areas
        if not areas:
            messagebox.showwarning("Uyarı", "Kaydedilecek alan yok!")
            return
        AREAS_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            title="Alanları Kaydet", initialdir=str(AREAS_DIR), defaultextension=".json",
            filetypes=[("Alan şablonu", "*.json")], parent=self.root)
        if not path:
            return
        try:
            save_areas(path, areas, self.get_frame_size())
            self.notify(f"{len(areas)} alan kaydedildi")
        except OSError as e:
            log.exception("Alanlar kaydedilemedi")
            messagebox.showerror("Hata", f"Kaydedilemedi:\n{e}")

    def load_from_file(self) -> None:
        if not self._has_video():
            messagebox.showwarning("Uyarı", "Önce bir video yükleyin!")
            return
        AREAS_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Alanları Yükle", initialdir=str(AREAS_DIR),
            filetypes=[("Alan şablonu", "*.json")], parent=self.root)
        if not path:
            return
        try:
            areas = load_areas(path, self.get_frame_size())
        except (OSError, ValueError, KeyError) as e:
            log.exception("Alanlar yüklenemedi")
            messagebox.showerror("Hata", f"Dosya okunamadı:\n{e}")
            return
        self.apply_areas(areas)
        self.notify(f"{len(areas)} alan yüklendi")

    def apply_areas(self, areas: list[dict]) -> None:
        self.reset_drawing()
        self.counter.set_areas(areas)
        self.on_changed()

    def rescale(self, old_size, new_size) -> None:
        """Farklı çözünürlüklü yeni video açıldığında alanları ölçekle."""
        if not old_size[0] or not old_size[1] or old_size == new_size:
            return
        sx, sy = new_size[0] / old_size[0], new_size[1] / old_size[1]
        areas = self.areas
        for a in areas:
            a["points"] = [(int(round(x * sx)), int(round(y * sy))) for x, y in a["points"]]
        self.counter.set_areas(areas)
        self.notify("Video çözünürlüğü değişti; alanlar ölçeklendi")
