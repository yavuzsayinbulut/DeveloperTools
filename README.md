# DeveloperTools

macOS uzerinde gunluk akisi hizlandiran, lokal calisan kucuk arac kolleksiyonu.
Hepsi Python ile yazildi, hicbiri internete veri gondermez, veriler tamamen
lokalde tutulur.

## Neler Var

### Ana Projeler

| Proje | Tip | Ne ise yarar |
|------|-----|--------------|
| [clipboard-keeper](#clipboard-keeper) | PySide6 menubar | macOS pano gecmisi: pinleme, sekme, TXT export, bildirim, show-all |
| [fordeveloper](#fordeveloper) | Flask web | Deployment, task, reminder, daily-note, markdown arama ve workspace paneli |

### Yardimci Arac

| Arac | Tip | Ne ise yarar |
|------|-----|--------------|
| [tools-hub](#tools-hub) | PySide6 desktop | Bu repodaki araclari tek pencereden baslat, durdur, URL ac, log incele, PID/port kill yap |
| [display-agent](#display-agent) | Swift menubar | Menubar'da sessiz calisan display session ve input activity yardimcisi |
| [for-developer-radar](#for-developer-radar) | Flask dashboard | Finance workspace icin Git, Jira/TCO ve deployment notlarini eslestiren delivery radar |
| [window-pinner-menubar](#window-pinner-menubar) | Swift menubar | Aktif macOS penceresini hotkey ile hep ustte tut, sonra normal gibi tasi ve yeniden boyutlandir |

```
Tools/
├── start.command            # tools-hub launcher'i acar
├── stop.command
├── tools-hub/               # arac yoneticisi
├── display-agent/           # display session yardimcisi
├── for-developer-radar/     # Finance delivery radar dashboard
├── window-pinner-menubar/   # aktif pencereyi ustte tutan macOS yardimci araci
├── clipboard-keeper/        # menubar clipboard manager
└── fordeveloper/            # workspace dashboard (Flask)
```

---

## Hizli Baslangic

```bash
git clone https://github.com/yavuzsayinbulut/DeveloperTools.git
cd DeveloperTools

# Tum araclari tek pencereden yonet
./start.command
```

Ilk acilista her uygulama icin venv otomatik kurulur (PySide6, Flask, vb.
indirilir). Bu bir kerelik islemdir; sonraki acilislar hizlidir.

> **Gereksinim:** Python 3.9+ (macOS Command Line Tools veya `brew install python`)

---

## tools-hub

Tools klasorunu tarayan, alt klasorlerdeki `start.command` / `app.py` /
`main.py` / `package.json`'lari uygulama olarak gosteren masaustu launcher.

**Yapabildikleri:**

- Alt klasorleri otomatik kesfeder
- Start / Stop
- URL'i tarayicida ac (Flask gibi web uygulamalar icin)
- Klasoru / log dosyasini Finder'da ac
- PID kill ve port kill araclari
- URL override edip kaydeder
- Surec saglik durumu

**Calistirma:**

```bash
./start.command
```

Durum dosyasi: `~/Library/Application Support/ToolsHub/state.json`

---

## display-agent

Menubar'da calisan, Dock'ta gorunmeyen kucuk bir display session yardimcisi.

**Ozellikler:**

- Display session durumunu tek menubar ikonundan acip kapatir
- Input activity'yi `Slow / Normal / Fast` hizlarinda yonetir
- macOS'in izin verdigi kapali kapak kosullarinda normal akisi surdurur

**Calistirma:**

```bash
cd display-agent
./start.command
```

---

## for-developer-radar

Finance workspace icindeki local git gecmisi, deployment notlari ve Jira/TCO
izlerini tek ekranda eslestiren Flask dashboard.

**Calistirma:**

```bash
cd for-developer-radar
./fdev start
```

Tarayici: `http://127.0.0.1:5556`

---

## window-pinner-menubar

Menubar'da calisan, aktif macOS penceresini hotkey ile pinleyen kucuk bir arac.

**Ozellikler:**

- `Control + Option + Command + P` ile aktif pencereyi pinler
- `Control + Option + Command + U` ile pin'i kaldirir
- Pinlenen pencereyi normal pencere gibi tasiyip yeniden boyutlandirabilirsin
- Cikis yaparken pencere seviyesini eski haline geri alir
- `Accessibility` izni ister

**Calistirma:**

```bash
cd window-pinner-menubar
./start.command
```

---

## clipboard-keeper

macOS menubar'inda yasayan, pano gecmisini lokalde tutan minimal manager.

**Ozellikler:**

- Kopyalananlari yerelde JSON olarak saklar
- Pinli kayitlar her zaman ustte
- Varsayilan son 10 kayit; "Show all" ile ayarlardan verilen gun kadar gecmisi
  kaydirarak gosterir
- Uzun icerikler icin hover tooltip ile tam goruntuleme
- Birden fazla sekmede acma + duzenleme
- TXT export (bolumlu)
- "Always on top" secenegi
- macOS bildirimi yeni kopya geldiginde
- Acilista otomatik baslama (LaunchAgent)
- Dock ikonu opsiyonel gizleme (`pyobjc` ile)

**Calistirma:**

```bash
cd clipboard-keeper
./start.command
```

Veriler: `~/Library/Application Support/ClipboardKeeperPro/`

---

## fordeveloper

Lokal Flask sunucusu olarak calisan, secilen klasor altindaki `.md`
dosyalarini parse edip "developer dashboard" haline getiren bir surec
asistani.

**Sayfalar:**

- **Dashboard** — sprint ozet, deployment sayaci, gunun reminder'lari, son aktivite
- **Deployments** — `DEPLOYMENT_LOG.md` parse edilip kart goruntusunde
- **Repo Stats / Team Pulse** — workspace altindaki git repolarinin commit/MR aktivitesi
- **Tasks Board** — drag & drop kanban (TODO / IN_PROGRESS / IN_REVIEW / DONE / ARCHIVED)
- **Reminders** — bir kez / her gun / hafta ici / sali-persembe / haftalik tekrarli
- **Daily Notes** — gunluk not defteri, markdown destekli, Cmd+S
- **Search & Trace** — tum md'lerde full-text + `TCO-XXXX` ile JIRA timeline
- **Docs Browser** — kategorize md gorunumu (rehber / deployment / mimari / vb.)
- **Settings** — workspace klasoru, PIN aciklama, animasyon yogunlugu, bildirim saatleri

**Yapilandirilabilir noktalar (Settings ekraninda):**

- Calisma alani (workspace klasoru) — istedigin klasoru gosterirsen md/git/deployment hep oradan tarar
- Acilis PIN'i — toggle ile acilip kapanir, kod yerinde durur
- Animasyon yogunlugu — `Yuksek / Orta / Dusuk / Kapali`, her ekran icin ayri kapatma listesi
- Sayfa gecis efekti olasiligi
- Bildirim saatleri, tema, port

**Calistirma:**

```bash
cd fordeveloper

# Kalici servis (login'de otomatik baslar — ~/Desktop disindaysa)
./fdev agent-install

# Veya nohup daemon (her durumda calisir)
./fdev start

# Foreground debug
./fdev run

./fdev status   # durum
./fdev stop
./fdev log      # canli log
```

Tarayicida ac: **http://127.0.0.1:5555**

Veriler: `fordeveloper/data/` (SQLite + log) — `.gitignore`'da, repoya gitmez.

> macOS TCC nedeniyle proje `~/Desktop` altindaysa LaunchAgent calismaz; bu
> durumda `./fdev start` (nohup daemon) ile baslat.

---

## Mimari Kararlar

| Konu | Secim | Sebep |
|------|-------|-------|
| Dil | Python 3 | Hepsi tek runtime, kolay debug |
| Desktop UI | PySide6 (Qt) | macOS uzerinde native his + menubar destegi |
| Web UI | Flask + Vanilla JS | Framework yok, hizli yuklenir |
| Veritabani | SQLite | Tek dosya, sifreleme + replikasyon istemiyoruz |
| Veri akisi | Lokal | Hicbir arac internete veri gondermez |
| Servis yonetimi | launchd / nohup hibrit | Desktop TCC kisitlamasini bypass eder |

---

## Lisans

Kisisel kullanim icin yazilmistir. Kendine gore uyarlamak istersen serbest.
