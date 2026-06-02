
DROP TABLE IF EXISTS Fact_Tagihan_Utilitas CASCADE;
DROP TABLE IF EXISTS Dim_Waktu CASCADE;
DROP TABLE IF EXISTS Dim_Tenant CASCADE;
DROP TABLE IF EXISTS Dim_Unit_Properti CASCADE;

DROP MATERIALIZED VIEW IF EXISTS mvw_dashboard_tunas CASCADE;
DROP VIEW IF EXISTS vw_ringkasan_kuartal CASCADE;
DROP VIEW IF EXISTS vw_ringkasan_sektor_bulanan CASCADE;
DROP VIEW IF EXISTS vw_ringkasan_negara CASCADE;
DROP VIEW IF EXISTS vw_top_tenant CASCADE;

-- =====================================================
-- DIMENSI 1: Dim_Waktu (Kapan tagihan terjadi?)
-- =====================================================
CREATE TABLE Dim_Waktu (
    id_waktu        SERIAL PRIMARY KEY,
    tanggal_tagihan DATE NOT NULL UNIQUE,
    bulan           VARCHAR(20) NOT NULL,
    bulan_angka     INTEGER NOT NULL,
    kuartal         VARCHAR(5) NOT NULL,
    tahun_kuartal   VARCHAR(10) NOT NULL,   -- "2025-Q1", "2025-Q3"
    hari            VARCHAR(20),
    tahun           INTEGER NOT NULL
);

-- =====================================================
-- DIMENSI 2: Dim_Tenant (Siapa yang ditagih?)
-- =====================================================
CREATE TABLE Dim_Tenant (
    id_tenant        SERIAL PRIMARY KEY,
    nama_perusahaan  VARCHAR(255) NOT NULL,
    sektor_industri  VARCHAR(100) NOT NULL,
    asal_negara      VARCHAR(100) NOT NULL
);

-- =====================================================
-- DIMENSI 3: Dim_Unit_Properti (Di mana unit propertinya?)
-- =====================================================
CREATE TABLE Dim_Unit_Properti (
    id_properti       SERIAL PRIMARY KEY,
    kode_blok         VARCHAR(50) NOT NULL,
    tipe_unit         VARCHAR(100) NOT NULL,
    luas_tanah        NUMERIC(10,2),
    luas_bangunan     NUMERIC(10,2),
    kapasitas_listrik INTEGER
);

-- =====================================================
-- TABEL FAKTA: Fact_Tagihan_Utilitas (Berapa tagihan/pemakaiannya?)
-- =====================================================
CREATE TABLE Fact_Tagihan_Utilitas (
    id_fakta_tagihan  SERIAL PRIMARY KEY,
    id_waktu          INTEGER NOT NULL REFERENCES Dim_Waktu(id_waktu),
    id_tenant         INTEGER NOT NULL REFERENCES Dim_Tenant(id_tenant),
    id_properti       INTEGER NOT NULL REFERENCES Dim_Unit_Properti(id_properti),
    pemakaian_listrik NUMERIC(12,2) NOT NULL CHECK (pemakaian_listrik >= 0),
    tagihan_listrik   NUMERIC(15,2) NOT NULL,
    pemakaian_air     NUMERIC(12,2) NOT NULL CHECK (pemakaian_air >= 0),
    tagihan_air       NUMERIC(15,2) NOT NULL,
    service_charge    NUMERIC(15,2) NOT NULL,
    pajak_pju         NUMERIC(15,2) NOT NULL,
    biaya_akhir       NUMERIC(15,2) NOT NULL,
    etl_loaded_at     TIMESTAMP DEFAULT NOW()
);