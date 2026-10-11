# Pengembangan engine dan fitur peninjauan

## Fitur yang ditambahkan

- **RTL multi-kolom:** kolom mengikuti dominasi huruf Arab/Latin pada halaman;
  header Latin tidak mengalahkan isi Arab. Blok yang beririsan secara vertikal
  dengan pemisah lintas kolom tidak lagi hilang dari hasil.
- **Integritas rekursif:** paragraf anak daftar, catatan kaki, dan isi tabel
  ikut diperiksa. Deteksi font Arab EPUB juga mencakup blok anak dan tabel.
- **Pemeriksaan kualitas:** total/jenis blok, blok disunting, blok perlu ditinjau,
  ringkasan per halaman, ID berulang, isi kosong, dan resource gambar/sampul
  yang tidak tersedia. Masalah struktur berat menghentikan ekspor API/UI.
- **Editor struktur:** ubah paragraf ↔ judul ↔ kutipan; pilih H1–H6, pindahkan
  blok atas/bawah dalam kelompok yang sama, dan sunting paragraf anak daftar
  serta catatan kaki. Isi sumber tidak dibuat ulang; cadangan sebelum suntingan
  pertama tetap dapat dipulihkan. Pemulihan isi tidak memulihkan posisi urutan.
- **Aksesibilitas gambar:** deskripsi alternatif dapat disimpan dan ikut EPUB;
  tanda kutip dan karakter XML pada deskripsi di-escape dengan aman.
- **Navigasi buku:** outline judul di workspace dan daftar isi EPUB bertingkat
  dengan tautan ke anchor H1–H6. Judul top-level dipakai untuk daftar isi;
  judul yang berada di dalam catatan kaki/daftar bukan bab baru.
- **OCR:** mode native/otomatis/paksa, pemilihan mesin dan bahasa, pemeriksaan
  binary/data bahasa, PaddleOCR v2/v3, timeout Tesseract, confidence blok,
  dan keputusan OCR per halaman. Mode paksa bukan pilihan default.
- **EPUBCheck W3C:** pilihan validasi tambahan pada unduhan bila Java dan
  `EPUBCHECK_JAR` tersedia. Default tetap validasi struktur internal.

## Menjalankan localhost di Windows

Prasyarat: dependency Python ada di `.venv` dan `npm ci` sudah dijalankan
di `apps/web`.

```powershell
# Dari root proyek; tidak mengubah instalasi sistem
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1

# Saat Anda ingin menghentikannya
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

- Web: `http://localhost:3000` / `http://127.0.0.1:3000`.
- API/docs: `http://127.0.0.1:8000/docs`.
- Health: `http://127.0.0.1:8000/api/v1/health`.
- Kesiapan OCR/validator: `http://127.0.0.1:8000/api/v1/capabilities`.
- Dokumen, model lokal, log, dan catatan PID berada di `.local-data` (diabaikan
  Git). PDF pengguna tidak diunggah ke layanan OCR/AI eksternal.
- Script menolak port yang sudah digunakan dan tidak menghentikan server lain.
  API memakai satu proses; restart setelah perubahan kode Python. Web memakai
  Next.js dev dengan hot reload. Kedua server hanya bind loopback.
- Port alternatif: `scripts/start-local.ps1 -WebPort 3001 -ApiPort 8001`.

## Konfigurasi OCR lokal

Tesseract binary terdeteksi dari `TESSERACT_CMD`, PATH, atau lokasi standar
Windows `Program Files/Tesseract-OCR`. Model Arab/Indonesia/Inggris disimpan
di `.local-data/tessdata`, bukan ditulis ke Program Files. Starter mengaktifkan
`TESSDATA_PREFIX` jika ketiga model tersedia. Repo tidak membundel model tersebut;
di mesin lain, pasang sendiri model `ara/ind/eng` dari proyek Tesseract.

Data bahasa yang dipasang lokal berasal dari `tesseract-ocr/tessdata_fast`
(Apache-2.0; salinan lisensi ada di folder model). Memasang model memerlukan
unduhan awal, tetapi pengenalan dokumen berjalan lokal. PaddleOCR belum
dipasang; pengecekan kesiapan tidak mengunduh model Paddle secara otomatis.

## Konfigurasi validator W3C

