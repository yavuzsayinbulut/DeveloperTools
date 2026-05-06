# WindowPinner

Menubar'da calisan kucuk bir macOS yardimci araci.

Ne yapar:
- Aktif penceredeyken `Control + Option + Command + P` ile o pencereyi pinler.
- Pinlenen pencereyi normal uygulama penceresi gibi tasiyip yeniden boyutlandirabilirsin.
- `Control + Option + Command + U` ile pin'i kaldirir.
- Cikis yaparken pinlenen pencerenin seviyesini eski haline dondurur.

Gereken izin:
- `Accessibility` izni gerekir. Ilk acilista uygulama seni ilgili ayara yonlendirir.

Not:
- Bu arac macOS WindowServer seviyesine mudahale ettigi icin yardimci pencere seviyesi cok ozel olan bazi uygulamalarda davranis farki olabilir.
- Bir anda tek pencere pinlenir.

## Build

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/window-pinner-menubar
./Scripts/build-app.sh
open dist/WindowPinner.app
```

## Kullanim

1. Uygulamayi ac.
2. `System Settings > Privacy & Security > Accessibility` altindan `WindowPinner` icin izin ver.
3. Pinlemek istedigin pencereye gec.
4. `Control + Option + Command + P` tuslarina bas.
5. Pin'i kaldirmak icin `Control + Option + Command + U` tuslarina bas.

## Tools Hub

- `tools-hub` bu klasoru otomatik kesfeder.
- Kart uzerinden `Baslat` dediginde uygulama acilir.
- `Durdur` dediginde uygulama kapanir.
