import threading
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, filedialog
import random
import pandas as pd

from db import init_db, list_companies, delete_company, add_company, add_document, update_company_totals, list_documents, get_company, mark_document_suspicious, update_document_reported
from data_seed import seed_database
from ml import compute_and_update_risk

DB_PATH = "app.db"

# Tema renk paletleri
THEMES = {
	"light": {
		"bg_primary": "#f5f7fa",
		"bg_secondary": "#ffffff",
		"bg_toolbar": "#2c3e50",
		"accent_blue": "#3498db",
		"accent_green": "#2ecc71",
		"accent_red": "#e74c3c",
		"accent_orange": "#f39c12",
		"text_primary": "#2c3e50",
		"text_secondary": "#7f8c8d",
		"border": "#e0e0e0",
		"hover_blue": "#2980b9",
		"hover_green": "#27ae60",
		"hover_red": "#c0392b",
		"risk_low": "#d5f4e6",
		"risk_medium": "#fff4e6",
		"risk_high": "#ffe6e6",
		"suspicious": "#ffebee",
		"gelir": "#2e7d32",
		"gider": "#1565c0"
	},
	"dark": {
		"bg_primary": "#1a1a1a",
		"bg_secondary": "#2d2d2d",
		"bg_toolbar": "#0d1117",
		"accent_blue": "#58a6ff",
		"accent_green": "#3fb950",
		"accent_red": "#f85149",
		"accent_orange": "#d29922",
		"text_primary": "#e6edf3",
		"text_secondary": "#8b949e",
		"border": "#30363d",
		"hover_blue": "#388bfd",
		"hover_green": "#2ea043",
		"hover_red": "#da3633",
		"risk_low": "#1a472a",
		"risk_medium": "#3d2817",
		"risk_high": "#3d1f1f",
		"suspicious": "#3d2121",
		"gelir": "#238636",
		"gider": "#1f6feb"
	}
}

# Varsayılan tema
COLORS = THEMES["light"]


class AddCompanyDialog(simpledialog.Dialog):
	def body(self, master):
		self.title("Şirket Ekle")
		master.configure(bg=COLORS["bg_primary"], padx=20, pady=20)
		
		# Başlık
		title_label = tk.Label(master, text="Yeni Şirket Ekle", font=("Segoe UI", 14, "bold"), 
		                      bg=COLORS["bg_primary"], fg=COLORS["text_primary"])
		title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=tk.W)
		
		# Şirket Adı
		name_label = tk.Label(master, text="Şirket Adı:", font=("Segoe UI", 10), 
		                     bg=COLORS["bg_primary"], fg=COLORS["text_primary"])
		name_label.grid(row=1, column=0, sticky=tk.W, padx=6, pady=10)
		self.name_var = tk.StringVar()
		self.name_entry = tk.Entry(master, textvariable=self.name_var, width=40, 
		                          font=("Segoe UI", 10), relief=tk.FLAT, bd=2, 
		                          highlightthickness=1, highlightbackground=COLORS["border"],
		                          highlightcolor=COLORS["accent_blue"])
		self.name_entry.grid(row=1, column=1, padx=6, pady=10)

		# Vergi No
		tax_label = tk.Label(master, text="Vergi No (10 hane):", font=("Segoe UI", 10), 
		                    bg=COLORS["bg_primary"], fg=COLORS["text_primary"])
		tax_label.grid(row=2, column=0, sticky=tk.W, padx=6, pady=10)
		self.tax_var = tk.StringVar()
		# Maksimum 10 karakter sınırı için validate fonksiyonu
		vcmd = (master.register(self._validate_tax_input), '%P')
		self.tax_entry = tk.Entry(master, textvariable=self.tax_var, width=20, 
		                         font=("Segoe UI", 10), relief=tk.FLAT, bd=2,
		                         highlightthickness=1, highlightbackground=COLORS["border"],
		                         highlightcolor=COLORS["accent_blue"], validate='key', validatecommand=vcmd)
		self.tax_entry.grid(row=2, column=1, padx=6, pady=10, sticky=tk.W)

		# Oto Belge Üret
		docs_label = tk.Label(master, text="Oto Belge Üret (50-120 adet):", font=("Segoe UI", 10), 
		                    bg=COLORS["bg_primary"], fg=COLORS["text_primary"])
		docs_label.grid(row=3, column=0, sticky=tk.W, padx=6, pady=10)
		self.gen_docs_var = tk.BooleanVar(value=True)
		self.gen_docs_chk = tk.Checkbutton(master, variable=self.gen_docs_var, 
		                                  bg=COLORS["bg_primary"], activebackground=COLORS["bg_primary"],
		                                  selectcolor=COLORS["accent_blue"], font=("Segoe UI", 10))
		self.gen_docs_chk.grid(row=3, column=1, sticky=tk.W, padx=6, pady=10)
		return self.name_entry

	def _validate_tax_input(self, new_value):
		# Sadece rakam kabul et ve maksimum 10 karakter
		if len(new_value) > 10:
			return False
		# Boş string veya sadece rakamlar
		return new_value == "" or new_value.isdigit()

	def validate(self):
		name = (self.name_var.get() or "").strip()
		tax = (self.tax_var.get() or "").strip()
		if not name or not tax or not tax.isdigit() or len(tax) != 10:
			messagebox.showerror("Hata", "Lütfen geçerli bir ad ve 10 haneli vergi no girin.")
			return False
		return True

	def apply(self):
		self.result = {
			"name": self.name_var.get().strip(),
			"tax": self.tax_var.get().strip(),
			"gen_docs": bool(self.gen_docs_var.get()),
		}


