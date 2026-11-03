import tkinter as tk

from core.database import init_db
from core.logger import get_logger, setup_logging
from core.paths import ensure_dirs
from page.main_container.video import MainVideoContainer
from page.video_container.video import VideoContainer
from page.grafik.main import GrafikContainer
from page.files_container import FilesContainer
from page.settings.main import SettingsContainer
from page.ai_train.main import AITrainContainer

class VideoPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Proje Arayüzü — V9")
        self._maximize_window()
        
        # Renk paleti
        self.colors = {
            'bg_dark': '#1e1e1e',
            'bg_medium': '#2d2d30',
            'bg_light': '#3e3e42',
            'accent': '#667eea',
            'accent_hover': '#764ba2',
            'text': '#e0e0e0'
        }
        
        # Tüm panel container'larını sakla (gizle/göster için)
        self.panel_containers = {}
        self.current_panel_name = None
        
        self.setup_ui()
        
    def _maximize_window(self):
        """Pencereyi büyüt (Windows / Linux / macOS)."""
        try:
            self.root.state('zoomed')              # Windows
        except tk.TclError:
            try:
                self.root.attributes('-zoomed', True)   # Linux
            except tk.TclError:
                w, h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                self.root.geometry(f"{w}x{h}+0+0")      # macOS / yedek

    def setup_ui(self):
        """Ana UI yapısını oluştur"""
        # Ana container
        self.root.configure(bg=self.colors['bg_dark'])
        
        # Üst Menü Bar
        self.create_top_menu()
        
        # Alt container (Sol panel + Sağ panel)
        self.main_container = tk.Frame(self.root, bg=self.colors['bg_dark'])
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sol Panel (%7 genişlik)
        self.create_left_panel()
        
        # Sağ Panel (Video alanı)
        self.create_right_panel()
        
    def create_top_menu(self):
        """Üst menü bar oluştur"""
        menu_frame = tk.Frame(self.root, bg=self.colors['accent'], height=60)
        menu_frame.pack(fill=tk.X, side=tk.TOP)
        menu_frame.pack_propagate(False)
        
        # Logo ve başlık
        title_label = tk.Label(
            menu_frame, 
            text="🐍 Python Görüntü İşleme Proje Aracı", 
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['accent'],
            fg='white',
            padx=20
        )
        title_label.pack(side=tk.LEFT, pady=15)
        
        # Menü butonları
        menu_items = ['Dosya', 'Grafik', 'Ayarlar']
        for item in menu_items:
            btn = tk.Button(
                menu_frame,
                text=item,
                font=('Segoe UI', 10),
                bg=self.colors['accent'],
                fg='white',
                relief=tk.FLAT,
                padx=15,
                pady=5,
                cursor='hand2',
                command=lambda i=item: self.select_top_menu(i)
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.add_hover_effect(btn, self.colors['accent'], self.colors['accent_hover'])
            
    def create_left_panel(self):
        """Sol navigasyon panelini oluştur"""
        # Sol panel frame - %7 genişlik için
        self.left_panel = tk.Frame(
            self.main_container, 
            bg=self.colors['bg_medium'],
            width=80
        )
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)
        
        # Panel ikonları ve isimleri
        panel_items = [
            ('🏠', 'Ana Sayfa'),
            ('🎬', 'Video'),
            ('⚙️', 'Ayarlar'),
            ('📁', 'Dosyalar'),
            ('📊', 'Grafik'),
            ('🧪', 'AI Eğitimi'),
            ('🔔', 'Bildirim')
        ]
        
        self.panel_buttons = []
        for icon, name in panel_items:
            btn_frame = tk.Frame(self.left_panel, bg=self.colors['bg_medium'])
            btn_frame.pack(pady=10, padx=10)
            
            btn = tk.Button(
                btn_frame,
                text=icon,
                font=('Segoe UI', 20),
                bg=self.colors['bg_light'],
                fg=self.colors['text'],
                relief=tk.FLAT,
                width=3,
                height=2,
                cursor='hand2',
                command=lambda n=name: self.select_panel(n)
            )
            btn.pack()
            self.panel_buttons.append((btn, name))
            
            # Hover efekti
            self.add_hover_effect(btn, self.colors['bg_light'], self.colors['accent'])
            
            # Tooltip
            self.create_tooltip(btn, name)
        
        # İlk butonu aktif yap
        self.panel_buttons[0][0].configure(bg=self.colors['accent'])
        
    def create_right_panel(self):
        """Sağ video panelini oluştur"""
        self.right_panel = tk.Frame(self.main_container, bg=self.colors['bg_dark'])
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Tüm paneller için container'ları oluştur (başlangıçta gizli)
        self.initialize_all_panels()
        
        # İlk olarak Ana Sayfa container'ını göster
        self.select_panel('Ana Sayfa')
        
    def add_hover_effect(self, widget, normal_color, hover_color):
        """Butonlara hover efekti ekle"""
        widget.bind('<Enter>', lambda e: widget.configure(bg=hover_color))
        widget.bind('<Leave>', lambda e: widget.configure(bg=normal_color))
        
    def create_tooltip(self, widget, text):
        """Widget için tooltip oluştur"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                tooltip,
                text=text,
                font=('Segoe UI', 9),
                bg=self.colors['bg_light'],
                fg='white',
                padx=8,
                pady=4,
                relief=tk.SOLID,
                borderwidth=1
            )
            label.pack()
            
            widget.tooltip = tooltip
            
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
                
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)
        
    def initialize_all_panels(self):
        """Tüm paneller için container'ları oluştur (başlangıçta gizli)"""
        # Ana Sayfa
        main_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
        main_container = MainVideoContainer(main_frame, self.colors)
        self.panel_containers['Ana Sayfa'] = {
            'frame': main_frame,
            'container': main_container
        }
        main_frame.pack_forget()  # Başlangıçta gizli
        
        # Video
        video_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
        video_container = VideoContainer(video_frame, self.colors)
        self.panel_containers['Video'] = {
            'frame': video_frame,
            'container': video_container
        }
        video_frame.pack_forget()  # Başlangıçta gizli
        
        # Grafik paneli
        grafik_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
        grafik_container = GrafikContainer(grafik_frame, self.colors)
        self.panel_containers['Grafik'] = {
            'frame': grafik_frame,
            'container': grafik_container
        }
        grafik_frame.pack_forget()  # Başlangıçta gizli

        # Dosyalar paneli (kayıtlı videolar)
        files_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])

        def open_video_in_panel(video_path):
            # Önce Video paneline geç, sonra seçilen videoyu yükle
            self.select_panel('Video')
            container = self.panel_containers.get('Video', {}).get('container')
            if container and hasattr(container, 'load_video_from_path'):
                container.load_video_from_path(video_path)

        files_container = FilesContainer(files_frame, self.colors, open_video_in_panel)
        self.panel_containers['Dosyalar'] = {
            'frame': files_frame,
            'container': files_container
        }
        files_frame.pack_forget()  # Başlangıçta gizli

        # --- YENİ: Ayarlar paneli ---
        settings_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
        settings_container = SettingsContainer(
            settings_frame,
            self.colors,
            on_model_applied=self._on_model_applied,
        )
        self.panel_containers['Ayarlar'] = {
            'frame': settings_frame,
            'container': settings_container
        }
        settings_frame.pack_forget()  # Başlangıçta gizli
        # ----------------------------

        # --- YENİ: AI Train / AI Eğitimi paneli ---
        ai_train_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
        ai_train_container = AITrainContainer(ai_train_frame, self.colors)
        self.panel_containers['AI Eğitimi'] = {
            'frame': ai_train_frame,
            'container': ai_train_container
        }
        ai_train_frame.pack_forget()  # Başlangıçta gizli
        # -----------------------------------------

        # Diğer paneller için placeholder container'lar
        other_panels = ['Bildirim']  # 'Ayarlar' artık buradan çıktı
        for panel_name in other_panels:
            panel_frame = tk.Frame(self.right_panel, bg=self.colors['bg_dark'])
            placeholder = tk.Label(
                panel_frame,
                text=f"{panel_name} Paneli\n\nBu panel yakında eklenecek",
                font=('Segoe UI', 18),
                bg=self.colors['bg_dark'],
                fg=self.colors['text']
            )
            placeholder.pack(expand=True)
            self.panel_containers[panel_name] = {
                'frame': panel_frame,
                'container': None
            }
            panel_frame.pack_forget()  # Başlangıçta gizli
    
    def _on_model_applied(self):
        """Ayarlar > Modeli Uygula — ana sayfadaki YOLO modelini güncelle."""
        container = self.panel_containers.get('Ana Sayfa', {}).get('container')
        if container and hasattr(container, 'reload_model_from_settings'):
            container.reload_model_from_settings()

    def select_panel(self, panel_name):
        """Panel seçimi yap - gizle/göster sistemi"""
        # Tüm butonları normale çevir
        for btn, name in self.panel_buttons:
            btn.configure(bg=self.colors['bg_light'])
        
        # Seçili butonu vurgula
        for btn, name in self.panel_buttons:
            if name == panel_name:
                btn.configure(bg=self.colors['accent'])
                break
        
        # Mevcut paneli gizle
        if self.current_panel_name and self.current_panel_name in self.panel_containers:
            panel_data = self.panel_containers[self.current_panel_name]
            panel_data['frame'].pack_forget()
        
        # Yeni paneli göster
        if panel_name in self.panel_containers:
            panel_data = self.panel_containers[panel_name]
            panel_data['frame'].pack(fill=tk.BOTH, expand=True)
        
        self.current_panel_name = panel_name
    
    def select_top_menu(self, menu_name):
        """Üst menüden panel seçimi"""
        # Menü isimlerini panel isimlerine map et
        menu_to_panel = {
            'Dosya': 'Dosyalar',
            'Grafik': 'Grafik',
            'Ayarlar': 'Ayarlar'  # Üst menü Ayarlar → Ayarlar paneli
        }
        
        panel_name = menu_to_panel.get(menu_name)
        if panel_name:
            self.select_panel(panel_name)
        
    def on_closing(self):
        """Uygulama kapatılırken"""
        # Tüm container'ları temizle
        for panel_name, panel_data in self.panel_containers.items():
            if panel_data['container'] and hasattr(panel_data['container'], 'cleanup'):
                try:
                    panel_data['container'].cleanup()
                except Exception:
                    log.exception("'%s' paneli temizlenirken hata", panel_name)
        self.root.destroy()


log = get_logger("main")


def main():
    ensure_dirs()
    setup_logging()
    init_db()          # tablolar yoksa oluşturulur; eski (V8) veritabanı olduğu gibi kullanılır
    log.info("Uygulama başlatılıyor")
    root = tk.Tk()
    app = VideoPlayerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()