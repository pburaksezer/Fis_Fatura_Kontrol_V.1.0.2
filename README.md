## Vergi Kaçakçılığını Önlemeye Yönelik Uygulama (Python + Tkinter)

Bu uygulama, şirketlerin gelir-gider ve belge (fatura/fiş) verilerini kullanarak makine öğrenmesi yardımıyla anormallikleri tespit eder ve her şirkete risk skoru atar.

### Özellikler
- Tkinter tabanlı GUI (Python)
- 1000 örnek şirket ve belge (seed)
- SQLite veritabanında kalıcı saklama
- Makine öğrenmesi (IsolationForest) ile anomali tespiti
- Sahte/kuşkulu fiş-fatura tespiti (belge seviyesinde anomali)
- Risk skoru ve sınıfları: Düşük, Riskli, Yüksek
- Şirket ekle/sil, detay görüntüle

### Kurulum
1. Python 3.10+ yükleyin.
2. Bağımlılıkları kurun:
```bash
pip install -r requirements.txt
```

### Çalıştırma
```bash
python app.py
```

İlk çalıştırmada veritabanı oluşur ve içi boşsa 1000 şirket + belgelerle doldurur. Ardından risk skorlarını hesaplar.

### Notlar
- Tkinter ve sqlite3 Python ile birlikte gelir.
- Makine öğrenmesi için scikit-learn, veri işlemede pandas kullanılır.
