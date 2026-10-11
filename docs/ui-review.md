# Panduan UI dan pemeriksaan regresi

## Alur penggunaan

1. **Unggah** satu PDF, maksimal 100 MB. Berkas kosong, format lain, dan PDF
   terenkripsi ditolak. Tarik-lepas dan pemilihan berkas sama-sama tersedia.
2. **Konversi** setelah analisis halaman tampil. Pilih OCR untuk halaman
   pindai; mesin OCR harus terpasang di server. Progres diperbarui otomatis.
   Jika gagal, penyebab dan tombol coba lagi tetap tersedia.
3. **Tinjau** dengan PDF sumber, pratinjau EPUB, dan editor blok. Pada layar
   kecil, gunakan tombol PDF sumber / Pratinjau / Sunting blok. Memilih blok
   menyinkronkan halaman sumber. Navigasi halaman, blok sebelumnya/berikutnya,
   pencarian, filter, dan navigasi ke masalah berikutnya tersedia.
4. **Unduh** setelah menyimpan suntingan. Judul, penulis, dan sampul dapat
   diatur pada panel terakhir. EPUB, ReflowDoc JSON, dan laporan kualitas JSON
   dapat diunduh. EPUB tanpa isi tidak dapat diunduh melalui UI.

Riwayat berisi maksimal delapan dokumen yang dibuka dari browser yang sama.
Hanya metadata disimpan di localStorage, bukan PDF atau teks buku. Berkas
server harus tetap tersedia; riwayat bukan perpustakaan atau penyimpanan permanen.

## Perlindungan suntingan

- Simpan atau batalkan suntingan sebelum konversi ulang, tindakan perbaikan,
  penyuntingan identitas buku, atau ekspor.
- Pindah blok dan tautan keluar dari dokumen meminta konfirmasi jika ada
  perubahan belum disimpan. Reload/penutupan tab menggunakan peringatan browser.
- Konversi ulang meminta konfirmasi karena mengganti hasil, suntingan tersimpan,
  identitas buku, sampul, dan cadangan pemulihan blok.
- **Pulihkan teks awal** mengembalikan blok sebelum suntingan pertama, bukan
  undo bertahap. Tindakan hanya ditampilkan jika cadangannya tersedia.
- Normalisasi bentuk huruf dan penggunaan gambar sumber adalah pilihan eksplisit,
  bukan koreksi otomatis. Harakat dan isi sumber tidak dibuat ulang oleh AI.
- Draft belum disimpan tidak dipersistenkan. Jangan mengandalkan tombol Back/Forward
  browser untuk menyimpan draft; gunakan tombol Simpan terlebih dahulu.

## Temuan audit dan perbaikan

| Temuan awal | Dampak | Perbaikan |
| --- | --- | --- |
| Job dokumen mengambil pekerjaan pertama | Konversi ulang tampak selesai padahal masih berjalan | Registry pekerjaan terbaru, snapshot status, dan tes konversi ulang |
| Konversi ganda diizinkan | Penulisan hasil berlomba | Penolakan HTTP 409 dan penguncian mutasi per dokumen |
| Pekerjaan terputus tetap processing setelah restart | Progres macet selamanya | Status failed yang dapat dicoba lagi |
| Tombol konversi hilang setelah gagal | Pengguna tidak dapat melanjutkan | Tombol coba lagi dan pilihan OCR tetap tersedia |
| Draft editor tidak mengikuti pilihan dari preview | Editor kosong atau menyimpan teks blok lain | Editor terikat ke blok terpilih dan versi isi tersimpan |
| Perpindahan/konversi membuang draft tanpa peringatan | Suntingan hilang | Dirty-state guard dan konfirmasi |
| Suntingan paragraf menghapus span RTL/LTR | Tampilan Arab–Latin dapat rusak | Segmentasi inline yang menjaga karakter dan harakat |
| Spasi batas script ikut diisolasi RTL | Kata Arab–Latin terlihat menempel | Spasi batas tetap di konteks paragraf pada preview dan EPUB, urutan karakter tidak berubah |
| Laporan kualitas tidak diperbarui setelah suntingan | Peringatan/skor tidak mencerminkan hasil terkini | Laporan dihitung dari ReflowDoc terkini |
| Peringatan integritas berulang saat normalisasi | Jumlah masalah membesar keliru | Pembaruan anotasi idempoten |
| Normalisasi diklaim reversible tanpa UI pemulihan | Pengguna tidak bisa membatalkan perbaikan | Cadangan sebelum suntingan pertama dan pemulihan eksplisit |
| Pengunduhan tanpa busy-state/catch | Klik ganda dan kegagalan jaringan tidak jelas | Ekspor terkontrol, pesan inline, dan nama berkas dari CORS |
| Pratinjau tabel/daftar hanya placeholder | Pengguna tidak dapat memeriksa isi | Rendering isi tabel, daftar, catatan kaki, dan isolasi inline |
| Halaman sumber tidak mengikuti pilihan blok | Sulit membandingkan teks | Sinkronisasi pilihan dan navigasi halaman langsung |
| Tiga panel menumpuk pada mobile | Alur panjang dan membingungkan | Panel bergantian dan kontrol sentuh yang lebih besar |
| Hasil pindai kosong tetap dapat diunduh di UI | Buku kosong tampak sukses | Empty-state, petunjuk OCR, dan pembatasan unduh |
| Upload dibaca seluruhnya sebelum memeriksa batas | Penggunaan memori tidak terbatas oleh validasi | Pembacaan maksimal batas + satu byte |
| ID dokumen tidak dibatasi di penyimpanan | Risiko akses path di luar dokumen | Validasi ID heksadesimal sebelum akses filesystem |
| JSON ditulis langsung ke berkas aktif | Polling dapat membaca JSON parsial | Penulisan temporer dan atomic replace |
| Tidak ada pengujian frontend otomatis | Bug editor/navigasi mudah berulang | Tes kontrak/client, browser end-to-end, dan CI |
| Nama sumber ekspor mengikuti berkas internal `source.pdf` | Provenance dokumen tidak sesuai unggahan | Nama berkas unggahan dan ID dokumen API dipertahankan di ReflowDoc |
| Traceback kegagalan berpotensi berisi teks hasil ekstraksi | Isi dokumen dapat masuk log server | Log kegagalan hanya mencatat ID job dan jenis exception |