Set `EPUBCHECK_JAR` ke JAR EPUBCheck beserta folder dependensinya dan pastikan
Java tersedia. Starter juga mengenali instalasi EPUBCheck 5.2.1 pada folder
temporary OpenCode lokal bila tersedia. `POST .../export/epub?validation=w3c`
menolak paket yang gagal validasi; jika validator belum siap, respons 503
menjelaskan konfigurasi yang dibutuhkan. Checkbox W3C tidak mengubah teks buku.

## Pengujian

Tes engine/API mencakup RTL kolom, blok yang beririsan, integritas rekursif,
perubahan jenis/level, pemindahan, pemulihan, resource/isi kosong, mode OCR,
adapter Paddle tanpa mengunduh model, bahasa Tesseract, dan daftar isi EPUB.
Tes browser mencakup editor struktur, blok catatan kaki, deskripsi gambar,
dan penjelasan kesiapan OCR selain alur unggah hingga unduh.

OCR nyata telah diuji pada fixture pindai: 4 blok teks terpulihkan dengan mean
confidence 0,91. Ini bukan jaminan akurasi pada buku lain, khususnya harakat,
font kompleks, tabel tanpa garis, atau dokumen pindai berkualitas rendah.
Selalu bandingkan hasil dengan PDF sumber.

Hasil validasi iterasi ini: **267 tes Python lulus** (termasuk EPUBCheck W3C,
tanpa skip pada lingkungan dengan JAR yang dikonfigurasi), **12 tes frontend**
dan **13 tes browser production** lulus. Build/TypeScript dan schema check juga
lulus. Golden/snapshot Arabic yang disetujui tidak diubah. Satu warning
deprecation dari Starlette/httpx masih muncul, tidak menggagalkan tes.

Server localhost juga diuji langsung melalui HTTP: upload fixture pindai,
konversi otomatis Tesseract, pengambilan laporan, dan ekspor `validation=w3c`
berhasil (200). Web merespons 200 dan endpoint health berstatus `ok`.

## Batasan yang tetap ada

### Perbaikan teks dan pemulihan dari panel utama

Setelah memilih paragraf, judul, atau kutipan, editor langsung menampilkan
**Perbaiki teks**, **Jadikan gambar**, dan **Pulihkan teks awal** di atas kolom
suntingan. Aksi gambar tersedia untuk teks Arab maupun Latin yang mempunyai
halaman sumber. Tombol pemulihan aktif setelah cadangan sebelum suntingan pertama
tersimpan; pemulihan juga bisa mengembalikan blok gambar menjadi teks.

**Perbaiki otomatis blok bermasalah** di bagian atas editor memproses kandidat
pada seluruh dokumen, termasuk paragraf anak catatan kaki/daftar. Blok yang
sudah disunting dilewati. Hasil melaporkan jumlah blok berubah, tanpa perubahan
yang aman, dilewati, dan tetap perlu ditinjau. Suntingan belum tersimpan harus
disimpan atau dibatalkan sebelum menjalankan aksi.

Perbaikan melipat bentuk huruf/ligatur kompatibilitas secara per karakter,
menghapus karakter yang tidak bisa direpresentasikan XML, serta memperbaiki
penanda RTL dan isolasi teks campuran. Urutan harakat yang sudah ada tetap
dipertahankan. Sumber sebelum perubahan tersimpan untuk pemulihan dan provenance.
Tidak ada penebakan kata OCR, penggabungan huruf Arab berjarak, pembalikan teks,
atau klaim semua warning selesai. PDF sumber tidak berubah.

Tes tambahan mencakup perbaikan berulang tanpa perubahan, harakat, teks
campuran, cadangan pertama, batch yang melewati suntingan, ID tidak dikenal,
blok anak, pemulihan sesudah gambar, serta kontrol utama melalui browser.

### Fitur yang belum tersedia

Belum ada deteksi/pemisahan bab otomatis, editor sel tabel, penggabungan/pemisahan
blok, undo urutan bertahap, cancel job, antrean lintas proses, autentikasi, atau
retensi otomatis. Model Paddle dan performa buku sangat besar belum diuji nyata.
Backend ini ditujukan untuk localhost/self-hosted satu proses, bukan layanan
publik multi-pengguna tanpa hardening tambahan.
