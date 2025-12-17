"""
Veritabanı işlemleri modülü.
SQLite veritabanı üzerinde şirket ve belge verilerinin yönetimi için fonksiyonlar içerir.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

# Varsayılan veritabanı dosya adı
DB_FILE = "app.db"


def _enable_foreign_keys(conn: sqlite3.Connection) -> None:
	"""
	SQLite bağlantısında yabancı anahtar kısıtlamalarını etkinleştirir.
	Bu sayede referans bütünlüğü korunur (ör: şirket silindiğinde belgeleri de silinir).
	
	Args:
		conn: SQLite veritabanı bağlantısı
	"""
	conn.execute("PRAGMA foreign_keys = ON;")


def get_connection(db_path: str = DB_FILE) -> sqlite3.Connection:
	"""
	Veritabanı bağlantısı oluşturur ve yabancı anahtarları etkinleştirir.
	
	Args:
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		SQLite veritabanı bağlantı nesnesi
	"""
	conn = sqlite3.connect(db_path)
	_enable_foreign_keys(conn)
	return conn


def init_db(db_path: str = DB_FILE) -> None:
	"""
	Veritabanını başlatır ve gerekli tabloları oluşturur.
	
	Oluşturulan tablolar:
	- companies: Şirket bilgileri (isim, vergi no, gelir, gider, risk skoru)
	- documents: Belge bilgileri (fatura/fiş, tutar, bildirim durumu, şüpheli işareti)
	
	Eğer tablolar zaten varsa, hiçbir şey yapmaz (IF NOT EXISTS).
	
	Args:
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	# Veritabanı dosyasının bulunduğu dizini oluştur (yoksa)
	Path(db_path).parent.mkdir(parents=True, exist_ok=True)
	conn = get_connection(db_path)
	try:
		conn.executescript(
			"""
			-- Şirketler tablosu
			CREATE TABLE IF NOT EXISTS companies (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				tax_number TEXT NOT NULL UNIQUE,
				revenue REAL NOT NULL DEFAULT 0,
				expenses REAL NOT NULL DEFAULT 0,
				risk_score REAL NOT NULL DEFAULT 0,
				risk_level TEXT NOT NULL DEFAULT 'Düşük',
				created_at TEXT NOT NULL
			);

			-- Belgeler tablosu
			CREATE TABLE IF NOT EXISTS documents (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				company_id INTEGER NOT NULL,
				doc_type TEXT NOT NULL CHECK (doc_type IN ('FATURA','FIS')),
				amount REAL NOT NULL,
				reported INTEGER NOT NULL CHECK (reported IN (0,1)),
				vendor TEXT,
				date TEXT NOT NULL,
				suspicious INTEGER NOT NULL DEFAULT 0 CHECK (suspicious IN (0,1)),
				FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
			);
			"""
		)
		conn.commit()
	finally:
		conn.close()


