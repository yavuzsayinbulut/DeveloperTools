# KeepAwake

Dock'ta gorunmeyen, menubar'da yasayan kucuk bir macOS yardimci uygulamasi.

Ne yapar:
- `caffeinate -dims` calistirarak ekranin ve sistemin uykuya gecmesini engeller.
- Acilista hem keep-awake hem de mouse hareketi otomatik olarak aktif olur.
- Menubar ikonundan tek tikla acilip kapatilir.
- Menudeki ek secenekle fare imlecini her 10 saniyede bir hafifce saga-sola kaydirir.

Ne yapmaz:
- Teams, Slack veya benzeri uygulamalarda yapay aktivite uretmez.
- Klavye girdisi veya editor otomasyonu yapmaz.

## Build

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/keep-awake-menubar
./Scripts/build-app.sh
open dist/KeepAwake.app
```

## Kullanim

- Menubar'daki ikonun uzerine tikla.
- `Keep Screen Awake` secenegi isaretliyse aktif demektir.
- `Keep Mouse Moving` secenegi isaretliyse fare hareketi aciktir.
- `Stop Mouse Movement` diyerek bunu menubardan kapatabilirsin.
- Kapatmak icin ayni secenegi tekrar tikla ya da `Quit` ile cik.

## Tools Hub

- `tools-hub` bu klasoru otomatik kesfeder.
- Kart uzerinden `Baslat` dediginde uygulama acilir.
- `Durdur` dediginde uygulama nazikce kapanir.
