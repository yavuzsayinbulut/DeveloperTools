# Delivery Radar

Finance workspace icin Git, Jira/TCO ve deployment notlarini eslestiren local dashboard.

Bu proje mevcut `fordeveloper` uygulamasinin kopyasindan ayrildi. Orijinal uygulama `/Users/yavuz.sayinbulut/Desktop/Tools/fordeveloper` altinda kalir; bu kopya Finance odakli degisiklikler icindir.

## Calistirma

```bash
cd /Users/yavuz.sayinbulut/Desktop/Tools/for-developer-radar
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Tarayici: http://127.0.0.1:5556

Varsayilan PIN: `1453`

## Yeni Odak

- `/delivery-radar`: deployment gunleri, PR/MR eslesmeleri, dosya etkisi, test branch teyidi ve pipeline sinyalleri.
- `/team-pulse`: Finance altindaki local git repo hareketi.
- `/search`: local markdown ve TCO trace.
- `/deployments`: local deployment notlarindan gelen kayitlar.

## Workspace

Uygulama Tools reposunda durur; varsayilan analiz workspace'i Finance klasorudur:

```text
/Users/yavuz.sayinbulut/Desktop/Finance
```

Farkli deployment log konumu varsa `Settings > Calisma Alani > Deployment Log Yolu` alanindan verilebilir.

## Plan

Ayrintili ilerleme plani: [DELIVERY_RADAR_PLAN.md](DELIVERY_RADAR_PLAN.md)
