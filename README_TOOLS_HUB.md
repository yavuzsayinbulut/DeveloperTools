# Tools Hub

Tools klasoru icindeki yerel uygulamalari tek ekrandan yonetmek icin yapilan
cati uygulama.

## Ne Yapar

- Alt klasorlerdeki uygulamalari otomatik bulur
- Start / Stop verir
- PID ve port kill verebilir
- URL varsa tarayicida acar
- Klasoru ve loglari acar
- URL bilgisini duzenleyip kaydeder
- Calisan surecin durumunu takip eder

## Calistirma

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools
./start.command
```

## Durdurma

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools
./stop.command
```

## Not

- `clipboard-keeper` ve `fordeveloper` uygulamalari otomatik tespit edilir.
- Her uygulama kendi klasorundeki `start.command` veya uygun fallback komutu
  ile baslatilir.
