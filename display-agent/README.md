# Display Agent

Dock'ta gorunmeyen, menubar'da yasayan kucuk bir macOS yardimci uygulamasi.

Ne yapar:
- `caffeinate -dims` calistirarak ekranin ve sistemin uykuya gecmesini engeller.
- Acilista hem display session hem de input activity otomatik olarak normal hizda aktif olur.
- Menubar ikonundan tek tikla acilip kapatilir.
- Menudeki ek secenekle fare imlecini secilen hizda ekranin rastgele uzak noktalarina tasir.

Ne yapmaz:
- Teams, Slack veya benzeri uygulamalarda yapay aktivite uretmez.
- Klavye girdisi veya editor otomasyonu yapmaz.
- MacBook kapagini harici ekran ve guc olmadan yazilimla zorla acik tutamaz.

## Build

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/display-agent
./Scripts/build-app.sh
open dist/DisplayAgent.app
```

## Kullanim

- Menubar'daki ikonun uzerine tikla.
- `Display Session` secenegi isaretliyse aktif demektir.
- `Input Activity` secenegi isaretliyse fare hareketi aciktir.
- `Stop Input Activity` diyerek bunu menubardan kapatabilirsin.
- `Activity Rate` alt menusunden `Slow`, `Normal` veya `Fast` secerek hareket sikligini degistirebilirsin.
- Kapatmak icin ayni secenegi tekrar tikla ya da `Quit` ile cik.

## Kapak Kapali Kullanim

- macOS'ta bir Mac laptopta kapagı kapatmak normalde cihazi uykuya alir.
- Bu uygulama, macOS izin verdigi durumda akisa devam eder: guc bagliysa, harici ekran varsa ve harici klavye/fare ile kapali kapak kullanim kosullari saglaniyorsa.
- Bu kosullarda `Input Activity` aciksa fare hareketi normal akista devam eder.

## Tools Hub

- `tools-hub` bu klasoru otomatik kesfeder.
- Kart uzerinden `Baslat` dediginde uygulama acilir.
- `Durdur` dediginde uygulama nazikce kapanir.
