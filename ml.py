"""
Makine öğrenmesi tabanlı risk analizi modülü.
Şirketlerin ve belgelerin anomali tespiti için Isolation Forest algoritması kullanır.
"""

from typing import List, Tuple
import math

import pandas as pd
from sklearn.ensemble import IsolationForest

from db import (
	list_companies,
	list_documents,
	update_company_risk,
	mark_document_suspicious,
)


def _safe_div(a: float, b: float) -> float:
	"""
	Güvenli bölme işlemi. Sıfıra bölme hatasını önler.
	
	Args:
		a: Bölünen sayı
		b: Bölen sayı
		
	Returns:
		a/b sonucu, eğer b=0 ise 0.0 döner
	"""
	return a / b if b != 0 else 0.0


def _company_features(db_path: str) -> pd.DataFrame:
	"""
	Veritabanından şirket verilerini çekip makine öğrenmesi için özellik vektörlerine dönüştürür.
	
	Her şirket için şu özellikler hesaplanır:
	- revenue: Toplam gelir
	- expenses: Toplam gider
	- num_docs: Toplam belge sayısı
	- avg_amount: Ortalama belge tutarı
	- invoice_ratio: Fatura tutarının toplam belge tutarına oranı
	- profit_margin: Kar marjı (gelir - gider) / gelir
	- reported_ratio: Bildirilen belgelerin oranı
	
	Args:
		db_path: Veritabanı dosya yolu
		
	Returns:
		Şirket özelliklerini içeren pandas DataFrame
	"""
	rows: List[Tuple] = list_companies(db_path)
	features = []
	for (cid, name, tax, revenue, expenses, risk_score, risk_level, created_at) in rows:
		# Şirkete ait tüm belgeleri getir
		docs = list_documents(cid, db_path)
		num_docs = len(docs)
		
		# Fatura ve fiş tutarlarını ayrı ayrı hesapla
		invoice_amt = sum(d[2] for d in docs if d[1] == "FATURA")
		receipt_amt = sum(d[2] for d in docs if d[1] == "FIS")
		
		# Bildirilen belge sayısını say
		reported_count = sum(1 for d in docs if int(d[3]) == 1)
		
		# Ortalama belge tutarını hesapla
		avg_amount = _safe_div(sum(d[2] for d in docs), max(1, num_docs))
		
		# Fatura oranını hesapla (fatura tutarı / toplam belge tutarı)
		invoice_ratio = _safe_div(invoice_amt, invoice_amt + receipt_amt)
		
		# Kar marjını hesapla
		profit_margin = _safe_div((revenue - expenses), max(1.0, revenue))
		
		# Bildirilen belge oranını hesapla
		reported_ratio = _safe_div(reported_count, max(1, num_docs))

		# Özellik vektörünü listeye ekle
		features.append({
			"company_id": cid,
			"revenue": float(revenue),
			"expenses": float(expenses),
			"num_docs": float(num_docs),
			"avg_amount": float(avg_amount),
			"invoice_ratio": float(invoice_ratio),
			"profit_margin": float(profit_margin),
			"reported_ratio": float(reported_ratio),
		})
	return pd.DataFrame(features)


def _document_anomalies(db_path: str) -> float:
	"""
	Belge seviyesinde anomali tespiti yapar ve şüpheli belgeleri işaretler.
	Her şirket için belge tutarlarını analiz ederek aykırı değerleri tespit eder.
	
	Robust Z-score yöntemi kullanılır (medyan mutlak sapma ile):
	- Medyan ve MAD (Median Absolute Deviation) hesaplanır
	- 3.5'ten büyük Z-score değerine sahip belgeler şüpheli olarak işaretlenir
	
	Args:
		db_path: Veritabanı dosya yolu
		
	Returns:
		Global şüpheli belge oranı (0.0 - 1.0 arası)
	"""
	companies = list_companies(db_path)
	all_docs = 0
	suspicious_total = 0
	
	for (cid, *_rest) in companies:
		docs = list_documents(cid, db_path)
		if not docs:
			continue
		
		# Belge tutarlarını pandas Series'e dönüştür
		amounts = pd.Series([d[2] for d in docs], dtype=float)
		
		# Robust Z-score hesaplama: medyan ve medyan mutlak sapma kullanılır
		median = float(amounts.median())
		mad = float((amounts - median).abs().median()) or 1.0  # MAD, eğer 0 ise 1.0 kullan
		robust_z = (amounts - median).abs() / (1.4826 * mad)  # 1.4826 normal dağılım için sabit
		
		# Her belgeyi kontrol et ve şüpheli olanları işaretle
		for idx, d in enumerate(docs):
			is_susp = bool(robust_z.iloc[idx] > 3.5)  # 3.5'ten büyükse şüpheli
			mark_document_suspicious(d[0], is_susp, db_path=db_path)
			suspicious_total += 1 if is_susp else 0
			all_docs += 1
	
	# Global şüpheli belge oranını döndür
	return (suspicious_total / all_docs) if all_docs else 0.0


