# Görüntü İşleme V9

Video üzerinde araç tespiti (YOLO11), takip ve **alan bazlı geçiş sayımı**.
V8'in üzerine kuruldu; V8 veritabanları olduğu gibi açılır (veri kaybı yok).

## Kurulum ve çalıştırma

```bash
pip install -r requirements.txt
python main.py
```

1. **Ayarlar > Model Seçimi**: `dosyalar/` altındaki `best.pt` (veya `.onnx`, `.engine`, OpenVINO) modelini seçip *Modeli Uygula*.
2. **Ana Sayfa**: *Dosya Seç* → *➕ Ekle* ile alanları çiz (sol tık nokta, *✓ Tamamla*) → *▶️ Oynat*.
3. Alanları **💾 Alanları Kaydet** ile JSON'a kaydedip sonraki videoda **📂 Alanları Yükle** ile geri getirebilirsin.
4. *🛑 Bitir* (veya video sonu): sayımlar veritabanına yazılır; **Grafik** sayfasından görülür.

## V8 → V9: ne değişti?

| # | Madde | V9'da |
|---|-------|-------|
| 1 | UI güncellemeleri ana thread'de | İşçi thread'i Tkinter'e hiç dokunmaz; kareler kuyruğa konur, ana thread `after(15ms)` ile okur (`core/player.py`, `video.py`). Video artık kendi FPS'ine göre oynar (sabit `sleep(0.033)` yok). |
| 2 | Eşikler tek yerde + **alan bazlı** sayım + sınıf bazlı sayım | `core/config.py` (tek güven eşiği), `core/zones.py` (alan bazlı), sınıf bazlı sayım DB'ye de yazılır. Çizgi sayımı **yok** — kasıtlı. |
| 3 | `.pyc`, `database.db` repodan çıkar, `requirements.txt` | `.gitignore` güncellendi; `requirements.txt` eklendi. |
| 4 | `supervision` ile sayım | `sv.PolygonZone`, `sv.Detections`, annotator'lar. Doğruluk için `tools/count_accuracy.py`. |
| 5 | BoT-SORT + ONNX/TensorRT, FPS ölçümü | Ayarlar'dan izleyici seçimi; model sekmesinden dışa aktarma; `tools/benchmark.py`. |
| 6 | `video.py`'yi parçala | 1053 → 566 satır (yalnızca arayüz); mantık `core/` ve `area_editor.py`, `info_panel.py`, `dialogs.py` içinde. |

Ek düzeltmeler: tüm yollar çalışma dizininden bağımsız (`core/paths.py`); ortak veritabanı katmanı ve şema sürümü; hatalar `except: pass` ile yutulmuyor, `dosyalar/logs/app.log`'a yazılıyor; Yapılandırma sekmesi artık gerçekten bağlı (V8'de yalnızca önizlemeydi); alan seçimi ID yazdırmak yerine listeden; alan isimleri benzersiz; Türkçe karakterli alan isimleri videoda doğru çiziliyor; ölü kod temizlendi.

## Alan bazlı sayım nasıl çalışır?

Her takip ID'si için **son onaylı alan** hatırlanır. Aracın *ayak noktası* (kutunun alt-orta noktası) başka bir alana girip `Alan Onay Karesi` kadar video karesi orada kalırsa **önceki alan → yeni alan** geçişi sayılır. Alanlar arasındaki boşlukta durum korunur. Böylece:

- video kare atlasa veya tespit birkaç kare kaybolsa geçiş kaçmaz (çizgi sayımı iki ardışık karede çizginin iki yanını görmek zorundadır),
- kutu iki alanın sınırında titrese çift sayım olmaz (onay süresi),
- işlenen iki kare arasında dar bir alanı **tamamen atlayan** araç da o alandan geçmiş sayılır ("taranan yol", `MAX_BRIDGE` = 90 video karesi),
- ayrıca her alana giren **benzersiz araç** sayısı tutulur.

### Bilinen sınırlar (dürüst liste)

- Takipçi (ByteTrack/BoT-SORT) bir aracın ID'sini kaybedip yeni ID verirse, yeni ID "ilk girişi" olarak başlar; o araçın geçişi sayılamaz. Alan bazlı yaklaşım bunu azaltır ama ortadan kaldırmaz.
- Bir araç hiçbir işlenen karede ilk alanın içinde (ve ondan önce de) görülmediyse, o geçiş gözlemlenmemiş demektir; hiçbir alan yöntemi onu sayamaz. Alanları araçların *mutlaka görüneceği* kadar geniş çiz.
- Sayım doğruluğu modelin tespit kalitesine bağlıdır; `tools/count_accuracy.py` ile kendi videonda ölç.

## Araçlar (arayüzsüz)

```bash
# Elle sayım (truth.json) ile karşılaştır; --skip N: her N. kareyi işle (kare atlama simülasyonu)
python tools/count_accuracy.py --video v.mp4 --model dosyalar/Model/x/weights/best.pt \
       --areas dosyalar/alanlar/sablon.json --truth truth.json --skip 1 --skip 5 --skip 10

# FPS: model formatları ve izleyiciler
python tools/benchmark.py --video v.mp4 --models a/best.pt a/best.onnx --tracker bytetrack --tracker botsort

# Dönüştür
python tools/export_model.py a/best.pt --format onnx      # | openvino | engine
```

`truth.json` örneği: `{"Giriş->Çıkış": 12, "Çıkış->Giriş": 3}`

> **Hız notu:** ONNX/OpenVINO/TensorRT kazancı donanıma bağlıdır. V9 geliştirme testinde tek çekirdekli bir CPU'da ONNX, `.pt`'den *yavaş* çıktı (7,4 vs 11,0 FPS). TensorRT (NVIDIA GPU) ve OpenVINO (Intel) bu ortamda denenmedi. Karar vermeden önce `benchmark.py` ile ölç.

## Testler

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # ZoneCounter, ayarlar, alan JSON, veritabanı (YOLO gerekmez)
```

## Yapı

```
main.py                    uygulama kabuğu
core/                      arayüzden bağımsız çekirdek (tkinter import etmez)
  paths · logger · database · config · detection · zones · annotate · player · areas · text · exporter
page/
  main_container/          Ana Sayfa: video.py (UI) · area_editor · info_panel · dialogs · save
  settings/                Model Seçimi (+dışa aktarma) · Yapılandırma
  grafik · files_container · video_container · ai_train
tools/                     count_accuracy · benchmark · export_model
tests/
dosyalar/                  veritabanı, modeller, videolar, alan şablonları, loglar (repoya girmez)
```

Veri klasörünü taşımak için `GORUNTU_DATA_DIR` ortam değişkenini ayarla.