class CompanyDetailWindow(tk.Toplevel):
	def __init__(self, master, company_id: int):
		super().__init__(master)
		self.company_id = company_id
		self.title(f"Şirket Detayı - ID {company_id}")
		self.geometry("1000x570")
		self.configure(bg=COLORS["bg_primary"])
		self._build_ui()
		self.refresh()

	def _build_ui(self):
		# Detay bilgileri kısmı
		self.info_frame = tk.Frame(self, bg=COLORS["bg_secondary"], relief=tk.FLAT, bd=0)
		self.info_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=12)
		
		info_inner = tk.Frame(self.info_frame, bg=COLORS["bg_secondary"], padx=15, pady=12)
		info_inner.pack(fill=tk.X)

		self.lbl_name = tk.Label(info_inner, text="Şirket:", font=("Segoe UI", 10), 
		                        bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])
		self.lbl_name.pack(side=tk.LEFT)
		self.lbl_name_val = tk.Label(info_inner, text="-", font=("Segoe UI", 11, "bold"), 
		                            bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])
		self.lbl_name_val.pack(side=tk.LEFT, padx=8)

		separator1 = tk.Frame(info_inner, width=1, bg=COLORS["border"], height=20)
		separator1.pack(side=tk.LEFT, padx=12)

		self.lbl_tax = tk.Label(info_inner, text="Vergi No:", font=("Segoe UI", 10), 
		                       bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])
		self.lbl_tax.pack(side=tk.LEFT)
		self.lbl_tax_val = tk.Label(info_inner, text="-", font=("Segoe UI", 10), 
		                           bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])
		self.lbl_tax_val.pack(side=tk.LEFT, padx=8)

		separator2 = tk.Frame(info_inner, width=1, bg=COLORS["border"], height=20)
		separator2.pack(side=tk.LEFT, padx=12)

		self.lbl_risk = tk.Label(info_inner, text="Risk:", font=("Segoe UI", 10), 
		                        bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])
		self.lbl_risk.pack(side=tk.LEFT)
		self.lbl_risk_val = tk.Label(info_inner, text="-", font=("Segoe UI", 10), 
		                            bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])
		self.lbl_risk_val.pack(side=tk.LEFT, padx=8)

		# Üst Bar kısmı
		toolbar = tk.Frame(self, bg=COLORS["bg_secondary"], relief=tk.FLAT, bd=0)
		toolbar.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 12))
		
		toolbar_inner = tk.Frame(toolbar, bg=COLORS["bg_secondary"], padx=8, pady=8)
		toolbar_inner.pack(fill=tk.X)
		
		self.btn_refresh = self._create_button(toolbar_inner, "Yenile", COLORS["accent_blue"], 
		                                     COLORS["hover_blue"], self.refresh)
		self.btn_refresh.pack(side=tk.LEFT, padx=4)
		
		self.btn_toggle_susp = self._create_button(toolbar_inner, "Seçileni Şüpheli Değiştir", 
		                                          COLORS["accent_orange"], COLORS["accent_red"], 
		                                          self.toggle_selected_suspicious)
		self.btn_toggle_susp.pack(side=tk.LEFT, padx=4)
		
		self.btn_toggle_rep = self._create_button(toolbar_inner, "Seçileni Beyan Değiştir", 
		                                         COLORS["accent_green"], COLORS["hover_green"], 
		                                         self.toggle_selected_reported)
		self.btn_toggle_rep.pack(side=tk.LEFT, padx=4)
		
		self.btn_export = self._create_button(toolbar_inner, "Excel Dışa Aktar", 
		                                     COLORS["accent_blue"], COLORS["hover_blue"], 
		                                     self.export_excel)
		self.btn_export.pack(side=tk.LEFT, padx=4)
		
		self.btn_recompute = self._create_button(toolbar_inner, "Bu Şirket İçin Risk Hesapla", 
		                                        COLORS["accent_green"], COLORS["hover_green"], 
		                                        self.recompute_company_risk)
		self.btn_recompute.pack(side=tk.LEFT, padx=4)

		# Belge ağacı kısmı
		tree_frame = tk.Frame(self, bg=COLORS["bg_primary"])
		tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
		
		cols = ("id", "flow", "type", "amount", "reported", "vendor", "date", "suspicious")
		self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
		self.tree.heading("id", text="ID")
		self.tree.heading("flow", text="Akış")
		self.tree.heading("type", text="Tür")
		self.tree.heading("amount", text="Tutar")
		self.tree.heading("reported", text="Beyan")
		self.tree.heading("vendor", text="Tedarikçi")
		self.tree.heading("date", text="Tarih")
		self.tree.heading("suspicious", text="Şüpheli")

		self.tree.column("id", width=60, anchor=tk.CENTER)
		self.tree.column("flow", width=80, anchor=tk.CENTER)
		self.tree.column("type", width=80, anchor=tk.CENTER)
		self.tree.column("amount", width=110, anchor=tk.E)
		self.tree.column("reported", width=80, anchor=tk.CENTER)
		self.tree.column("vendor", width=260)
		self.tree.column("date", width=120, anchor=tk.CENTER)
		self.tree.column("suspicious", width=80, anchor=tk.CENTER)

		self.tree.tag_configure("suspicious", background=COLORS["suspicious"])
		self.tree.tag_configure("gelir", foreground=COLORS["gelir"], font=("Segoe UI", 9))
		self.tree.tag_configure("gider", foreground=COLORS["gider"], font=("Segoe UI", 9))

		scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview, style="Vertical.TScrollbar")
		self.tree.configure(yscrollcommand=scroll_y.set)
		self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
	
	def _create_button(self, parent, text, bg_color, hover_color, command):
		btn = tk.Button(parent, text=text, command=command, font=("Segoe UI", 9),
		               bg=bg_color, fg="white", relief=tk.FLAT, bd=0, padx=12, pady=6,
		               cursor="hand2", activebackground=hover_color, activeforeground="white")
		return btn

	def refresh(self):
		c = get_company(self.company_id, db_path=DB_PATH)
		if not c:
			messagebox.showerror("Hata", "Şirket bulunamadı (silinmiş olabilir).")
			self.destroy()
			return
		cid, name, tax, revenue, expenses, risk_score, risk_level, created_at = c
		self.lbl_name_val.config(text=name)
		self.lbl_tax_val.config(text=tax)
		self.lbl_risk_val.config(text=f"{risk_level} ({risk_score:.1f})  Gelir: {revenue:,.2f}  Gider: {expenses:,.2f}")

		for i in self.tree.get_children():
			self.tree.delete(i)
		docs = list_documents(self.company_id, db_path=DB_PATH)
		for d in docs:
			doc_id, doc_type, amount, reported, vendor, date, suspicious = d
			flow = "Gelir" if doc_type == "FATURA" else "Gider"
			amount_disp = f"{amount:,.2f}" if flow == "Gelir" else f"-{amount:,.2f}"
			tag_flow = "gelir" if flow == "Gelir" else "gider"
			tags = (tag_flow,) + (("suspicious",) if int(suspicious) == 1 else tuple())
			rep_txt = "Evet" if int(reported) == 1 else "Hayır"
			sus_txt = "Evet" if int(suspicious) == 1 else "Hayır"
			self.tree.insert("", tk.END, values=(doc_id, flow, doc_type, amount_disp, rep_txt, vendor or "-", date, sus_txt), tags=tags)

	def _get_selected_doc_id(self) -> int:
		cur = self.tree.selection()
		if not cur:
			return -1
		values = self.tree.item(cur[0], "values")
		return int(values[0])

	def toggle_selected_suspicious(self):
		doc_id = self._get_selected_doc_id()
		if doc_id < 0:
			messagebox.showinfo("Bilgi", "Lütfen bir belge seçin.")
			return
		# determine current value from row
		values = self.tree.item(self.tree.selection()[0], "values")
		current = (values[7] == "Evet")
		mark_document_suspicious(doc_id, not current, db_path=DB_PATH)
		self.refresh()

	def toggle_selected_reported(self):
		doc_id = self._get_selected_doc_id()
		if doc_id < 0:
			messagebox.showinfo("Bilgi", "Lütfen bir belge seçin.")
			return
		values = self.tree.item(self.tree.selection()[0], "values")
		current = (values[4] == "Evet")
		update_document_reported(doc_id, not current, db_path=DB_PATH)
		self.refresh()

	def export_excel(self):
		path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], title="Excel olarak kaydet")
		if not path:
			return
		docs = list_documents(self.company_id, db_path=DB_PATH)
		df = pd.DataFrame(docs, columns=["id", "type", "amount", "reported", "vendor", "date", "suspicious"])
		df["flow"] = df["type"].map(lambda t: "Gelir" if t == "FATURA" else "Gider")
		df["amount_display"] = df.apply(lambda r: ("-" if r["flow"] == "Gider" else "") + f"{float(r['amount']):,.2f}", axis=1)
		df["reported"] = df["reported"].map(lambda x: "Evet" if int(x) == 1 else "Hayır")
		df["suspicious"] = df["suspicious"].map(lambda x: "Evet" if int(x) == 1 else "Hayır")
		df = df[["id", "flow", "type", "amount_display", "reported", "vendor", "date", "suspicious"]]
		df.columns = ["id", "akış", "tür", "tutar", "beyan", "tedarikçi", "tarih", "şüpheli"]
		df.to_excel(path, index=False)
		messagebox.showinfo("Tamam", "Excel dışa aktarıldı.")

	def recompute_company_risk(self):
		# Basit çözüm: küresel risk hesaplamayı çalıştır, ardından yalnızca bu pencereyi yenile
		self.config(cursor="watch")
		self.title("Risk hesaplanıyor... - Şirket Detayı")
		def wrapper():
			try:
				compute_and_update_risk(DB_PATH)
			except Exception as e:
				self.after(0, lambda: messagebox.showerror("Hata", str(e)))
			finally:
				self.after(0, self._clear_busy_risk)
		threading.Thread(target=wrapper, daemon=True).start()
	
	def _clear_busy_risk(self):
		self.config(cursor="")
		self.title(f"Şirket Detayı - ID {self.company_id}")
		self.refresh()


