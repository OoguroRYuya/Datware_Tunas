import pandas as pd
import os
import logging
import random
from sqlalchemy import create_engine, text
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# 1. SETUP LOGGING & KONEKSI DATABASE
# ==========================================
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Koneksi via environment variable (.env)
load_dotenv()
DB_URI = os.getenv("DATABASE_URL")
if not DB_URI:
    raise ValueError("[ERROR] DATABASE_URL tidak ditemukan! Pastikan file .env ada dan berisi DATABASE_URL.")
engine = create_engine(DB_URI)

logger.info("=" * 60)
logger.info("MEMULAI ETL PIPELINE - TAGIHAN UTILITAS BATAM")
logger.info("=" * 60)

# Helper untuk memproses angka berformat Indonesia / Rupiah dan data teks aneh
def clean_indonesian_numeric(val):
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).strip()
    
    # Deteksi anomali keterangan teks (seperti "Rusak", "Meteran Mati", "N/A")
    if any(abnormal in val_str.upper() for abnormal in ["RUSAK", "MATI", "N/A", "CATATAN"]):
        return None
        
    # Buang simbol Rupiah dan spasi
    val_str = val_str.replace("Rp.", "").replace("Rp", "").replace("RP", "").strip()
    
    # Deteksi format Indonesia (titik desimal menggunakan koma)
    if "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    else:
        # Jika tidak ada koma desimal tapi ada titik separator ribuan
        parts = val_str.split('.')
        if len(parts) > 1:
            last_part = parts[-1]
            if len(last_part) == 3:
                val_str = val_str.replace(".", "")
            elif len(last_part) in [1, 2]:
                val_str = "".join(parts[:-1]).replace(".", "") + "." + last_part
            else:
                if val_str.count(".") > 1:
                    val_str = val_str.replace(".", "")
                    
    try:
        return float(val_str)
    except ValueError:
        return None

# ==========================================
# 2. EXTRACT (Menarik Data Mentah)
# ==========================================
logger.info("[EXTRACT] Membaca data mentah dari CSV (skip header & filter footer)...")

# Membaca tenant: skip 3 baris header laporan
df_tenant_raw = pd.read_csv('tenant_kotor_batam.csv', skiprows=3)
# Buang baris kosong atau footer (baris yang tenant_id-nya bukan numerik)
df_tenant_raw = df_tenant_raw[pd.to_numeric(df_tenant_raw['tenant_id'], errors='coerce').notna()].copy()
df_tenant_raw['tenant_id'] = df_tenant_raw['tenant_id'].astype(int)

# Membaca transaksi: skip 4 baris header laporan
df_transaksi_raw = pd.read_csv('transaksi_kotor_batam.csv', skiprows=4)
# Buang baris kosong atau footer (baris yang trx_id-nya bukan numerik)
df_transaksi_raw = df_transaksi_raw[pd.to_numeric(df_transaksi_raw['trx_id'], errors='coerce').notna()].copy()
df_transaksi_raw['trx_id'] = df_transaksi_raw['trx_id'].astype(int)
df_transaksi_raw['tenant_id'] = df_transaksi_raw['tenant_id'].astype(int)
df_transaksi_raw['properti_id'] = df_transaksi_raw['properti_id'].astype(int)

logger.info(f"  Tenant: {len(df_tenant_raw)} baris")
logger.info(f"  Transaksi: {len(df_transaksi_raw)} baris")

# ==========================================
# 3. TRANSFORM (Pembersihan & Kalkulasi)
# ==========================================
logger.info("[TRANSFORM] Membersihkan data (dengan pembersih format Rupiah & teks)...")

# --- A. Cleaning Dim_Tenant ---
df_tenant_clean = df_tenant_raw.copy()

# Anomali #1: Memperbaiki typo di sektor industri (Standarisasi)
typo_sektor_sebelum = df_tenant_clean['sektor_industri'].isin(['mnfktur', 'LOGISTIK ', 'elektronika']).sum()
df_tenant_clean['sektor_industri'] = df_tenant_clean['sektor_industri'].str.strip()
df_tenant_clean['sektor_industri'] = df_tenant_clean['sektor_industri'].replace({
    'mnfktur': 'Manufaktur',
    'LOGISTIK': 'Logistik',
    'elektronika': 'Elektronik'
})
logger.info(f"  #1 Typo sektor industri: {typo_sektor_sebelum} baris diperbaiki")

