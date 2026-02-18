SXWordPress Shooter V.10 - sxtools
==================================

SXWordPress Shooter adalah tool CLI sederhana untuk melakukan bruteforce login WordPress
berbasis file payload dan multi-thread.

Tool ini dibuat untuk kebutuhan audit keamanan terhadap instalasi WordPress yang Anda miliki
sendiri atau yang Anda miliki izin eksplisit untuk mengujinya.


Fitur
-----
- Membaca target dari file payload (`.txt`)
- Format payload: `https://domain.com:username:password`
- Multi-threaded login attempt
- Deteksi sukses login berdasarkan cookie `wordpress_logged_in`
- Deteksi role sederhana:
  - ADMIN: bisa mengakses `/wp-admin/` tanpa pesan "tidak punya akses"
  - USER: login sukses tapi tidak punya hak akses penuh ke dashboard
- Menyimpan kombinasi yang vuln ke folder `output/` pada file `vuln.txt`


Instalasi
---------
Pastikan Python 3 sudah terpasang dan modul `requests` tersedia.

Contoh instalasi cepat:

```bash
pip install requests
```


Penggunaan
----------
Jalankan dari direktori project:

```bash
python sxwp.py -i target.txt -t 10
```

Parameter:
- `-i, --input`    : path ke file payload (wajib)
- `-t, --threads`  : jumlah thread worker (opsional, default 10)
- `-path, --path`  : path instalasi WordPress, contoh `/blog` (opsional)

Format file `target.txt`:

```text
https://example.com:admin:password123
https://example.org:user@example.org:SuperSecret!
```

Jika Anda menggunakan `-path`, maka URL di payload sebaiknya hanya domain/root,
contoh:

```text
https://example.com:admin:password123      # dan jalankan dengan: -path /blog
```


Help
----
Untuk melihat help dan opsi yang tersedia:

```bash
python sxwp.py -h
```

Jika argumen yang diberikan salah atau kurang, help dan usage akan ditampilkan secara otomatis.


Output
------
- Folder `output/` akan berisi sub-folder per eksekusi dengan pola nama `sxwp-vuln-YYYYMMDD-HHMMSS/`.
- Di dalam setiap folder terdapat:
  - `admin.txt` : semua kombinasi yang berhasil login dan terdeteksi sebagai ADMIN.
  - `user.txt`  : semua kombinasi yang berhasil login dan terdeteksi sebagai USER.
- Setiap baris file tersebut berisi payload yang berhasil (format sama seperti input).


Catatan
-------
- Gunakan tool ini hanya pada sistem yang Anda miliki atau telah diberi izin resmi.
- Penulis tidak bertanggung jawab atas penyalahgunaan tool ini.
