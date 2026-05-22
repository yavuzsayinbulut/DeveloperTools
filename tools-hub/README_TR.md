# Tools Hub

Tools klasoru icindeki uygulamalari listeleyen ve yoneten masaustu launcher.

## Ozellikler

- Uygulama klasorlerini otomatik tarar
- Start / Stop / URL Ac / Klasor Ac / Log Ac
- Uygulama gizleme, gizlenenleri tekrar gosterme ve arka planda baslatma
- PID Kill ve Port Kill araclari
- URL override saklar
- PID ve erisim durumu takibi yapar
- Log onizlemesi sunar

## Baslatma

Root klasorden:

```bash
./start.command
```

## Uygulama Tespiti

Asagidaki yapilardan birini bulursa uygulama olarak sayar:

- `start.command`
- `main.py`
- `app.py`
- `package.json`

Gizlenen uygulamalar silinmez veya durdurulmaz. Sadece ana liste ve menubar
menusunden saklanir; `Gizlenenleri Yönet` ile tekrar gorunur yapilabilir.

## Durum Dosyasi

Launcher durumu:

- `~/Library/Application Support/ToolsHub/state.json`