# Anomali #5: Missing nama_perusahaan → isi placeholder
null_nama = df_tenant_clean['nama_perusahaan'].isna().sum()
df_tenant_clean['nama_perusahaan'] = df_tenant_clean['nama_perusahaan'].fillna("Tenant Tidak Diketahui")
logger.info(f"  #5 Missing nama_perusahaan: {null_nama} baris → diisi 'Tenant Tidak Diketahui'")

# --- B. Cleaning & Transform Fact_Transaksi ---
df_transaksi_clean = df_transaksi_raw.copy()

# Bersihkan format angka/Rupiah dan string aneh di kolom numerik terlebih dahulu
df_transaksi_clean['pemakaian_listrik'] = df_transaksi_clean['pemakaian_listrik'].apply(clean_indonesian_numeric)
df_transaksi_clean['pemakaian_air'] = df_transaksi_clean['pemakaian_air'].apply(clean_indonesian_numeric)
df_transaksi_clean['service_charge_base'] = df_transaksi_clean['service_charge_base'].apply(clean_indonesian_numeric)

# Anomali #3: Menghapus duplikat transaksi berdasarkan trx_id
duplikat_sebelum = df_transaksi_clean['trx_id'].duplicated().sum()
df_transaksi_clean = df_transaksi_clean.drop_duplicates(subset=['trx_id'], keep='last')
logger.info(f"  #3 Duplikat trx_id: {duplikat_sebelum} baris dihapus (sisa: {len(df_transaksi_clean)})")

# Anomali #2 & #9: Memperbaiki pemakaian listrik (negatif dijadikan absolut, missing/teks diisi median)
negatif_listrik = (df_transaksi_clean['pemakaian_listrik'] < 0).sum()
df_transaksi_clean['pemakaian_listrik'] = df_transaksi_clean['pemakaian_listrik'].abs()

null_listrik = df_transaksi_clean['pemakaian_listrik'].isna().sum()
median_listrik = df_transaksi_clean['pemakaian_listrik'].median()
df_transaksi_clean['pemakaian_listrik'] = df_transaksi_clean['pemakaian_listrik'].fillna(median_listrik)
logger.info(f"  #2 Pemakaian listrik negatif: {negatif_listrik} baris → abs()")
logger.info(f"  #9 Missing/Abnormal listrik: {null_listrik} baris → diisi median ({median_listrik:.2f})")

# Anomali #4 & #9: Missing pemakaian_air → isi dengan median
null_air = df_transaksi_clean['pemakaian_air'].isna().sum()
median_air = df_transaksi_clean['pemakaian_air'].median()
df_transaksi_clean['pemakaian_air'] = df_transaksi_clean['pemakaian_air'].fillna(median_air)
logger.info(f"  #4 Missing/Abnormal air: {null_air} baris → diisi median ({median_air:.2f})")

# Imputasi service_charge_base jika ada missing setelah pembersihan
null_sc = df_transaksi_clean['service_charge_base'].isna().sum()
if null_sc > 0:
    median_sc = df_transaksi_clean['service_charge_base'].median()
    df_transaksi_clean['service_charge_base'] = df_transaksi_clean['service_charge_base'].fillna(median_sc)

# Anomali #6: Outlier pemakaian_listrik → cap ke batas atas 50.000 kWh
BATAS_LISTRIK = 50000.0
outlier_count = (df_transaksi_clean['pemakaian_listrik'] > BATAS_LISTRIK).sum()
df_transaksi_clean['pemakaian_listrik'] = df_transaksi_clean['pemakaian_listrik'].clip(upper=BATAS_LISTRIK)
logger.info(f"  #6 Outlier listrik (>{BATAS_LISTRIK:.0f} kWh): {outlier_count} baris → di-cap")

# Anomali #7: Format tanggal inkonsisten → parse mixed format
df_transaksi_clean['tanggal'] = pd.to_datetime(
    df_transaksi_clean['tanggal'], format='mixed', dayfirst=True
)
logger.info(f"  #7 Format tanggal: berhasil di-parse (mixed format)")

# --- C. Kalkulasi Measure / Metrik Tagihan ---
logger.info("[TRANSFORM] Menghitung measures...")
# Asumsi tarif: Listrik Rp 1.500/kWh, Air Rp 5.000/m3
df_transaksi_clean['tagihan_listrik'] = df_transaksi_clean['pemakaian_listrik'] * 1500
df_transaksi_clean['tagihan_air'] = df_transaksi_clean['pemakaian_air'] * 5000

# Service charge dan Pajak PJU (10% dari tagihan listrik)
df_transaksi_clean['service_charge'] = df_transaksi_clean['service_charge_base']
df_transaksi_clean['pajak_pju'] = df_transaksi_clean['tagihan_listrik'] * 0.10

