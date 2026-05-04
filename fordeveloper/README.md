# Yavuz Sayinbulut Development Notes Panel

Odeal gelistirme sureci icin kisisel dashboard ve hatirlatma sistemi. Deployment takibi, task yonetimi, dokuman tarama ve gunluk not tutma islerini tek bir yerden yonetir.

## Hizli Baslangic

```bash
cd /Users/yavuz.sayinbulut/Desktop/Projects/fordeveloper

# Ilk kurulum (bir kez)
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Calistir
./venv/bin/python app.py
```

Tarayicida ac: **http://127.0.0.1:5555**

## Sayfalar

### Dashboard (`/`)

Ana sayfa. Tek bakista gunun ozetini verir.

- **Deployment Sayaci** - Sonraki deployment gunune kac gun kaldigi. Deployment gunu ise uyari banner'i.
- **Sprint Overview** - Tasklarin status dagilimi (TODO / IN_PROGRESS / IN_REVIEW / DONE) bar chart.
- **Bugunun Hatirlatmalari** - Bugun icin zamanlanmis tum reminder'lar saat sirasinda.
- **Son Deploymentlar** - DEPLOYMENT_LOG.md'den son 5 kayit, JIRA ve MR linkleri tiklanabilir.
- **Aktif Tasklar** - TODO, IN_PROGRESS veya IN_REVIEW statusundeki tasklar.
- **Daily Note** - Bugunun notu yazildiysa onizleme, yazilmadiysa uyari.
- **Son Aktivite** - Son 10 islem (task olusturma, status degisikligi, reminder ekleme vb.)

Hizli islemler icin "+" butonlari ile task veya reminder eklenebilir.

### Deployments (`/deployments`)

`DEPLOYMENT_LOG.md` dosyasini otomatik parse eder ve kart gorunumunde sunar.

- Tarih bazli filtreleme
- Her kartta: task numarasi, JIRA linki, repo listesi, MR linkleri
- Test Branch Merge durumu renk kodlu badge (Yapildi=yesil, Yapilmadi=kirmizi, Teyit Bekliyor=sari)
- Ilgililer listesi
- "Bu task'in tum kayitlarini gor" linki ile Search & Trace sayfasina yonlendirme

**Deployment gunleri:** Sali ve Persembe

### Tasks Board (`/tasks`)

Kanban board ile task yonetimi. 5 kolon:

| Kolon | Anlami |
|-------|--------|
| TODO | Henuz baslanmamis |
| IN_PROGRESS | Uzerinde calisiliyor |
| IN_REVIEW | Review bekliyor |
| DONE | Tamamlandi |
| ARCHIVED | Arsivlendi |

**Ozellikler:**
- **Drag & drop** ile kartlari kolonlar arasinda tasiyarak status degistir
- Her kartta: TCO numarasi, kategori badge, oncelik gostergesi, JIRA/MR linkleri
- TCO numarasina tikla -> o task'in tum kayitlarini trace et
- Kart uzerinde duzenle/sil butonlari
- "Yeni Task" butonu ile modal form

**Kategoriler:** `backend`, `frontend`, `devops`, `hotfix`, `refactor`, `analysis`

**Oncelikler:** `low` (yesil), `medium` (sari), `high` (turuncu), `critical` (kirmizi, yanip soner)

### Reminders & Jobs (`/reminders`)

Hatirlatma ve zamanlanmis is yonetimi.

**Yeni hatirlatma eklerken:**
- Not metni
- Kategori: `genel`, `deployment`, `task`, `review`, `meeting`, `daily`
- Tarih ve saat
- Tekrar secenegi:
  - `Bir Kez` - sadece belirtilen zamanda
  - `Her Gun` - her gun ayni saatte
  - `Hafta Ici` - pazartesi-cuma
  - `Sali & Persembe` - deployment gunleri
  - `Haftalik` - her hafta ayni gun
- Oncelik
- Iliskili task (opsiyonel)

**Status yonetimi:**
- `Aktif` - zamanlanmis, bildirim bekliyor
- `Tamamlandi` - is yapildi
- `Iptal` - artik gerekli degil