def _map_risk(score_0_100: float) -> str:
	"""
	Risk skorunu (0-100 arası) risk seviyesine dönüştürür.
	
	Risk seviyeleri:
	- 0-33.33: Düşük risk
	- 33.34-66.66: Riskli
	- 66.67-100: Yüksek risk
	
	Args:
		score_0_100: 0 ile 100 arasında risk skoru
		
	Returns:
		Risk seviyesi string'i ("Düşük", "Riskli", "Yüksek")
	"""
	if score_0_100 < 33.34:
		return "Düşük"
	elif score_0_100 < 66.67:
		return "Riskli"
	return "Yüksek"


def compute_and_update_risk(db_path: str = "app.db", random_state: int = 42) -> None:
	"""
	Ana risk hesaplama ve güncelleme fonksiyonu.
	
	İşlem adımları:
	1. Şirket özelliklerini çıkarır
	2. Isolation Forest algoritması ile şirket seviyesinde anomali tespiti yapar
	3. Belge seviyesinde anomali tespiti yapar
	4. Tüm faktörleri birleştirerek risk skoru hesaplar
	5. Veritabanındaki şirket risk skorlarını günceller
	
	Risk skoru hesaplama formülü:
	- %60: Şirket anomali skoru (Isolation Forest)
	- %25: Bildirilmemiş belge cezası
	- %15: Global şüpheli belge oranı
	
	Args:
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		random_state: Rastgele sayı üreteci seed değeri (varsayılan: 42)
	"""
	# Şirket özelliklerini çıkar
	df = _company_features(db_path)
	if df.empty:
		return

	# Isolation Forest ile anomali tespiti
	# Düşük skorlar daha anormal şirketleri gösterir
	model = IsolationForest(n_estimators=200, contamination=0.08, random_state=random_state)
	X = df[["revenue", "expenses", "num_docs", "avg_amount", "invoice_ratio", "profit_margin", "reported_ratio"]]
	model.fit(X)
	scores = model.score_samples(X)  # Yüksek skor = daha az anormal

	# Skorları [0,1] aralığına normalize et (1 = yüksek risk, ters çevir)
	min_s, max_s = float(scores.min()), float(scores.max())
	span = (max_s - min_s) or 1.0
	anom_0_1 = 1.0 - ((scores - min_s) / span)

	# Belge seviyesinde anomali tespiti
	suspicious_ratio_global = _document_anomalies(db_path)

	# Risk skorunu hesapla: tüm faktörleri birleştir
	risk_scores = []
	for i, row in df.iterrows():
		# Bildirilmemiş belge cezası: daha fazla bildirilmemiş = daha yüksek risk
		reported_penalty = 1.0 - float(row["reported_ratio"])
		
		# Ağırlıklı risk bileşenleri
		company_weighted = 0.6 * float(anom_0_1[i])  # %60 şirket anomali skoru
		report_weighted = 0.25 * float(reported_penalty)  # %25 bildirilmemiş belge cezası
		doc_weighted = 0.15 * float(suspicious_ratio_global)  # %15 global şüpheli belge oranı
		
		# Toplam risk skoru (0-100 arası)
		total = (company_weighted + report_weighted + doc_weighted) * 100.0
		risk_scores.append(total)

	# Veritabanını güncelle: her şirket için risk skoru ve seviyesini kaydet
	for idx, cid in enumerate(df["company_id"].tolist()):
		score = float(risk_scores[idx])
		level = _map_risk(score)
		update_company_risk(int(cid), score, level, db_path=db_path)