# Total Biaya Akhir (tanpa total_service_charge yang redundan)
df_transaksi_clean['biaya_akhir'] = (
    df_transaksi_clean['tagihan_listrik'] + 
    df_transaksi_clean['tagihan_air'] + 
    df_transaksi_clean['service_charge'] + 
    df_transaksi_clean['pajak_pju']
)

# --- D. Membuat Dimensi Tambahan ---
logger.info("[TRANSFORM] Membuat dimensi tambahan...")

# Dim_Waktu: Diambil dari tanggal unik di transaksi (diperkaya untuk OLAP)
df_waktu = pd.DataFrame({'tanggal_tagihan': df_transaksi_clean['tanggal'].dt.date.unique()})
df_waktu['tanggal_tagihan'] = pd.to_datetime(df_waktu['tanggal_tagihan'])
df_waktu['bulan'] = df_waktu['tanggal_tagihan'].dt.strftime('%B')
df_waktu['bulan_angka'] = df_waktu['tanggal_tagihan'].dt.month
df_waktu['kuartal'] = 'Q' + df_waktu['tanggal_tagihan'].dt.quarter.astype(str)
df_waktu['tahun_kuartal'] = df_waktu['tanggal_tagihan'].dt.year.astype(str) + '-' + df_waktu['kuartal']
df_waktu['hari'] = df_waktu['tanggal_tagihan'].dt.day_name()
df_waktu['tahun'] = df_waktu['tanggal_tagihan'].dt.year
df_waktu['id_waktu'] = range(1, len(df_waktu) + 1)

# Dim_Unit_Properti: Generate dummy properti (332 unit)
random.seed(42)  # Konsistensi data properti setiap run

prop_ids = []
kode_bloks = []
tipe_units = []
luas_tanahs = []
luas_bangunans = []
kapasitas_listriks = []

# Generate 250 Factory/Warehouse units
for i in range(1, 251):
    prop_ids.append(i)
    # Block codes: Blok A to Blok J
    block_char = chr(65 + (i % 10))  # A-J
    kode_bloks.append(f"Blok {block_char}-{i}")
    
    tipe = random.choice(['Pabrik Besar', 'Pabrik Sedang', 'Gudang Logistik'])
    tipe_units.append(tipe)
    
    if tipe == 'Pabrik Besar':
        lt = round(random.uniform(2500, 5000), 2)
        lb = round(random.uniform(2000, lt - 100), 2)
        cap = random.choice([50000, 100000, 150000])
    elif tipe == 'Pabrik Sedang':
        lt = round(random.uniform(1000, 2500), 2)
        lb = round(random.uniform(800, lt - 50), 2)
        cap = random.choice([22000, 33000, 50000])
    else: # Gudang Logistik
        lt = round(random.uniform(800, 2000), 2)
        lb = round(random.uniform(600, lt - 50), 2)
        cap = random.choice([10000, 22000, 33000])
        
    luas_tanahs.append(lt)
    luas_bangunans.append(lb)
    kapasitas_listriks.append(cap)

# Generate 82 Ruko/Commercial units
for i in range(251, 333):
    prop_ids.append(i)
    # Block codes: Bizpark-1 to Bizpark-50, Blok K-1 to K-16, Blok L-1 to L-16
    if i <= 300:
        kode_bloks.append(f"Bizpark-{i - 250}")
    elif i <= 316:
        kode_bloks.append(f"Blok K-{i - 300}")
    else:
        kode_bloks.append(f"Blok L-{i - 316}")
        
    tipe = random.choice(['Ruko Komersial', 'Kios Bisnis'])
    tipe_units.append(tipe)
    
    lt = round(random.uniform(100, 250), 2)
    lb = round(random.uniform(80, lt - 20), 2)
    cap = random.choice([2200, 3500, 4400, 6600])
    
    luas_tanahs.append(lt)
    luas_bangunans.append(lb)
    kapasitas_listriks.append(cap)

df_properti = pd.DataFrame({
    'id_properti': prop_ids,
    'kode_blok': kode_bloks,
    'tipe_unit': tipe_units,
    'luas_tanah': luas_tanahs,
    'luas_bangunan': luas_bangunans,
    'kapasitas_listrik': kapasitas_listriks
})


# --- E. Mapping Foreign Key untuk Fact_Transaksi ---
df_transaksi_clean = df_transaksi_clean.merge(
    df_waktu[['tanggal_tagihan', 'id_waktu']], 
    left_on='tanggal', 
    right_on='tanggal_tagihan', 
    how='left'
)

