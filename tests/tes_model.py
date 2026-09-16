import cv2
import numpy as np
import os
import sys
import glob
import pickle
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from sklearn.tree import export_text, plot_tree # <--- tambahan import matplotlib.pyplot as plt # untuk plot (opsional)
from tqdm import tqdm

# ================== FUNGSI EKSTRAKSI FITUR ==================
def ekstrak_fitur(gambar_path):
    """
    Membaca gambar, menghitung persentase piksel untuk setiap warna (HSV).
    Mengembalikan list: [merah, kuning, hijau, putih, hitam] dalam persen.
    """
    img = cv2.imread(gambar_path)
    if img is None:
        print(f"Gagal membaca gambar: {gambar_path}")
        return None

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    total_piksel = hsv.shape[0] * hsv.shape[1]

    # Rentang warna (HSV)
    # Merah (dua rentang karena melingkar)
    merah_bawah1 = np.array([0, 50, 50])
    merah_atas1   = np.array([10, 255, 255])
    merah_bawah2 = np.array([170, 50, 50])
    merah_atas2   = np.array([180, 255, 255])

    # Kuning
    kuning_bawah = np.array([20, 50, 50])
    kuning_atas   = np.array([30, 255, 255])

    # Hijau
    hijau_bawah = np.array([40, 50, 50])
    hijau_atas   = np.array([70, 255, 255])

    # Putih (S rendah, V tinggi)
    putih_bawah = np.array([0, 0, 200])
    putih_atas   = np.array([180, 30, 255])

    # Hitam (V rendah)
    hitam_bawah = np.array([0, 0, 0])
    hitam_atas   = np.array([180, 255, 30])

    # Mask
    mask_merah1 = cv2.inRange(hsv, merah_bawah1, merah_atas1)
    mask_merah2 = cv2.inRange(hsv, merah_bawah2, merah_atas2)
    mask_merah  = cv2.bitwise_or(mask_merah1, mask_merah2)

    mask_kuning = cv2.inRange(hsv, kuning_bawah, kuning_atas)
    mask_hijau  = cv2.inRange(hsv, hijau_bawah, hijau_atas)
    mask_putih  = cv2.inRange(hsv, putih_bawah, putih_atas)
    mask_hitam  = cv2.inRange(hsv, hitam_bawah, hitam_atas)

    # Jumlah piksel per warna
    jml_merah  = cv2.countNonZero(mask_merah)
    jml_kuning = cv2.countNonZero(mask_kuning)
    jml_hijau  = cv2.countNonZero(mask_hijau)
    jml_putih  = cv2.countNonZero(mask_putih)
    jml_hitam  = cv2.countNonZero(mask_hitam)

    # Persentase
    persen_merah  = (jml_merah / total_piksel) * 100
    persen_kuning = (jml_kuning / total_piksel) * 100
    persen_hijau  = (jml_hijau / total_piksel) * 100
    persen_putih  = (jml_putih / total_piksel) * 100
    persen_hitam  = (jml_hitam / total_piksel) * 100

    return [persen_merah, persen_kuning, persen_hijau, persen_putih, persen_hitam]

# ================== MEMUAT DATASET ==================
def load_dataset(folder_utama):
    """
    Membaca semua gambar dari subfolder (0,1,2,...) di dalam folder_utama.
    Mengembalikan X (list fitur) dan y (list label).
    """
    X = []
    y = []
    
    # Cari semua subfolder (anggap setiap subfolder adalah kelas)
    subfolders = [f for f in os.listdir(folder_utama) if os.path.isdir(os.path.join(folder_utama, f))]
    if not subfolders:
        print("Tidak ditemukan subfolder dalam folder utama.")
        return None, None

    for kelas in subfolders:
        kelas_path = os.path.join(folder_utama, kelas)
        # Ambil semua file gambar (ekstensi umum)
        pattern = os.path.join(kelas_path, '*.*')
        gambar_files = glob.glob(pattern)
        # Filter ekstensi gambar
        ekstensi = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        gambar_files = [f for f in gambar_files if f.lower().endswith(ekstensi)]
        
        print(f"Memproses kelas '{kelas}': {len(gambar_files)} gambar")
        for img_path in tqdm(gambar_files):
            fitur = ekstrak_fitur(img_path)
            if fitur is not None:
                X.append(fitur)
                y.append(kelas)  # label berupa string (nama folder)

    return np.array(X), np.array(y)

