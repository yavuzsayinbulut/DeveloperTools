# Delivery Radar Plan

Bu kopya, mevcut fordeveloper uygulamasini Finance workspace icin Git + Jira + deployment izleme aracina cevirmek icin acildi.

## Hedef

- Local deployment notlarini Finance altindaki git gecmisiyle eslestirmek.
- Jira/TCO key uzerinden task, MR/PR, dosya etkisi ve deployment gununu tek ekranda gostermek.
- Test branch basim/teyit durumunu deployment notlari ve merge hedef branch bilgisiyle izlemek.
- Pipeline hatalarini once local sinyallerden, sonra GitLab/Jira API entegrasyonlariyla madde madde raporlamak.

## Asama 1: Local Git + Deployment MVP

- Workspace default: `/Users/yavuz.sayinbulut/Desktop/Finance`
- Port: `5556`
- Yeni ekran: `/delivery-radar`
- Yeni API: `/api/delivery-radar`
- Local git merge commitlerinden PR/MR, branch, dosya diff, Jira/TCO key, test dosyasi ve risk sinyali cikarimi.
- `FutureDeployment` kayitlariyla TCO veya MR URL uzerinden eslesme.

## Asama 2: Jira Entegrasyonu

- Settings alanlari: Jira base URL, email/user, API token.
- Token `security.encrypt_value` ile saklanacak.
- Jira key icin summary, status, assignee, priority, sprint ve updated_at cekilecek.
- API cevaplari cache'lenecek; sayfa acilisinda Jira'ya her seferinde yuk bindirilmeyecek.

## Asama 3: GitLab Pipeline Entegrasyonu

- Settings alanlari: GitLab base URL ve token.
- Remote URL'den project path cozulup GitLab project id bulunacak.
- MR pipeline status, failed job listesi ve son hata satirlari cekilecek.
- Delivery Radar uyarilari failed job adi, stage, hata ozeti ve MR linkiyle madde madde gosterilecek.

## Asama 4: Gunluk Akis

- Deployment gunleri icin "bugun cikacaklar" gorunumu.
- Eksik test branch teyidi, Jira status uyumsuzlugu, failed pipeline ve dokuman eksigi icin radar kartlari.
- Gunun sonunda daily note'a otomatik ozet taslagi.
