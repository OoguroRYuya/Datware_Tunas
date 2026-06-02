import pandas as pd
import random
from faker import Faker
import datetime as dt_mod

# Seed agar data reproducible setiap run
random.seed(42)

# Menggunakan locale Indonesia
fake = Faker('id_ID') 
Faker.seed(42)

# Helper untuk memformat angka ke format Rupiah / lokal Indonesia
def format_indo_numeric(val, add_symbol=True):
    if val is None or pd.isna(val):
        return None
    # val adalah float atau int
    formatted = f"{val:,.2f}"
    parts = formatted.split('.')
    thousand_part = parts[0].replace(',', '.')
    decimal_part = parts[1]
    res = f"{thousand_part},{decimal_part}"
    if add_symbol:
        res = f"Rp. {res}"
    return res

# 1. Generate Data Tenant (Fokus Ekosistem Industri Batam)
def generate_tenant_data(num_records):
    tenants = []
    sektor_options = ['Manufaktur', 'Logistik', 'Elektronik', 'Otomotif', 'Plastik & Molding', 'Marine/Shipyard']
    # Negara-negara yang umum punya pabrik di Batam
    negara_options = ['Indonesia (Lokal Batam)', 'Singapura', 'Malaysia', 'Jepang', 'Korea Selatan', 'Taiwan']
    
    for i in range(1, num_records + 1):
        sektor = random.choice(sektor_options)
        asal_negara = random.choice(negara_options)
        
        # Skenario Data Kotor #1: 10% sektor industri disengaja salah ketik (typo)
        if random.random() < 0.1:
            if sektor == 'Manufaktur': sektor = 'mnfktur'
            elif sektor == 'Logistik': sektor = 'LOGISTIK ' # Ada spasi lebih
            elif sektor == 'Elektronik': sektor = 'elektronika'
            
        nama = f"{fake.company()} Batam" if asal_negara == 'Indonesia (Lokal Batam)' else f"PT {fake.last_name()} Indonesia"
        
        # Skenario Data Kotor #5: 3% nama_perusahaan NULL (missing data)
        if random.random() < 0.03:
            nama = None
            
        tenants.append({
            'tenant_id': i,
            'nama_perusahaan': nama,
            'sektor_industri': sektor,
            'asal_negara': asal_negara
        })
    return pd.DataFrame(tenants)

