# Folder Pengujian & Analisis (Tests)

Folder ini berisi script pengujian mandiri dan alat bantu analisis untuk sistem pemilah tomat C4.5:

| File Script | Deskripsi & Kegunaan |
| :--- | :--- |
| **`tes_servo_manual.py`** | Antarmuka CLI interaktif untuk menguji respon sudut dan gerakan S-Curve Servo 1 & 2 pada ESP32 secara manual. |
| **`TES_VISUAL_HSV.py`** | Visualisasi 3D interaktif sebaran fitur histogram warna HSV menggunakan scatter plot OpenCV. |
| **`tes_model_hstogram.py`** | Script pelatihan dan evaluasi model C4.5 (Decision Tree) berbasis fitur histogram HSV 3D. |
| **`tes_model.py`** | Script eksperimen awal klasifikasi Decision Tree berbasis persentase warna sederhana. |
| **`tse_warna.py`** | Script pengujian segmentasi rentang warna HSV pada gambar sampel tomat. |

### Cara Menjalankan Script Test
Script dapat dijalankan langsung dari root proyek maupun dari dalam folder `tests`:
```bash
# Contoh menguji servo manual ESP32:
python tests/tes_servo_manual.py

# Contoh visualisasi fitur HSV:
python tests/TES_VISUAL_HSV.py
```
