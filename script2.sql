-- =====================================================
-- VIEWS & MATERIALIZED VIEW — OLAP LAYER
-- Jalankan di DBeaver SETELAH ETL Pipeline berhasil
-- =====================================================

-- =====================================================
-- 1. MATERIALIZED VIEW: Dashboard Utama (untuk Data Studio)
--    Pre-computed JOIN semua tabel — query sangat cepat
-- =====================================================
CREATE MATERIALIZED VIEW mvw_dashboard_tunas AS
SELECT 
    -- Dimensi Waktu (diperkaya untuk drill-down)
    dw.tanggal_tagihan, 
    dw.bulan, 
    dw.bulan_angka,
    dw.kuartal,
    dw.tahun_kuartal,
    dw.hari,
    dw.tahun,
    
    -- Dimensi Tenant
    dt.nama_perusahaan, 
    dt.sektor_industri, 
    dt.asal_negara,
    
    -- Dimensi Unit Properti
    dp.kode_blok, 
    dp.tipe_unit, 
    dp.luas_tanah, 
    dp.luas_bangunan, 
    dp.kapasitas_listrik,
    
    -- Fakta Tagihan (Measures)
    ft.pemakaian_listrik, 
    ft.tagihan_listrik, 
    ft.pemakaian_air, 
    ft.tagihan_air, 
    ft.service_charge, 
    ft.pajak_pju, 
    ft.biaya_akhir,
    ft.etl_loaded_at
FROM 
    Fact_Tagihan_Utilitas ft
JOIN 
    Dim_Waktu dw ON ft.id_waktu = dw.id_waktu
JOIN 
    Dim_Tenant dt ON ft.id_tenant = dt.id_tenant
JOIN 
    Dim_Unit_Properti dp ON ft.id_properti = dp.id_properti;


-- =====================================================
-- 2. VIEW: Ringkasan per Kuartal (Tahun → Kuartal drill-down)
--    Untuk line chart tren per kuartal di Data Studio
-- =====================================================
CREATE OR REPLACE VIEW vw_ringkasan_kuartal AS
SELECT 
    dw.tahun,
    dw.kuartal,
    dw.tahun_kuartal,
    COUNT(*)                     AS jumlah_transaksi,
    COUNT(DISTINCT ft.id_tenant) AS jumlah_tenant_aktif,
    SUM(ft.pemakaian_listrik)    AS total_pemakaian_listrik,
    SUM(ft.pemakaian_air)        AS total_pemakaian_air,
    SUM(ft.tagihan_listrik)      AS total_tagihan_listrik,
    SUM(ft.tagihan_air)          AS total_tagihan_air,
    SUM(ft.biaya_akhir)          AS total_pendapatan,
    AVG(ft.biaya_akhir)          AS rata_rata_tagihan
FROM Fact_Tagihan_Utilitas ft
JOIN Dim_Waktu dw ON ft.id_waktu = dw.id_waktu
GROUP BY dw.tahun, dw.kuartal, dw.tahun_kuartal
ORDER BY dw.tahun, dw.kuartal;


-- =====================================================
-- 3. VIEW: Ringkasan Bulanan per Sektor Industri
--    Untuk bar/line chart per sektor di Data Studio
-- =====================================================
CREATE OR REPLACE VIEW vw_ringkasan_sektor_bulanan AS
SELECT 
    dw.tahun,
    dw.bulan,
    dw.bulan_angka,
    dw.kuartal,
    dw.tahun_kuartal,
    dt.sektor_industri,
    COUNT(*)                    AS jumlah_transaksi,
    SUM(ft.pemakaian_listrik)   AS total_pemakaian_listrik,
    SUM(ft.pemakaian_air)       AS total_pemakaian_air,
    SUM(ft.biaya_akhir)         AS total_pendapatan,
    AVG(ft.biaya_akhir)         AS rata_rata_tagihan
FROM Fact_Tagihan_Utilitas ft
JOIN Dim_Waktu dw ON ft.id_waktu = dw.id_waktu
JOIN Dim_Tenant dt ON ft.id_tenant = dt.id_tenant
GROUP BY dw.tahun, dw.bulan, dw.bulan_angka, dw.kuartal, dw.tahun_kuartal, dt.sektor_industri
ORDER BY dw.tahun, dw.bulan_angka;


-- =====================================================
-- 4. VIEW: Ringkasan per Negara Asal
--    Untuk pie chart distribusi negara di Data Studio
-- =====================================================
CREATE OR REPLACE VIEW vw_ringkasan_negara AS
SELECT 
    dt.asal_negara,
    COUNT(DISTINCT dt.id_tenant) AS jumlah_tenant,
    COUNT(*)                     AS jumlah_transaksi,
    SUM(ft.biaya_akhir)          AS total_pendapatan,
    AVG(ft.biaya_akhir)          AS rata_rata_tagihan
FROM Fact_Tagihan_Utilitas ft
JOIN Dim_Tenant dt ON ft.id_tenant = dt.id_tenant
GROUP BY dt.asal_negara;


-- =====================================================
-- 5. VIEW: Top 10 Tenant berdasarkan Total Tagihan
--    Untuk leaderboard / scorecard di Data Studio
-- =====================================================
CREATE OR REPLACE VIEW vw_top_tenant AS
SELECT 
    dt.nama_perusahaan,
    dt.sektor_industri,
    dt.asal_negara,
    COUNT(*)               AS jumlah_transaksi,
    SUM(ft.biaya_akhir)    AS total_tagihan,
    AVG(ft.biaya_akhir)    AS rata_rata_tagihan
FROM Fact_Tagihan_Utilitas ft
JOIN Dim_Tenant dt ON ft.id_tenant = dt.id_tenant
GROUP BY dt.nama_perusahaan, dt.sektor_industri, dt.asal_negara
ORDER BY total_tagihan DESC
LIMIT 10;