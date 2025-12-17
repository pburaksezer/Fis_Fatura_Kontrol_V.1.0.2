"""
Veritabanı test verisi oluşturma modülü.
Rastgele şirket ve belge verileri üreterek veritabanını doldurur.
Makine öğrenmesi algoritmalarının test edilmesi için anomali içeren veriler de üretir.
"""

import random
from datetime import datetime, timedelta
from typing import Tuple

from db import init_db, add_company, add_document, update_company_totals, get_connection


# Tedarikçi firma isimleri listesi
VENDORS = [
	"Anadolu Tedarik",
	"Efes Lojistik",
	"Marmara Yazilim",
	"Karadeniz Gida",
	"Ege Temizlik",
	"Akdeniz Elektrik",
	"Doğu Donanım",
	"İç Anadolu Kırtasiye",
	"Trakya İnşaat",
	"Van Ofis"
]

# Şirket ismi oluşturmak için önek ve sonek listeleri
COMPANY_PREFIX = ["Anka", "Vizyon", "Atlas", "Nova", "Delta", "Penta", "Beta", "Kuzey", "Güney", "Doğu", "Batı", "Orion", "Mars", "Yakamoz", "Sedef"]
COMPANY_SUFFIX = ["Teknoloji", "Gıda", "Lojistik", "Yazılım", "İnşaat", "Makine", "Enerji", "Danışmanlık", "Perakende", "Sanayi"]


def _gen_company_name(rng: random.Random) -> str:
	"""
	Rastgele şirket ismi oluşturur.
	Önek ve sonek listelerinden rastgele seçim yaparak birleştirir.
	
	Args:
		rng: Rastgele sayı üreteci
		
	Returns:
		Rastgele oluşturulmuş şirket ismi (örn: "Anka Teknoloji A.Ş.")
	"""
	return f"{rng.choice(COMPANY_PREFIX)} {rng.choice(COMPANY_SUFFIX)} A.Ş."


def _gen_tax_number(rng: random.Random) -> str:
	"""
	Rastgele vergi numarası oluşturur.
	10 haneli rastgele sayı dizisi üretir.
	
	Args:
		rng: Rastgele sayı üreteci
		
	Returns:
		10 haneli vergi numarası string'i
	"""
	return "".join(str(rng.randint(0, 9)) for _ in range(10))


def _gen_doc_date(rng: random.Random) -> str:
	"""
	Rastgele belge tarihi oluşturur.
	Bugünden geriye doğru 0-365 gün arası rastgele bir tarih seçer.
	
	Args:
		rng: Rastgele sayı üreteci
		
	Returns:
		YYYY-MM-DD formatında tarih string'i
	"""
	base = datetime.utcnow() - timedelta(days=rng.randint(0, 365))
	return base.strftime("%Y-%m-%d")


def _company_profile(rng: random.Random) -> Tuple[int, float, float]:
	"""
	Şirket için rastgele profil parametreleri oluşturur.
	Her şirketin farklı belge sayısı ve ortalama tutarları olur.
	
	Args:
		rng: Rastgele sayı üreteci
		
	Returns:
		(num_docs, expected_invoice_avg, expected_receipt_avg) tuple'ı
		- num_docs: Şirketin toplam belge sayısı (20-200 arası)
		- expected_invoice_avg: Ortalama fatura tutarı (3,000-50,000 TL arası)
		- expected_receipt_avg: Ortalama fiş tutarı (300-8,000 TL arası)
	"""
	num_docs = rng.randint(20, 200)
	invoice_avg = rng.uniform(3_000, 50_000)
	receipt_avg = rng.uniform(300, 8_000)
	return num_docs, invoice_avg, receipt_avg


def seed_database(db_path: str = "app.db", companies: int = 1000, seed: int = 42) -> None:
	"""
	Veritabanını test verileriyle doldurur.
	
	Her şirket için:
	- Rastgele isim ve vergi numarası oluşturur
	- Belirli sayıda fatura ve fiş belgesi üretir
	- Bazı şirketlerde anomali davranışları simüle eder (aykırı tutarlar, bildirilmemiş belgeler)
	- Gelir ve gider toplamlarını hesaplayıp günceller
	
	Anomali simülasyonları:
	- Şirket seviyesi: Fatura ve fiş tutarlarında çarpanlar (0.5-1.8 arası)
	- Belge seviyesi: Normal dağılımdan sapmalar
	- Bildirim: Bazı şirketlerde %5-35 arası bildirilmemiş belge oranı
	
	Args:
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		companies: Oluşturulacak şirket sayısı (varsayılan: 1000)
		seed: Rastgele sayı üreteci seed değeri (varsayılan: 42)
	"""
	rng = random.Random(seed)
	
	# Veritabanını başlat
	init_db(db_path)
	conn = get_connection(db_path)
	conn.close()

	# Her şirket için veri oluştur
	for _ in range(companies):
		# Şirket temel bilgilerini oluştur
		name = _gen_company_name(rng)
		tax = _gen_tax_number(rng)
		num_docs, invoice_avg, receipt_avg = _company_profile(rng)

		# Başlangıç toplamları sıfırla
		revenue_total = 0.0
		expenses_total = 0.0

		# Şirketi veritabanına ekle (başlangıçta toplamlar 0)
		company_id = add_company(name, tax, 0.0, 0.0, db_path=db_path)

		# Şirket seviyesinde anomali simülasyonu: çarpanlar ile tutarları değiştir
		# Bu, bazı şirketlerin normalden daha yüksek/düşük tutarlı belgeleri olmasını sağlar
		invoice_multiplier = rng.uniform(0.5, 1.6)
		receipt_multiplier = rng.uniform(0.5, 1.8)

		# Bazı şirketlerde bildirilmemiş belge davranışı simüle et
		# Yüksek olasılık = daha fazla bildirilmemiş belge
		under_report_prob = rng.uniform(0.05, 0.35)

		# Her şirket için belgeler oluştur
		for _d in range(num_docs):
			# %55 olasılıkla fatura, %45 olasılıkla fiş
			is_invoice = rng.random() < 0.55
			
			if is_invoice:
				# Fatura tutarı: normal dağılım kullanarak ortalama etrafında varyasyon
				# Çarpan ile şirket seviyesinde anomali eklenir
				amount = max(50.0, rng.gauss(invoice_avg * invoice_multiplier, invoice_avg * 0.35))
				doc_type = "FATURA"
				revenue_total += amount
			else:
				# Fiş tutarı: normal dağılım kullanarak ortalama etrafında varyasyon
				amount = max(20.0, rng.gauss(receipt_avg * receipt_multiplier, receipt_avg * 0.45))
				doc_type = "FIS"
				expenses_total += amount

			# Belgenin bildirilip bildirilmediğini rastgele belirle
			reported = rng.random() > under_report_prob
			
			# Rastgele tedarikçi ve tarih seç
			vendor = rng.choice(VENDORS)
			date_str = _gen_doc_date(rng)
			
			# Belgeyi veritabanına ekle
			add_document(company_id, doc_type, float(amount), reported, vendor, date_str, db_path=db_path)

		# Şirketin toplam gelir ve giderlerini güncelle
		update_company_totals(company_id, revenue_total, expenses_total, db_path=db_path)


if __name__ == "__main__":
	# Modül doğrudan çalıştırıldığında veritabanını doldur
	seed_database()