# Menyiapkan kolom final untuk Fact Table (sesuai DDL baru - tanpa total_service_charge)
cols_fact = [
    'id_waktu', 'tenant_id', 'properti_id', 
    'pemakaian_listrik', 'tagihan_listrik', 'pemakaian_air', 'tagihan_air', 
    'service_charge', 'pajak_pju', 'biaya_akhir'
]
df_fact = df_transaksi_clean[cols_fact].rename(columns={'tenant_id': 'id_tenant', 'properti_id': 'id_properti'})

# Siapkan Dim_Waktu dan Dim_Tenant final
df_waktu_final = df_waktu[['id_waktu', 'tanggal_tagihan', 'bulan', 'bulan_angka', 'kuartal', 'tahun_kuartal', 'hari', 'tahun']]
df_tenant_final = df_tenant_clean[['tenant_id', 'nama_perusahaan', 'sektor_industri', 'asal_negara']].rename(columns={'tenant_id': 'id_tenant'})

logger.info(f"  Dim_Waktu: {len(df_waktu_final)} baris (tanggal unik)")
logger.info(f"  Dim_Tenant: {len(df_tenant_final)} baris")
logger.info(f"  Dim_Unit_Properti: {len(df_properti)} baris")
logger.info(f"  Fact_Tagihan_Utilitas: {len(df_fact)} baris")

# ==========================================
# 4. LOAD (Memasukkan Data ke PostgreSQL)
# ==========================================
logger.info("[LOAD] Memulai loading data ke Data Warehouse (Aiven)...")

# TRUNCATE semua tabel sebelum load (idempotent - aman dijalankan ulang)
logger.info("[LOAD] TRUNCATE semua tabel (idempotent)...")
try:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE fact_tagihan_utilitas CASCADE"))
        conn.execute(text("TRUNCATE TABLE dim_waktu CASCADE"))
        conn.execute(text("TRUNCATE TABLE dim_tenant CASCADE"))
        conn.execute(text("TRUNCATE TABLE dim_unit_properti CASCADE"))
    logger.info("  Semua tabel berhasil di-TRUNCATE")
except Exception as e:
    logger.warning(f"  TRUNCATE gagal (tabel mungkin belum ada): {e}")
    logger.info("  Pipeline akan membuat tabel baru via to_sql()")

# Load data - dimensi dulu, baru fact (urutan FK)
tables_to_load = [
    ('dim_waktu', df_waktu_final),
    ('dim_tenant', df_tenant_final),
    ('dim_unit_properti', df_properti),
    ('fact_tagihan_utilitas', df_fact),
]

for table_name, df in tables_to_load:
    try:
        df.to_sql(table_name, engine, if_exists='append', index=False)
        logger.info(f"  [OK] {table_name} loaded ({len(df)} rows)")
    except Exception as e:
        logger.error(f"  [ERROR] Gagal load {table_name}: {e}")
        raise  # Stop pipeline jika ada error

# ==========================================
# 5. VALIDASI POST-LOAD
# ==========================================
logger.info("[VALIDASI] Memeriksa jumlah data di database...")

def validate_load(table_name, expected):
    """Verifikasi jumlah baris di tabel sesuai dengan yang di-load."""
    with engine.connect() as conn:
        actual = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
    status = "[OK]" if actual == expected else "[WARN]"
    logger.info(f"  {status} {table_name}: {actual}/{expected} rows")
    return actual == expected

all_ok = all([
    validate_load('dim_waktu', len(df_waktu_final)),
    validate_load('dim_tenant', len(df_tenant_final)),
    validate_load('dim_unit_properti', len(df_properti)),
    validate_load('fact_tagihan_utilitas', len(df_fact)),
])

# ==========================================
# 6. REFRESH MATERIALIZED VIEW
# ==========================================
try:
    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW mvw_dashboard_tunas"))
    logger.info("[REFRESH] [OK] Materialized View mvw_dashboard_tunas di-refresh")
except Exception as e:
    logger.warning(f"[REFRESH] [WARN] MV belum ada atau gagal refresh: {e}")
    logger.info("  Jalankan script2.sql di DBeaver untuk membuat MV dan Views")

# ==========================================
# SELESAI
# ==========================================
logger.info("=" * 60)
if all_ok:
    logger.info("[DONE] ETL PIPELINE SELESAI - Semua data berhasil masuk ke Data Warehouse!")
else:
    logger.warning("[WARN] ETL selesai tapi ada ketidaksesuaian jumlah data. Periksa log di atas.")
logger.info("=" * 60)