class App(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title("Vergi Risk Analizi")
		self.geometry("1050x600")
		self.current_theme = "light"
		self.configure(bg=COLORS["bg_primary"])
		self._setup_style()
		self._setup_widgets()
		self._init_and_seed()
	
	def _setup_style(self):
		style = ttk.Style()
		style.theme_use("clam")
		style.configure("Treeview", background=COLORS["bg_secondary"], foreground=COLORS["text_primary"],
		               fieldbackground=COLORS["bg_secondary"], font=("Segoe UI", 9), rowheight=25)
		style.configure("Treeview.Heading", background=COLORS["bg_toolbar"], foreground="white",
		               font=("Segoe UI", 9, "bold"), relief=tk.FLAT)
		style.map("Treeview.Heading", background=[("active", COLORS["accent_blue"])])
		style.configure("Treeview", rowheight=28)
		style.configure("Vertical.TScrollbar", background=COLORS["bg_secondary"], 
		               troughcolor=COLORS["bg_primary"], borderwidth=0, arrowcolor=COLORS["text_secondary"])

	def _setup_widgets(self):
		# Modern toolbar
		toolbar = tk.Frame(self, bg=COLORS["bg_toolbar"], relief=tk.FLAT, bd=0, height=60)
		toolbar.pack(side=tk.TOP, fill=tk.X)
		toolbar.pack_propagate(False)
		
		toolbar_inner = tk.Frame(toolbar, bg=COLORS["bg_toolbar"], padx=12, pady=10)
		toolbar_inner.pack(fill=tk.BOTH, expand=True)

		# Butonlar
		btn_frame = tk.Frame(toolbar_inner, bg=COLORS["bg_toolbar"])
		btn_frame.pack(side=tk.LEFT)

		self.btn_refresh = self._create_button(btn_frame, "Yenile", COLORS["accent_blue"], 
		                                     COLORS["hover_blue"], self.refresh)
		self.btn_refresh.pack(side=tk.LEFT, padx=3)

		self.btn_seed = self._create_button(btn_frame, "Boşsa 1000 Şirket Yükle", COLORS["accent_green"], 
		                                  COLORS["hover_green"], self.seed_if_empty)
		self.btn_seed.pack(side=tk.LEFT, padx=3)

		self.btn_risk = self._create_button(btn_frame, "Risk Hesapla", COLORS["accent_orange"], 
		                                  COLORS["accent_red"], self.compute_risk_async)
		self.btn_risk.pack(side=tk.LEFT, padx=3)

		self.btn_add = self._create_button(btn_frame, "Şirket Ekle", COLORS["accent_blue"], 
		                                 COLORS["hover_blue"], self.add_company_dialog)
		self.btn_add.pack(side=tk.LEFT, padx=3)

		self.btn_del = self._create_button(btn_frame, "Şirket Sil", COLORS["accent_red"], 
		                                 COLORS["hover_red"], self.delete_selected)
		self.btn_del.pack(side=tk.LEFT, padx=3)

		self.btn_delete_all = self._create_button(btn_frame, "Tümünü Sil", COLORS["accent_red"], 
		                                         COLORS["hover_red"], self.delete_all_companies)
		self.btn_delete_all.pack(side=tk.LEFT, padx=3)

		self.btn_detail = self._create_button(btn_frame, "Detay", COLORS["accent_green"], 
		                                     COLORS["hover_green"], self.open_selected_detail)
		self.btn_detail.pack(side=tk.LEFT, padx=3)

		# Tema değiştirme butonu
		self.btn_theme = self._create_button(btn_frame, "🌙 Karanlık", COLORS["accent_orange"], 
		                                   COLORS["accent_red"], self.toggle_theme)
		self.btn_theme.pack(side=tk.LEFT, padx=3)

		# Arama kontrolleri
		search_frame = tk.Frame(toolbar_inner, bg=COLORS["bg_toolbar"])
		search_frame.pack(side=tk.RIGHT)
		
		lbl = tk.Label(search_frame, text="Ara:", font=("Segoe UI", 9), 
		             bg=COLORS["bg_toolbar"], fg="white")
		lbl.pack(side=tk.LEFT, padx=(0, 6))
		
		self.search_var = tk.StringVar()
		self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=28,
		                            font=("Segoe UI", 9), relief=tk.FLAT, bd=0,
		                            highlightthickness=1, highlightbackground=COLORS["border"],
		                            highlightcolor=COLORS["accent_blue"], bg=COLORS["bg_secondary"],
		                            fg=COLORS["text_primary"], insertbackground=COLORS["text_primary"])
		self.search_entry.pack(side=tk.LEFT, padx=2)
		self.search_entry.bind("<Return>", lambda _e: self.refresh())
		
		self.btn_search = self._create_button(search_frame, "Ara", COLORS["accent_blue"], 
		                                    COLORS["hover_blue"], self.refresh)
		self.btn_search.pack(side=tk.LEFT, padx=2)
		
		self.btn_clear = self._create_button(search_frame, "Temizle", COLORS["text_secondary"], 
		                                   COLORS["text_primary"], self.clear_search)
		self.btn_clear.pack(side=tk.LEFT, padx=2)

		# Belge ağacı kısmı
		tree_frame = tk.Frame(self, bg=COLORS["bg_primary"])
		tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

		cols = ("id", "name", "tax", "revenue", "expenses", "risk_score", "risk_level", "created")
		self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=22)
		self.tree.heading("id", text="ID")
		self.tree.heading("name", text="Şirket")
		self.tree.heading("tax", text="Vergi No")
		self.tree.heading("revenue", text="Gelir")
		self.tree.heading("expenses", text="Gider")
		self.tree.heading("risk_score", text="Risk Skoru")
		self.tree.heading("risk_level", text="Seviye")
		self.tree.heading("created", text="Oluşturma")

		self.tree.column("id", width=60, anchor=tk.CENTER)
		self.tree.column("name", width=260)
		self.tree.column("tax", width=120)
		self.tree.column("revenue", width=120, anchor=tk.E)
		self.tree.column("expenses", width=120, anchor=tk.E)
		self.tree.column("risk_score", width=100, anchor=tk.E)
		self.tree.column("risk_level", width=90, anchor=tk.CENTER)
		self.tree.column("created", width=160, anchor=tk.W)

		self.tree.tag_configure("Düşük", background=COLORS["risk_low"])
		self.tree.tag_configure("Riskli", background=COLORS["risk_medium"])
		self.tree.tag_configure("Yüksek", background=COLORS["risk_high"])

		self.tree.bind("<Double-1>", self.on_double_click_row)

		scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview, style="Vertical.TScrollbar")
		self.tree.configure(yscrollcommand=scroll_y.set)
		self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
	
	def _create_button(self, parent, text, bg_color, hover_color, command):
		btn = tk.Button(parent, text=text, command=command, font=("Segoe UI", 9),
		               bg=bg_color, fg="white", relief=tk.FLAT, bd=0, padx=12, pady=6,
		               cursor="hand2", activebackground=hover_color, activeforeground="white")
		return btn

	def toggle_theme(self):
		global COLORS
		# Tema değiştir
		if self.current_theme == "light":
			self.current_theme = "dark"
			COLORS = THEMES["dark"]
			self.btn_theme.config(text="☀️ Aydınlık")
		else:
			self.current_theme = "light"
			COLORS = THEMES["light"]
			self.btn_theme.config(text="🌙 Karanlık")
		
		# Tüm widget'ları güncelle
		self._apply_theme()

	def _apply_theme(self):
		# Ana pencere
		self.configure(bg=COLORS["bg_primary"])
		
		# Style güncelle
		style = ttk.Style()
		style.configure("Treeview", background=COLORS["bg_secondary"], foreground=COLORS["text_primary"],
		               fieldbackground=COLORS["bg_secondary"], font=("Segoe UI", 9), rowheight=25)
		style.configure("Treeview.Heading", background=COLORS["bg_toolbar"], foreground="white",
		               font=("Segoe UI", 9, "bold"), relief=tk.FLAT)
		style.map("Treeview.Heading", background=[("active", COLORS["accent_blue"])])
		style.configure("Treeview", rowheight=28)
		style.configure("Vertical.TScrollbar", background=COLORS["bg_secondary"], 
		               troughcolor=COLORS["bg_primary"], borderwidth=0, arrowcolor=COLORS["text_secondary"])
		
		# Toolbar ve içindeki widget'lar
		for widget in self.winfo_children():
			if isinstance(widget, tk.Frame):
				self._update_widget_colors(widget)
		
		# Treeview tag'leri güncelle
		self.tree.tag_configure("Düşük", background=COLORS["risk_low"])
		self.tree.tag_configure("Riskli", background=COLORS["risk_medium"])
		self.tree.tag_configure("Yüksek", background=COLORS["risk_high"])
		
		# Refresh ile verileri yeniden yükle
		self.refresh()

	def _update_widget_colors(self, widget):
		"""Rekursif olarak widget renklerini güncelle"""
		try:
			if isinstance(widget, tk.Frame):
				if hasattr(widget, 'cget'):
					try:
						bg = widget.cget('bg')
						if bg in [THEMES["light"]["bg_toolbar"], THEMES["dark"]["bg_toolbar"], 
						          THEMES["light"]["bg_primary"], THEMES["dark"]["bg_primary"],
						          THEMES["light"]["bg_secondary"], THEMES["dark"]["bg_secondary"]]:
							if "toolbar" in str(widget):
								widget.config(bg=COLORS["bg_toolbar"])
							elif "tree" in str(widget).lower() or "frame" in str(widget).lower():
								widget.config(bg=COLORS["bg_primary"])
							else:
								widget.config(bg=COLORS["bg_secondary"])
					except:
						pass
			elif isinstance(widget, tk.Label):
				try:
					bg = widget.cget('bg')
					if bg in [THEMES["light"]["bg_toolbar"], THEMES["dark"]["bg_toolbar"]]:
						widget.config(bg=COLORS["bg_toolbar"], fg="white")
					elif bg in [THEMES["light"]["bg_primary"], THEMES["dark"]["bg_primary"]]:
						widget.config(bg=COLORS["bg_primary"], fg=COLORS["text_primary"])
					elif bg in [THEMES["light"]["bg_secondary"], THEMES["dark"]["bg_secondary"]]:
						widget.config(bg=COLORS["bg_secondary"], fg=COLORS["text_primary"])
				except:
					pass
			elif isinstance(widget, tk.Entry):
				try:
					widget.config(bg=COLORS["bg_secondary"], fg=COLORS["text_primary"],
					            highlightbackground=COLORS["border"],
					            highlightcolor=COLORS["accent_blue"],
					            insertbackground=COLORS["text_primary"])
				except:
					pass
			
			# Alt widget'ları da güncelle
			for child in widget.winfo_children():
				self._update_widget_colors(child)
		except:
			pass

	def _init_and_seed(self):
		init_db(DB_PATH)
		rows = list_companies(DB_PATH)
		if not rows:
			self._run_bg(self._seed_and_compute, "Veriler yükleniyor...")
		else:
			self.refresh()

	def _run_bg(self, func, busy_message: str):
		self.config(cursor="watch")
		self.title(f"{busy_message} - Vergi Risk Analizi")
		def wrapper():
			try:
				func()
			except Exception as e:
				self.after(0, lambda: messagebox.showerror("Hata", str(e)))
			finally:
				self.after(0, self._clear_busy)
		threading.Thread(target=wrapper, daemon=True).start()

	def _clear_busy(self):
		self.config(cursor="")
		self.title("Vergi Risk Analizi")
		self.refresh()

	def _seed_and_compute(self):
		seed_database(DB_PATH, companies=1000)
		compute_and_update_risk(DB_PATH)

	def refresh(self):
		q = (self.search_var.get() if hasattr(self, "search_var") else "").strip().lower()
		for i in self.tree.get_children():
			self.tree.delete(i)
		for row in list_companies(DB_PATH):
			cid, name, tax, revenue, expenses, risk_score, risk_level, created_at = row
			if q:
				if (q not in (name or "").lower()) and (q not in (tax or "").lower()):
					continue
			tag = risk_level if risk_level in ("Düşük", "Riskli", "Yüksek") else ""
			self.tree.insert("", tk.END, values=(cid, name, tax, f"{revenue:,.2f}", f"{expenses:,.2f}", f"{risk_score:,.1f}", risk_level, created_at), tags=(tag,))

	def clear_search(self):
		if hasattr(self, "search_var"):
			self.search_var.set("")
		self.refresh()

	def seed_if_empty(self):
		self._run_bg(self._seed_and_compute, "Seed çalışıyor...")

	def compute_risk_async(self):
		self._run_bg(lambda: compute_and_update_risk(DB_PATH), "Risk hesaplanıyor...")

	def add_company_dialog(self):
		dlg = AddCompanyDialog(self)
		if not getattr(dlg, "result", None):
			return
		data = dlg.result
		name = data["name"]
		tax = data["tax"]
		cid = add_company(name, tax, 0.0, 0.0, db_path=DB_PATH)
		if data["gen_docs"]:
			self._generate_documents_for_company(cid)
		self.refresh()

	def _generate_documents_for_company(self, company_id: int):
		rng = random.Random()
		num_docs = rng.randint(50, 120)
		revenue_total = 0.0
		expenses_total = 0.0
		invoice_avg = rng.uniform(5_000, 40_000)
		receipt_avg = rng.uniform(500, 8_000)
		under_rep = rng.uniform(0.05, 0.25)
		for _ in range(num_docs):
			is_invoice = rng.random() < 0.55
			if is_invoice:
				amount = max(50.0, rng.gauss(invoice_avg, invoice_avg * 0.35))
				doc_type = "FATURA"
				revenue_total += amount
			else:
				amount = max(20.0, rng.gauss(receipt_avg, receipt_avg * 0.45))
				doc_type = "FIS"
				expenses_total += amount
			reported = rng.random() > under_rep
			vendor = "Yeni Tedarikçi"
			date_str = "2025-01-01"
			add_document(company_id, doc_type, float(amount), reported, vendor, date_str, db_path=DB_PATH)
		update_company_totals(company_id, revenue_total, expenses_total, db_path=DB_PATH)

	def delete_selected(self):
		cur = self.tree.selection()
		if not cur:
			messagebox.showinfo("Bilgi", "Lütfen bir şirket seçin.")
			return
		if not messagebox.askyesno("Onay", "Seçili şirket(ler) silinsin mi?"):
			return
		for item in cur:
			values = self.tree.item(item, "values")
			cid = int(values[0])
			delete_company(cid, DB_PATH)
		self.refresh()

	def delete_all_companies(self):
		# Önce kaç şirket olduğunu kontrol et
		companies = list_companies(DB_PATH)
		if not companies:
			messagebox.showinfo("Bilgi", "Silinecek şirket bulunmamaktadır.")
			return
		
		# Çift onay iste
		count = len(companies)
		msg = f"TÜM ŞİRKETLERİ SİLMEK İSTEDİĞİNİZE EMİN MİSİNİZ?\n\n"
		msg += f"Bu işlem {count} şirketi ve tüm belgelerini kalıcı olarak silecektir.\n"
		msg += f"Bu işlem geri alınamaz!\n\n"
		msg += f"Devam etmek istiyor musunuz?"
		
		if not messagebox.askyesno("DİKKAT - Tüm Şirketleri Sil", msg, icon='warning'):
			return
		
		# Son bir kez daha onay iste
		if not messagebox.askyesno("SON ONAY", 
		                          "Bu işlem geri alınamaz!\n\n"
		                          "Tüm şirketleri silmek istediğinize kesinlikle emin misiniz?",
		                          icon='error'):
			return
		
		# Tüm şirketleri sil
		self.config(cursor="watch")
		try:
			for company in companies:
				cid = company[0]
				delete_company(cid, DB_PATH)
			messagebox.showinfo("Tamamlandı", f"Tüm şirketler ({count} adet) başarıyla silindi.")
		except Exception as e:
			messagebox.showerror("Hata", f"Şirketler silinirken bir hata oluştu:\n{str(e)}")
		finally:
			self.config(cursor="")
			self.refresh()

	def on_double_click_row(self, _event):
		cur = self.tree.selection()
		if not cur:
			return
		values = self.tree.item(cur[0], "values")
		cid = int(values[0])
		CompanyDetailWindow(self, cid)

	def open_selected_detail(self):
		cur = self.tree.selection()
		if not cur:
			messagebox.showinfo("Bilgi", "Lütfen bir şirket seçin.")
			return
		values = self.tree.item(cur[0], "values")
		cid = int(values[0])
		CompanyDetailWindow(self, cid)


def main():
	init_db(DB_PATH)
	app = App()
	app.mainloop()


if __name__ == "__main__":
	main()
