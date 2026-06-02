# ETL Pipeline & Data Warehouse: Tagihan Utilitas Kawasan Industri Tunas Batam

## 📝 Deskripsi Proyek
Proyek ini mengimplementasikan sistem **Data Warehouse (DWH)** dan **pipeline ETL (Extract, Transform, Load)** otomatis untuk mengelola data penggunaan utilitas bulanan (listrik, air, dan *service charge*) penyewa (*tenant*) di Kawasan Industri Tunas Batam Centre.

Sistem dirancang menggunakan pendekatan **Dimensional Modeling (Star Schema)** untuk memisahkan data transaksional ke dalam tabel dimensi dan fakta. Guna mensimulasikan lingkungan bisnis nyata, proyek ini menggunakan data kotor (*dirty data*) yang menyerupai berkas laporan ekspor ERP perusahaan (terdapat spasi tambahan, desimal Rp lokal Indonesia, metadata non-data, dan data teks abnormal seperti "Rusak").

---

## 🛠️ Arsitektur Data Warehouse (Star Schema)
Database dirancang menggunakan skema bintang yang terdiri dari:
* **Tabel Dimensi (Dimension):**
  * `Dim_Tenant`: Data profil penyewa (nama, sektor industri, negara asal).
  * `Dim_Waktu`: Data waktu detail per hari (bulan, kuartal, tahun) untuk visualisasi tren historis.
  * `Dim_Unit_Properti`: Data fisik unit properti (kode blok, tipe unit, luas tanah/bangunan, kapasitas daya).
* **Tabel Fakta (Fact):**
  * `Fact_Tagihan_Utilitas`: Berisi kunci relasi dimensi dan ukuran kuantitatif (*measures*) berupa jumlah pemakaian serta biaya tagihan listrik, air, *service charge*, pajak PJU (10%), dan total biaya akhir.
* **Lapisan OLAP / Dashboard View:**
  * `mvw_dashboard_tunas`: *Materialized View* yang melakukan pra-join tabel fakta dan seluruh dimensi untuk konsumsi Looker Studio secara instan dan cepat.

---

## 🚀 Panduan Setup & Cara Menjalankan Proyek

### 1. Prasyarat (Prerequisites)
Pastikan Anda sudah menginstal:
* **Python 3.8+**
* **DBeaver** (Database Client)
* Akun **Aiven Cloud** (atau penyedia PostgreSQL lainnya)

### 2. Kloning Repositori & Instalasi
Buka terminal/command prompt di komputer Anda:
```bash
git clone https://github.com/OoguroRYuya/Datware_Tunas.git
cd Datware_Tunas
pip install -r requirements.txt
```

### 3. Konfigurasi Database (Aiven Cloud)
1. Buat layanan database PostgreSQL di **Aiven Console** (free tier/trial).
2. Dari Dashboard Aiven, dapatkan **Connection URI** Anda. Contoh:
   `postgresql://avnadmin:password@pg-service-name.aivencloud.com:15843/defaultdb?sslmode=require`
3. Salin berkas `.env.example` menjadi `.env` di komputer Anda, lalu isi variabel `DATABASE_URL` dengan Connection URI tersebut:
   ```env
   DATABASE_URL=postgresql://avnadmin:password@pg-service-name.aivencloud.com:15843/defaultdb?sslmode=require
   ```

### 4. Konfigurasi Koneksi di DBeaver
Untuk mengelola database Anda melalui DBeaver:
1. Buka DBeaver, klik **New Database Connection** -> Pilih **PostgreSQL**.
2. Masukkan parameter koneksi dari Aiven:
   * **Host:** `pg-service-name.aivencloud.com`
   * **Port:** `15843`
   * **Database:** `defaultdb`
   * **Username:** `avnadmin`
   * **Password:** *(Password dari Aiven)*
3. **Penting (SSL):** Buka tab **SSL** di konfigurasi DBeaver tersebut, centang **Use SSL**, dan atur **SSL Mode** ke `require`.
4. Klik **Test Connection**, lalu simpan jika berhasil.

---

## 🎮 Urutan Eksekusi Pipeline

Jalankan langkah-langkah berikut secara berurutan:

### Langkah 1: Jalankan DDL Skema (DBeaver)
* Buka berkas **`script1.sql`** di DBeaver.
* Eksekusi seluruh script untuk membuat tabel dimensi dan fakta baru.

### Langkah 2: Generate Laporan Data Mentah (Python)
Jalankan perintah berikut di terminal:
```bash
python generate_dummy.py
```
* Perintah ini menghasilkan file simulasi ekspor ERP yang kotor: `tenant_kotor_batam.csv` dan `transaksi_kotor_batam.csv`.

### Langkah 3: Jalankan DDL View Analisis (DBeaver)
* Buka berkas **`script2.sql`** di DBeaver.
* Eksekusi seluruh script untuk membuat *Materialized View* (`mvw_dashboard_tunas`) dan *Views* analisis kuartal/bulanan.

### Langkah 4: Jalankan Pipeline ETL (Python)
Jalankan perintah berikut di terminal:
```bash
python etl_pipeline.py
```
* Script ini akan:
  1. **Extract:** Membaca CSV kotor, melewati header laporan, dan membuang baris footer.
  2. **Transform:** Mengonversi teks abnormal (seperti "Rusak") ke desimal, mem-parsing format rupiah lokal Indonesia ke tipe numerik standar, mengimputasi data kosong dengan median, dan menghitung total biaya akhir.
  3. **Load:** Memasukkan data bersih ke PostgreSQL Aiven.
  4. **Refresh:** Melakukan *Refresh Materialized View* untuk menyinkronkan data visualisasi.

---

## 📊 Integrasi Looker Studio (formerly Data Studio)

Untuk membuat visualisasi dashboard menggunakan Looker Studio:
1. Masuk ke [Looker Studio](https://lookerstudio.google.com/).
2. Buat **Laporan Baru** -> Pilih konektor **PostgreSQL**.
3. Masukkan rincian koneksi Aiven Anda:
   * **Host:** `pg-service-name.aivencloud.com`
   * **Port:** `15843`
   * **Database:** `defaultdb`
   * **Username:** `avnadmin`
   * **Password:** *(Password Anda)*
4. Klik **Opsi Lanjutan (Advanced)** dan pastikan SSL aktif. (Looker Studio mendukung SSL default ke Aiven).
5. Pilih tabel **`mvw_dashboard_tunas`** (Materialized View) sebagai sumber data utama laporan Anda.
6. Buat visualisasi yang Anda inginkan (misalnya line chart tren pendapatan bulanan per kuartal, leaderboard top 10 penyewa, atau pie chart sebaran negara asal investor).
