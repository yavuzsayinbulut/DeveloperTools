# Clipboard Keeper Pro

macOS icin yerel calisan, menubar simgeli bir clipboard manager.

## Ozellikler

- Kopyalanan verileri yerelde saklar
- Pinlenmis kayitlari ustte tutar
- Varsayilan olarak son 10 kaydi gosterir
- "Show all" ile ayarlardan verilen gun kadar gecmisi gosterir
- Uzun kayitlarda hover tooltip ile tam icerik gosterir
- Yeni kopyalarda macOS bildirimi gosterir
- Tek tek silme ve pinli kayitlar disindakileri toplu temizleme vardir
- Kayitlari sekmede acar, birden fazla sekme destekler
- TXT export ile bolumlu kayit alir
- Her zaman ustte kalma secenegi vardir
- Menubar ikonuyla arka planda calisir
- Acilista baslatma destegi vardir

## Calistirma

`clipboard-keeper` klasoru icinden:

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/clipboard-keeper
./start.command
```

Ilk calistirmada:

- Python virtualenv olusturulur
- Gerekli paketler kurulur
- Uygulama baslatilir

Not:

- Virtualenv root klasorde `Tools/.venv` altinda tutulur.

## Durdurma

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/clipboard-keeper
./stop.command
```

## Notlar

- Veriler `~/Library/Application Support/ClipboardKeeperPro/` altinda saklanir.
- Ayarlardan "Acilista baslat" acildiginda LaunchAgent yazilir.
- Dock ikonunu gizleme ozelligi `pyobjc` uzerinden calisir.
