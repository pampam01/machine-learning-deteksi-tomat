import cv2
import numpy as np
import os
import sys
import glob
import pickle
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.tree import export_text, plot_tree
import matplotlib.pyplot as plt
from tqdm import tqdm

# ================== FUNGSI EKSTRAKSI FITUR (HISTOGRAM HSV) ==================
def ekstrak_fitur(gambar_path, bins=(8, 8, 4)):
    """
    Membaca gambar, menghitung histogram 3D pada ruang warna HSV.
    Mengembalikan vektor fitur hasil flatten dan normalisasi.
    """
    img = cv2.imread(gambar_path)
    if img is None:
        print(f"Gagal membaca gambar: {gambar_path}")
        return None

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Hitung histogram 3D (H: 0-180, S: 0-256, V: 0-256)
    hist = cv2.calcHist(
        [hsv],
        [0, 1, 2],          # kanal H, S, V
        None,
        bins,               # jumlah bin per kanal
        [0, 180, 0, 256, 0, 256]
    )

    # Normalisasi agar total = 1 (tidak tergantung ukuran gambar)
    hist = cv2.normalize(hist, hist).flatten()

    return hist.tolist()   # list dengan panjang bins[0]*bins[1]*bins[2]

# ================== MEMUAT DATASET ==================
def load_dataset(folder_utama):
    """
    Membaca semua gambar dari subfolder (0,1,2,...) di dalam folder_utama.
    Mengembalikan X (list fitur) dan y (list label).
    """
    X = []
    y = []

    subfolders = [f for f in os.listdir(folder_utama) if os.path.isdir(os.path.join(folder_utama, f))]
    if not subfolders:
        print("Tidak ditemukan subfolder dalam folder utama.")
        return None, None

    for kelas in subfolders:
        kelas_path = os.path.join(folder_utama, kelas)
        pattern = os.path.join(kelas_path, '*.*')
        gambar_files = glob.glob(pattern)
        ekstensi = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        gambar_files = [f for f in gambar_files if f.lower().endswith(ekstensi)]

        print(f"Memproses kelas '{kelas}': {len(gambar_files)} gambar")
        for img_path in tqdm(gambar_files):
            fitur = ekstrak_fitur(img_path)
            if fitur is not None:
                X.append(fitur)
                y.append(kelas)

    return np.array(X), np.array(y)

# ================== LATIH MODEL ==================
def latih_model(X, y, test_size=0.2):
    """
    Membagi data menjadi train/test, melatih DecisionTreeClassifier (C4.5-like),
    dan mengembalikan model terlatih beserta akurasi.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

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
    print(fitur)
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
    # -------------------------------
    # Bagian ini hanya contoh. Anda dapat mengganti dengan mode training
    # atau prediksi sesuai kebutuhan.
    # -------------------------------

    # Contoh: mode training (hilangkan komentar jika ingin melatih ulang)
    # folder_dataset = "d:/PTRIDIKC/clone_github/2026-tiara-deteksi tomat c4.5/crops"
    # if os.path.isdir(folder_dataset):
    #     print(f"Memuat dataset dari folder: {folder_dataset}")
    #     X, y = load_dataset(folder_dataset)
    #     if X is None or len(X) == 0:
    #         print("Dataset kosong. Pastikan folder berisi subfolder dengan gambar.")
    #         sys.exit(1)
    
    #     print(f"Jumlah data: {len(X)}, fitur: {X.shape[1]}, kelas: {set(y)}")
    #     model = latih_model(X, y, test_size=0.2)
    
    #     # Simpan model
    #     with open('model_c45_hist.pkl', 'wb') as f:
    #         pickle.dump(model, f)
    #     print("Model berhasil disimpan sebagai 'model_c45_hist.pkl'")
    # else:
    #     print("Folder dataset tidak ditemukan.")
    #     sys.exit(1)

    # # Contoh: mode prediksi (menggunakan model yang sudah dilatih dengan histogram)
    # if not os.path.exists('model_c45_hist.pkl'):
    #     print("File model 'model_c45_hist.pkl' tidak ditemukan. Latih model terlebih dahulu.")
    #     sys.exit(1)

    with open('model_c45_hist.pkl', 'rb') as f:
        model = pickle.load(f)

        # # Cetak pohon keputusan
        # print("\n" + "=" * 60)
        # print("          POHON KEPUTUSAN C4.5")
        # print("=" * 60)

        # # Karena jumlah fitur histogram banyak, buat nama generik
        # jumlah_fitur = model.n_features_in_
        # fitur_names = [f'fitur_{i}' for i in range(jumlah_fitur)]

        # tree_text = export_text(
        #     model,
        #     feature_names=fitur_names,
        #     decimals=2,
        #     show_weights=False
        # )
        # print(tree_text)
        # print("=" * 60)

        # Prediksi gambar contoh
        prediksi_gambar(
            model,
            "d:/PTRIDIKC/clone_github/2026-tiara-deteksi tomat c4.5/crops/1/mentah-2-_jpg.rf.d845ec40cda6dd66098c6fd68609825e_0.jpg"
        )