# ================== LATIH MODEL ==================
def latih_model(X, y, test_size=0.2):
    """
    Membagi data menjadi train/test, melatih DecisionTreeClassifier (C4.5-like),
    dan mengembalikan model terlatih beserta akurasi.
    """
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    
    # Model Decision Tree dengan kriteria entropy (mirip C4.5)
    model = DecisionTreeClassifier(
        criterion='entropy',   # entropy = gain informasi, mendekati C4.5
        splitter='best',
        random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluasi
    y_pred = model.predict(X_test)
    akurasi = accuracy_score(y_test, y_pred)
    print("\n=== Evaluasi Model ===")
    print(f"Akurasi pada data uji: {akurasi:.2f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    return model

# ================== PREDIKSI GAMBAR BARU ==================
def prediksi_gambar(model, gambar_path):
    """Memprediksi kelas dari satu gambar."""
    fitur = ekstrak_fitur(gambar_path)
    if fitur is None:
        print("Gagal memproses gambar.")
        return None
    fitur = np.array(fitur).reshape(1, -1)
    pred = model.predict(fitur)
    proba = model.predict_proba(fitur)
    print(f"\nHasil prediksi untuk {gambar_path}:")
    print(f"Kelas: {pred[0]}")
    print(f"Probabilitas: {dict(zip(model.classes_, proba[0]))}")
    return pred[0]

# ================== MAIN ==================
if __name__ == "__main__":


    # arg ="d:/PTRIDIKC/clone_github/2026-tiara-deteksi tomat c4.5/crops"

    # if os.path.isdir(arg):
    #     # Mode TRAINING
    #     print(f"Memuat dataset dari folder: {arg}")
    #     X, y = load_dataset(arg)
    #     if X is None or len(X) == 0:
    #         print("Dataset kosong. Pastikan folder berisi subfolder dengan gambar.")
    #         sys.exit(1)

    #     print(f"Jumlah data: {len(X)}, fitur: {X.shape[1]}, kelas: {set(y)}")
    #     model = latih_model(X, y, test_size=0.2)

    #     # Simpan model
    #     with open('model_c45.pkl', 'wb') as f:
    #         pickle.dump(model, f)
    #     print("Model berhasil disimpan sebagai 'model_c45.pkl'")

    # else:
    #     # Mode PREDIKSI (argumen adalah path gambar)
    #     if not os.path.isfile(arg):
    #         print(f"File tidak ditemukan: {arg}")
    #         sys.exit(1)

    #     # Muat model yang sudah dilatih
    #     if not os.path.exists('model_c45.pkl'):
    #         print("File model 'model_c45.pkl' tidak ditemukan. Latih model terlebih dahulu.")
    #         sys.exit(1)

        with open('model_c45.pkl', 'rb') as f:

           


            model = pickle.load(f)

            # ----------------- CETAK POHON -----------------
            print("\n" + "=" * 60)
            print("          POHON KEPUTUSAN C4.5")
            print("=" * 60)
            
            fitur_names = ['merah', 'kuning', 'hijau', 'putih', 'hitam']
            
            tree_text = export_text(
                            model,
                            feature_names=fitur_names,
                            decimals=2,
                            show_weights=False
                        )
            
            print(tree_text)
            print("=" * 60)

            prediksi_gambar(model, "d:/PTRIDIKC/clone_github/2026-tiara-deteksi tomat c4.5/crops/1/mentah-2-_jpg.rf.d845ec40cda6dd66098c6fd68609825e_0.jpg")