# 2. Generate Data Transaksi Tagihan (Pola bulanan berkala)
def generate_transaksi_data(tenant_df):
    transaksi = []
    
    # Membuat daftar bulan historis selama 24 bulan (Juni 2024 s/d Mei 2026)
    months = []
    for year in [2024, 2025, 2026]:
        for month in range(1, 13):
            if (year == 2024 and month >= 6) or (year == 2025) or (year == 2026 and month <= 5):
                months.append((year, month))
                
    trx_id_counter = 1
    
    for year, month in months:
        for tenant_id in tenant_df['tenant_id'].tolist():
            pemakaian_listrik = round(random.uniform(1000.0, 50000.0), 2)
            # Menentukan pemakaian air secara acak (gudang/ruko sedikit, pabrik banyak)
            pemakaian_air = round(random.uniform(100.0, 500.0) if random.random() > 0.1 else random.uniform(1000.0, 5000.0), 2)
            
            # Skenario Data Kotor #2: 5% data pemakaian listrik bernilai negatif (tidak valid)
            if random.random() < 0.05:
                pemakaian_listrik = -abs(pemakaian_listrik)
                
            # Skenario Data Kotor #6: 3% outlier pemakaian_listrik (>100.000 kWh, jauh di atas normal)
            if random.random() < 0.03:
                pemakaian_listrik = round(random.uniform(100000.0, 500000.0), 2)
                
            # Skenario Data Kotor #4: 5% pemakaian_air NULL (missing/tidak tercatat)
            if random.random() < 0.05:
                pemakaian_air = None
                
            # Skenario Data Kotor #9 (Baru): 3% data berisi teks abnormal ("Rusak", "Meteran Mati", "N/A")
            listrik_val = pemakaian_listrik
            air_val = pemakaian_air
            if listrik_val is not None and random.random() < 0.03:
                listrik_val = random.choice(["Rusak", "Meteran Mati", "N/A"])
            if air_val is not None and random.random() < 0.03:
                air_val = random.choice(["Rusak", "N/A", "Tanpa Catatan"])
                
            # Skenario Data Kotor #8 (Baru): Format Angka & Mata Uang Indonesia (Rp. 12.500,00 atau 12.500,00)
            if isinstance(listrik_val, (int, float)):
                if random.random() < 0.8:  # 80% data menggunakan format Indonesia
                    listrik_val = format_indo_numeric(listrik_val, add_symbol=random.choice([True, False]))
            
            if isinstance(air_val, (int, float)):
                if random.random() < 0.8:
                    air_val = format_indo_numeric(air_val, add_symbol=False) # Air biasanya tidak pakai Rp. tapi ribuan desimal lokal
                    
            service_charge_base = random.choice([5000000, 7500000, 10000000])
            if random.random() < 0.8:
                service_charge_base = format_indo_numeric(service_charge_base, add_symbol=True)
            
            # Skenario Data Kotor #3: 5% data duplikat ID transaksi
            trx_id = trx_id_counter if random.random() > 0.05 else max(1, trx_id_counter - 1)
            
            # Skenario Data Kotor #11 (Baru): Tanggal terpusat pada siklus billing (tanggal 20-25 setiap bulan)
            day = random.randint(20, 25)
            tanggal = dt_mod.date(year, month, day)
            
            # Skenario Data Kotor #7: 5% format tanggal inkonsisten (DD/MM/YYYY bukan YYYY-MM-DD)
            if random.random() < 0.05:
                tanggal_str = tanggal.strftime('%d/%m/%Y')  # Format salah
            else:
                tanggal_str = tanggal.strftime('%Y-%m-%d')   # Format benar
            
            transaksi.append({
                'trx_id': trx_id,
                'tanggal': tanggal_str,
                'tenant_id': tenant_id,
                'properti_id': random.randint(1, 20),
                'pemakaian_listrik': listrik_val,
                'pemakaian_air': air_val,
                'service_charge_base': service_charge_base
            })
            
            trx_id_counter += 1
            
    return pd.DataFrame(transaksi)

# Fungsi untuk menyimpan CSV dengan header & footer laporan (Skenario Data Kotor #10)
def save_csv_with_report_envelope(df, filename, title_rows, footer_rows):
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        # Tulis Header Laporan (Metadata Non-Data)
        for row in title_rows:
            f.write(row + '\n')
        # Tulis Konten Tabel Data
        df.to_csv(f, index=False)
        # Tulis Footer Laporan
        for row in footer_rows:
            f.write(row + '\n')

if __name__ == "__main__":
    print("Generating realistic Batam-centric utility data with Excel report headers/footers & Rupiah formats...")
    
    # 1. Generate Tenant Data
    df_tenant = generate_tenant_data(100)
    tenant_titles = [
        "LAPORAN DATA TENANT KAWASAN INDUSTRI TUNAS BATAM",
        "Periode Ekspor Laporan: Mei 2026",
        ""
    ]
    tenant_footers = [
        "",
        "--- AKHIR LAPORAN TENANT ---",
        f"Total Tenant Terdaftar: {len(df_tenant)}",
        "Dicetak secara otomatis oleh sistem master data."
    ]
    save_csv_with_report_envelope(df_tenant, 'tenant_kotor_batam.csv', tenant_titles, tenant_footers)
    
    # 2. Generate Transaction Data
    df_transaksi = generate_transaksi_data(df_tenant)
    transaksi_titles = [
        "LAPORAN HISTORIS PENGGUNAAN UTILITAS (LISTRIK DAN AIR)",
        "Kawasan Industri Tunas Batam Centre",
        "Periode Billing: Juni 2024 s/d Mei 2026",
        ""
    ]
    transaksi_footers = [
        "",
        "--- AKHIR LAPORAN TRANSAKSI UTILITAS ---",
        f"Total Baris Transaksi: {len(df_transaksi)}",
        "Status Sinkronisasi Data: Selesai"
    ]
    save_csv_with_report_envelope(df_transaksi, 'transaksi_kotor_batam.csv', transaksi_titles, transaksi_footers)
    
    print("\n[OK] Berhasil membuat tenant_kotor_batam.csv dan transaksi_kotor_batam.csv dengan format baru!")