def add_company(name: str, tax_number: str, revenue: float, expenses: float, db_path: str = DB_FILE) -> int:
	"""
	Yeni bir şirket ekler.
	
	Args:
		name: Şirket adı
		tax_number: Vergi numarası (benzersiz olmalı)
		revenue: Toplam gelir
		expenses: Toplam gider
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		Oluşturulan şirketin ID'si
	"""
	conn = get_connection(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			INSERT INTO companies(name, tax_number, revenue, expenses, created_at)
			VALUES(?,?,?,?,?)
			""",
			(name, tax_number, float(revenue), float(expenses), datetime.utcnow().isoformat()),
		)
		conn.commit()
		return cur.lastrowid
	finally:
		conn.close()


def delete_company(company_id: int, db_path: str = DB_FILE) -> None:
	"""
	Bir şirketi ve ona ait tüm belgeleri siler.
	
	Yabancı anahtar kısıtlaması sayesinde (ON DELETE CASCADE),
	şirket silindiğinde otomatik olarak tüm belgeleri de silinir.
	
	Args:
		company_id: Silinecek şirketin ID'si
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	conn = get_connection(db_path)
	try:
		conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
		conn.commit()
	finally:
		conn.close()


def list_companies(db_path: str = DB_FILE) -> List[Tuple]:
	"""
	Tüm şirketleri listeler.
	
	Args:
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		Şirket bilgilerini içeren tuple listesi:
		(id, name, tax_number, revenue, expenses, risk_score, risk_level, created_at)
		ID'ye göre artan sırada sıralanır.
	"""
	conn = get_connection(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			SELECT id, name, tax_number, revenue, expenses, risk_score, risk_level, created_at
			FROM companies
			ORDER BY id ASC
			"""
		)
		return cur.fetchall()
	finally:
		conn.close()


def get_company(company_id: int, db_path: str = DB_FILE) -> Optional[Tuple]:
	"""
	Belirli bir şirketin bilgilerini getirir.
	
	Args:
		company_id: Şirket ID'si
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		Şirket bilgilerini içeren tuple:
		(id, name, tax_number, revenue, expenses, risk_score, risk_level, created_at)
		Eğer şirket bulunamazsa None döner.
	"""
	conn = get_connection(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			SELECT id, name, tax_number, revenue, expenses, risk_score, risk_level, created_at
			FROM companies WHERE id = ?
			""",
			(company_id,),
		)
		return cur.fetchone()
	finally:
		conn.close()


def add_document(
	company_id: int,
	doc_type: str,
	amount: float,
	reported: bool,
	vendor: Optional[str],
	date_str: str,
	db_path: str = DB_FILE,
) -> int:
	"""
	Yeni bir belge ekler (fatura veya fiş).
	
	Args:
		company_id: Belgenin ait olduğu şirket ID'si
		doc_type: Belge tipi ("FATURA" veya "FIS")
		amount: Belge tutarı
		reported: Belgenin bildirilip bildirilmediği (True/False)
		vendor: Tedarikçi firma adı (opsiyonel)
		date_str: Belge tarihi (YYYY-MM-DD formatında)
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		Oluşturulan belgenin ID'si
	"""
	conn = get_connection(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			INSERT INTO documents(company_id, doc_type, amount, reported, vendor, date)
			VALUES(?,?,?,?,?,?)
			""",
			(company_id, doc_type, float(amount), 1 if reported else 0, vendor, date_str),
		)
		conn.commit()
		return cur.lastrowid
	finally:
		conn.close()


def list_documents(company_id: int, db_path: str = DB_FILE) -> List[Tuple]:
	"""
	Belirli bir şirkete ait tüm belgeleri listeler.
	
	Args:
		company_id: Şirket ID'si
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
		
	Returns:
		Belge bilgilerini içeren tuple listesi:
		(id, doc_type, amount, reported, vendor, date, suspicious)
		Tarihe göre artan, sonra ID'ye göre artan sırada sıralanır.
	"""
	conn = get_connection(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			SELECT id, doc_type, amount, reported, vendor, date, suspicious
			FROM documents
			WHERE company_id = ?
			ORDER BY date ASC, id ASC
			""",
			(company_id,),
		)
		return cur.fetchall()
	finally:
		conn.close()


def update_company_totals(company_id: int, revenue: float, expenses: float, db_path: str = DB_FILE) -> None:
	"""
	Şirketin toplam gelir ve gider tutarlarını günceller.
	
	Args:
		company_id: Güncellenecek şirket ID'si
		revenue: Yeni toplam gelir tutarı
		expenses: Yeni toplam gider tutarı
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	conn = get_connection(db_path)
	try:
		conn.execute(
			"UPDATE companies SET revenue = ?, expenses = ? WHERE id = ?",
			(float(revenue), float(expenses), company_id),
		)
		conn.commit()
	finally:
		conn.close()


def update_company_risk(company_id: int, risk_score: float, risk_level: str, db_path: str = DB_FILE) -> None:
	"""
	Şirketin risk skoru ve risk seviyesini günceller.
	
	Makine öğrenmesi algoritması tarafından hesaplanan risk değerlerini kaydeder.
	
	Args:
		company_id: Güncellenecek şirket ID'si
		risk_score: Risk skoru (0-100 arası)
		risk_level: Risk seviyesi ("Düşük", "Riskli", "Yüksek")
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	conn = get_connection(db_path)
	try:
		conn.execute(
			"UPDATE companies SET risk_score = ?, risk_level = ? WHERE id = ?",
			(float(risk_score), risk_level, company_id),
		)
		conn.commit()
	finally:
		conn.close()


def mark_document_suspicious(doc_id: int, suspicious: bool, db_path: str = DB_FILE) -> None:
	"""
	Belgenin şüpheli olup olmadığını işaretler.
	
	Makine öğrenmesi algoritması tarafından anomali tespiti yapılan belgeler
	şüpheli olarak işaretlenir.
	
	Args:
		doc_id: İşaretlenecek belge ID'si
		suspicious: Şüpheli durumu (True/False)
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	conn = get_connection(db_path)
	try:
		conn.execute(
			"UPDATE documents SET suspicious = ? WHERE id = ?",
			(1 if suspicious else 0, doc_id),
		)
		conn.commit()
	finally:
		conn.close()


def update_document_reported(doc_id: int, reported: bool, db_path: str = DB_FILE) -> None:
	"""
	Belgenin bildirilip bildirilmediğini günceller.
	
	Kullanıcı bir belgeyi bildirildi/bildirilmedi olarak işaretlediğinde
	bu fonksiyon kullanılır.
	
	Args:
		doc_id: Güncellenecek belge ID'si
		reported: Bildirim durumu (True/False)
		db_path: Veritabanı dosya yolu (varsayılan: "app.db")
	"""
	conn = get_connection(db_path)
	try:
		conn.execute(
			"UPDATE documents SET reported = ? WHERE id = ?",
			(1 if reported else 0, doc_id),
		)
		conn.commit()
	finally:
		conn.close()