Filtreleme: Aktif / Tamamlandi / Iptal / Tumu

### Daily Notes (`/daily-notes`)

Gunluk not defteri.

- Sol panelde gecmis notlarin listesi, bugun en ustte
- Sag panelde markdown destekli editor
- **Ctrl+S** (veya Cmd+S) ile hizli kaydet
- Onizleme modu ile markdown render
- Etiket ekle (virgul ile ayir)

Her sabah 09:30'da "Bugunun notunu yazmayi unutma" bildirimi gelir.

### Search & Trace (`/search`)

Iki modlu arama sistemi.

**Keyword Arama:**
- Tum `.md` dosyalarinda full-text arama
- Sonuclar kategorize edilir: Task, Deployment, Rehber, Dokuman, Proje, Mimari
- Her sonucta eslesme snippet'i ve dosya bilgisi
- Kategori filtresi ile daraltma

**JIRA Trace (TCO-XXXX):**
- Arama kutusuna `TCO-4320` gibi bir JIRA numarasi yazildiginda trace modu aktiflesir
- O task numarasinin gectigi TUM kayitlar kronolojik timeline gorunumunde:
  1. PLAN_AND_ANALYSIS
  2. DEVELOPMENT
  3. CODE_REVIEW
  4. MANUEL_TEST
  5. QA_TEST
  6. DEPLOYMENT_LOG kayitlari
  7. AGENTS-CHANGES notlari
- Her kayit tipine gore farkli renk ve ikon
- Kayitlara tiklanarak docs browser'da acilabilir

**Global arama kisayolu:** `Cmd+K`

### Docs Browser (`/docs`)

Projedeki tum `.md` dosyalarini goruntuler.