## Pengujian

```bash
# Dari root: engine, API, Arabic golden, dan snapshot regression
python -m pytest
python -m engine.reflowdoc.schema --check

# Dari apps/web
npm ci
npm test
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright menyalakan API terisolasi di `127.0.0.1:8100` dan web di
`127.0.0.1:3100`. Secara default Python diambil dari `.venv` repo; set
`REFLOW_PYTHON` jika menggunakan interpreter lain. Berkas fixture uji ada di
`tests/fixtures`; storage uji di `apps/web/.e2e-storage`, terpisah dari dokumen
pengguna. Kedua port harus bebas. Pengujian gagal menyimpan screenshot dan trace
di `apps/web/test-results`.

CI menjalankan pengujian browser terhadap production build. Untuk menjalankan
mode yang sama secara lokal, build dengan `NEXT_PUBLIC_API_URL` yang menunjuk
ke `http://127.0.0.1:8100`, lalu set `REFLOW_E2E_PRODUCTION=1` saat menjalankan
`npm run test:e2e`. Environment public Next.js dibekukan saat build.

### Hasil validasi audit ini

- Python/engine/API: **241 lulus**, **5 skip**; Arabic golden dan snapshot
  tidak berubah. Empat tes skip karena EPUBCheck JAR/Java belum tersedia;
  satu tes skenario “Tesseract tidak tersedia” skip karena Tesseract terdeteksi.
- Frontend contract/client: **9 lulus**.
- Browser Chromium terhadap production build: **9 lulus**, termasuk ukuran
  mobile, alur unggah hingga unduh, konversi ulang, pemulihan, dan kegagalan jaringan.
- Production build dan pemeriksaan TypeScript: lulus.
- Shared ReflowDoc schema: sesuai model, tanpa perubahan schema.
- `npm audit`: tidak melaporkan kerentanan pada dependency npm yang terpasang.
  Ini bukan audit keamanan menyeluruh terhadap deployment atau dependency Python.

## Batasan yang masih perlu diperhatikan

- OCR nyata bergantung pada binary/model dan language data. Tes kegagalan OCR
  menggunakan respons terkontrol; kualitas OCR nyata belum dijamin.
- Validasi EPUB internal bukan pengganti EPUBCheck W3C. Tes W3C memerlukan
  `EPUBCHECK_JAR` dan Java; pengujian tersebut dapat skip bila tidak tersedia.
- Backend MVP menggunakan filesystem dan thread, **satu proses API**. Belum ada
  antrean lintas proses, kuota resource per pengguna, autentikasi, retensi/cleanup
  dokumen otomatis, atau batas waktu eksekusi konversi. Jangan membuka API ini ke
  internet sebagai layanan multi-pengguna tanpa hardening tambahan.
- Pencarian dan pratinjau masih merender seluruh dokumen di sisi browser; buku
  sangat besar memerlukan paginasi/virtualisasi dan pengujian performa tambahan.
- Tabel, multi-kolom kompleks, font yang rusak, dan teks Arab hasil OCR tetap
  harus dibandingkan dengan PDF. Tidak ada klaim konversi bebas kesalahan.
- Jenis paragraf/judul/kutipan, level judul, urutan antarblok dalam kelompok
  yang sama, deskripsi gambar, dan paragraf anak daftar/catatan kaki dapat
  disunting. Editor sel tabel dan pemindahan item daftar sebagai satu kelompok
  belum disediakan.
- Tes browser saat ini menggunakan Chromium (desktop dan ukuran mobile), bukan
  verifikasi menyeluruh Firefox, Safari, atau pembaca layar.
- Font Google pada `next/font` dilayani lokal setelah build, tetapi build awal
  masih memerlukan akses unduh font. Deployment sepenuhnya offline sebaiknya
  menggunakan font berlisensi yang dibundel melalui `next/font/local`.

Pengembangan engine berikutnya, konfigurasi OCR lokal, dan cara menjalankan
server: lihat [`engine-features.md`](engine-features.md).

Identitas aplikasi memakai artwork asli di `public/brand/arabic-reflow-logo.png`.
Header/footer membingkai simbol buku; halaman unggah dan metadata berbagi memakai
logo lengkap. Ikon browser dan layar utama dibuat dari artwork yang sama.
Untuk deployment, set `NEXT_PUBLIC_SITE_URL` ke URL publik agar metadata berbagi
mengarah ke domain yang benar (default pengembangan: `http://localhost:3000`).