- Sol panelde dosya listesi, kategori renk kodlu noktalar ile
- Filtre alani ile dosya adina gore daraltma
- Sag panelde secili dosyanin markdown render'i:
  - Syntax highlighted kod bloklari
  - Tiklanabilir linkler (yeni sekmede acilir)
  - Otomatik icindekiler (heading'lerden)
  - TCO numaralari tiklanabilir tag olarak gosterilir

**Kategoriler:**
| Renk | Kategori | Ornekler |
|------|----------|----------|
| Mor | Rehber | AGENTS.md, PROMPTING.md |
| Sari | Degisiklik Kaydi | AGENTS-CHANGES.md |
| Kirmizi | Deployment | DEPLOYMENT_LOG.md |
| Yesil | Task | tasks/ altindaki dosyalar |
| Koyu Mor | Mimari | docs/architecture/ |
| Mavi | Dokuman | docs/ altindaki dosyalar |
| Gri | Template | TEMPLATE.md dosyalari |
| Cyan | Proje | README.md dosyalari |

### Settings (`/settings`)

- **Bildirim Saati** - Sabah bildirimleri icin saat:dakika
- **Deployment Hatirlatmasi** - Sali/Persembe bildirimi ac/kapa
- **Daily Note Hatirlatmasi** - Sabah notu bildirimi ac/kapa
- **Sabah Brifingi** - Gunluk ozet bildirimi ac/kapa
- **Tema** - Dark / Light
- **Md Index Yeniden Olustur** - Arama indexini sifirdan tara

## Background Job'lar

Uygulama arka planda su isleri otomatik yapar:

| Job | Zamanlama | Ne Yapar |
|-----|-----------|----------|
| Reminder Check | Her 1 dakika | Zamani gelen hatirlatmalar icin macOS bildirimi gonderir |
| Deployment Reminder | Sal/Per 09:00 | "Bugun deployment gunu" bildirimi + gunun kayitlari |
| Morning Briefing | Her gun 09:00 | Aktif task ve hatirlatma sayisi ozeti |
| Daily Note Reminder | Her gun 09:30 | "Notunu yazmayi unutma" hatirlatmasi |
| Md Reindex | Her 30 dakika | Yeni/degisen .md dosyalarini arama indexine ekler |

Bildirimler macOS Notification Center uzerinden gelir.

## Servis Yonetimi

```bash
# Durdur
launchctl unload ~/Library/LaunchAgents/com.odeal.fordeveloper.plist

# Baslat
launchctl load ~/Library/LaunchAgents/com.odeal.fordeveloper.plist

# Manuel calistir (debug icin)
cd /Users/yavuz.sayinbulut/Desktop/Projects/fordeveloper
./venv/bin/python app.py

# Log'lari gor
tail -f data/app.log
tail -f data/error.log
```

Login'de otomatik baslar. Crash ederse otomatik yeniden baslatilir (KeepAlive).

## LaunchAgent Kurulumu

LaunchAgent ilk kurulumda asagidaki komutla yuklenir:

```bash
cp com.odeal.fordeveloper.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.odeal.fordeveloper.plist
```

Kaldirmak icin:

```bash
launchctl unload ~/Library/LaunchAgents/com.odeal.fordeveloper.plist
rm ~/Library/LaunchAgents/com.odeal.fordeveloper.plist
```

## Kisayollar

| Kisayol | Islem |
|---------|-------|
| `Cmd+K` | Global arama kutusuna odaklan |
| `Cmd+S` | Daily note kaydet (daily notes sayfasinda) |
| `Escape` | Acik modal'i kapat |

## Teknik Detaylar

- **Port:** 5555
- **Backend:** Python Flask
- **Veritabani:** SQLite (`data/fordeveloper.db`)
- **Zamanlama:** APScheduler (background thread)
- **Markdown Render:** Python-Markdown + Pygments (syntax highlight)
- **Frontend:** Vanilla HTML/CSS/JS (framework yok)
- **Tema:** Dark/Light, CSS custom properties ile

## Dosya Yapisi

```
fordeveloper/
├── app.py                    # Flask uygulamasi ve route'lar
├── models.py                 # SQLAlchemy veri modelleri
├── parser.py                 # DEPLOYMENT_LOG.md parser
├── md_browser.py             # Md dosya tarama ve render
├── search_engine.py          # Full-text arama ve JIRA trace
├── notifier.py               # macOS bildirim gonderici
├── scheduler.py              # Background job zamanlayici
├── config.py                 # Yapilandirma ve sabitler
├── requirements.txt          # Python bagimliliklari
├── README.md                 # Bu dosya
├── com.odeal.fordeveloper.plist  # macOS LaunchAgent
├── data/
│   ├── fordeveloper.db       # SQLite veritabani
│   ├── app.log               # Uygulama log'u
│   └── error.log             # Hata log'u
├── templates/
│   ├── base.html             # Ortak layout (sidebar + topbar)
│   ├── dashboard.html        # Ana sayfa
│   ├── deployments.html      # Deployment log gorunumu
│   ├── tasks.html            # Kanban board
│   ├── reminders.html        # Hatirlatma yonetimi
│   ├── daily_notes.html      # Gunluk notlar
│   ├── search.html           # Arama ve JIRA trace
│   ├── docs.html             # Dokuman tarayici
│   └── settings.html         # Ayarlar
├── static/
│   ├── css/style.css         # Tum stiller (dark/light tema)
│   └── js/
│       ├── app.js            # Ortak: modal, toast, API, kisayollar
│       └── kanban.js         # Drag & drop board
└── venv/                     # Python sanal ortam
```

## API Referansi

Tum API'ler JSON ile calisir.

### Tasks
- `POST /api/tasks` - Yeni task olustur
- `PUT /api/tasks/<id>` - Task guncelle (status, oncelik, vb.)
- `DELETE /api/tasks/<id>` - Task sil
- `POST /api/tasks/reorder` - Kanban siralama ve status guncelle

### Reminders
- `POST /api/reminders` - Yeni hatirlatma
- `PUT /api/reminders/<id>` - Hatirlatma guncelle
- `DELETE /api/reminders/<id>` - Hatirlatma sil

### Daily Notes
- `POST /api/daily-notes` - Not kaydet/guncelle (tarih bazli upsert)

### Diger
- `GET /api/search?q=keyword` - JSON arama sonuclari
- `POST /api/index/rebuild` - Md dosya indexini yeniden olustur
- `POST /api/settings` - Ayarlari kaydet
