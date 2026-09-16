import cv2
import numpy as np
import pickle
import os

# ============================================================
# KONFIGURASI
# ============================================================
MODEL_PATH = "model_c45_hist.pkl"
BINS_HSV = (8, 8, 4)

JUMLAH_FITUR = BINS_HSV[0] * BINS_HSV[1] * BINS_HSV[2]
NAMA_FITUR = [f"fitur_{i}" for i in range(JUMLAH_FITUR)]

UKURAN_FRAME = (800, 600)
SCATTER_SIZE = 350

# ============================================================
# ROTASI 3D
# ============================================================
azimuth = np.deg2rad(30)
elevasi = np.deg2rad(20)

dragging = False
last_x = 0
last_y = 0


# ============================================================
# MOUSE CALLBACK
# ============================================================
def mouse_callback(event, x, y, flags, param):
    global azimuth, elevasi
    global dragging, last_x, last_y

    if event == cv2.EVENT_LBUTTONDOWN:
        dragging = True
        last_x = x
        last_y = y

    elif event == cv2.EVENT_MOUSEMOVE:
        if dragging:

            dx = x - last_x
            dy = y - last_y

            azimuth += dx * 0.01
            elevasi += dy * 0.01

            elevasi = np.clip(
                elevasi,
                -np.pi / 2,
                np.pi / 2
            )

            last_x = x
            last_y = y

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False


# ============================================================
# EKSTRAKSI FITUR HISTOGRAM HSV
# ============================================================
def ekstrak_fitur_frame(img):

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    hist = cv2.calcHist(
        [hsv],
        [0, 1, 2],
        None,
        BINS_HSV,
        [0, 180, 0, 256, 0, 256]
    )

    hist = cv2.normalize(
        hist,
        hist
    ).flatten()

    return hist.tolist()


# ============================================================
# TELUSURI DECISION TREE
# ============================================================
def telusuri_tree(model, fitur):

    tree = model.tree_

    node = 0
    langkah = []
    nomor = 1

    while tree.children_left[node] != tree.children_right[node]:

        index_fitur = tree.feature[node]
        threshold = tree.threshold[node]

        nama = NAMA_FITUR[index_fitur]
        nilai = fitur[index_fitur]

        if nilai <= threshold:

            kondisi = (
                f"{nama} <= {threshold:.4f}"
            )

            perbandingan = (
                f"{nilai:.4f} <= {threshold:.4f}"
            )

            node = tree.children_left[node]

        else:

            kondisi = (
                f"{nama} > {threshold:.4f}"
            )

            perbandingan = (
                f"{nilai:.4f} > {threshold:.4f}"
            )

            node = tree.children_right[node]

        langkah.append({
            "nomor": nomor,
            "kondisi": kondisi,
            "perbandingan": perbandingan,
            "keputusan": "YA"
        })

        nomor += 1

    kelas_index = np.argmax(
        tree.value[node][0]
    )

    hasil = model.classes_[kelas_index]

    return langkah, hasil


# ============================================================
# PROYEKSI HSV KE RUANG 3D
#
# H = SUDUT
# S = RADIUS
# V = TINGGI
#
# Ini adalah representasi HSV yang lebih benar.
# ============================================================
def hsv_ke_xyz(h, s, v):

    # OpenCV:
    # H = 0 ... 180
    # S = 0 ... 255
    # V = 0 ... 255

    # Hue menjadi sudut 0 ... 2PI
    theta = (h / 180.0) * 2.0 * np.pi

    # Saturation menjadi radius
    radius = s / 255.0

    # Value menjadi tinggi
    tinggi = v / 255.0

    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    z = tinggi

    return x, y, z


# ============================================================
# PROYEKSI 3D KE LAYAR
# ============================================================
def proyeksikan_3d(x, y, z):

    # -------------------------
    # Rotasi azimuth
    # -------------------------
    x1 = (
        x * np.cos(azimuth)
        - y * np.sin(azimuth)
    )

    y1 = (
        x * np.sin(azimuth)
        + y * np.cos(azimuth)
    )

    z1 = z

    # -------------------------
    # Rotasi elevasi
    # -------------------------
    y2 = (
        y1 * np.cos(elevasi)
        - z1 * np.sin(elevasi)
    )

    z2 = (
        y1 * np.sin(elevasi)
        + z1 * np.cos(elevasi)
    )

    return x1, y2, z2


# ============================================================
# GAMBAR GRID HSV
# ============================================================
def gambar_grid_hsv(panel, cx, cy, skala):

    # ========================================================
    # LINGKARAN HUE
    # ========================================================

    jumlah = 72

    titik = []

    for i in range(jumlah + 1):

        h = (i / jumlah) * 180.0

        x, y, z = hsv_ke_xyz(
            h,
            255,
            0
        )

        xp, yp, zp = proyeksikan_3d(
            x,
            y,
            z
        )

        sx = int(cx + xp * skala)
        sy = int(cy - yp * skala)

        titik.append((sx, sy))

    for i in range(len(titik) - 1):

        cv2.line(
            panel,
            titik[i],
            titik[i + 1],
            (90, 90, 90),
            1
        )

    # ========================================================
    # LINGKARAN SATURATION
    # ========================================================

    for radius in [0.25, 0.5, 0.75, 1.0]:

        titik = []

        for i in range(jumlah + 1):

            h = (i / jumlah) * 180.0
            s = radius * 255.0

            x, y, z = hsv_ke_xyz(
                h,
                s,
                0
            )

            xp, yp, zp = proyeksikan_3d(
                x,
                y,
                z
            )

            sx = int(cx + xp * skala)
            sy = int(cy - yp * skala)

            titik.append((sx, sy))

        for i in range(len(titik) - 1):

            cv2.line(
                panel,
                titik[i],
                titik[i + 1],
                (60, 60, 60),
                1
            )

    # ========================================================
    # GARIS V
    # ========================================================

    for i in range(8):

        v = (i / 7.0) * 255.0

        x, y, z = hsv_ke_xyz(
            0,
            255,
            v
        )

        xp, yp, zp = proyeksikan_3d(
            x,
            y,
            z
        )

        sx = int(cx + xp * skala)
        sy = int(cy - yp * skala)

        if i > 0:

            cv2.line(
                panel,
                prev,
                (sx, sy),
                (70, 70, 70),
                1
            )

        prev = (sx, sy)


# ============================================================
# SCATTER HSV 3D
# ============================================================
def gambar_scatter_3d_panel(
        panel,
        fitur,
        pos=(20, 80),
        ukuran=350):

    x0, y0 = pos

    w = ukuran
    h = ukuran

    cx = x0 + w // 2
    cy = y0 + h // 2

    # ========================================================
    # BACKGROUND
    # ========================================================

    cv2.rectangle(
        panel,
        (x0, y0),
        (x0 + w, y0 + h),
        (25, 25, 25),
        -1
    )

    cv2.rectangle(
        panel,
        (x0, y0),
        (x0 + w, y0 + h),
        (120, 120, 120),
        1
    )

    # ========================================================
    # HISTOGRAM
    # ========================================================

    hist_3d = np.array(
        fitur
    ).reshape(BINS_HSV)

    mean_val = np.mean(hist_3d)
    std_val = np.std(hist_3d)

    threshold = (
        mean_val
        + 0.5 * std_val
    )

    bin_indices = np.argwhere(
        hist_3d > threshold
    )

    if len(bin_indices) == 0:

        cv2.putText(
            panel,
            "No significant bins",
            (x0 + 10, y0 + h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )

        return

    # ========================================================
    # SKALA
    # ========================================================

    skala = w * 0.38

    # ========================================================
    # GRID HSV
    # ========================================================

    gambar_grid_hsv(
        panel,
        cx,
        cy,
        skala
    )

    # ========================================================
    # SUMBU V
    # ========================================================

    x, y, z = hsv_ke_xyz(
        0,
        0,
        255
    )

    xp, yp, zp = proyeksikan_3d(
        x,
        y,
        z
    )

    v_end = (
        int(cx + xp * skala),
        int(cy - yp * skala)
    )

    cv2.line(
        panel,
        (cx, cy),
        v_end,
        (255, 255, 255),
        2
    )

    cv2.putText(
        panel,
        "V",
        (
            v_end[0] + 5,
            v_end[1]
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
    )

    # ========================================================
    # LABEL HUE
    # ========================================================

    label_hue = [
        (0, "RED"),
        (30, "YELLOW"),
        (60, "GREEN"),
        (90, "CYAN"),
        (120, "BLUE"),
        (150, "MAGENTA")
    ]

    for h_value, label in label_hue:

        x, y, z = hsv_ke_xyz(
            h_value,
            255,
            0
        )

        xp, yp, zp = proyeksikan_3d(
            x,
            y,
            z
        )

        sx = int(cx + xp * skala)
        sy = int(cy - yp * skala)

        cv2.putText(
            panel,
            label,
            (sx - 15, sy - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (220, 220, 220),
            1
        )

    # ========================================================
    # BIN HISTOGRAM
    # ========================================================

    h_bin_width = (
        180 / BINS_HSV[0]
    )

    s_bin_width = (
        256 / BINS_HSV[1]
    )

    v_bin_width = (
        256 / BINS_HSV[2]
    )

    # ========================================================
    # SORT BERDASARKAN DEPTH
    # Agar titik belakang digambar lebih dahulu
    # ========================================================

    titik_data = []

    for idx in bin_indices:

        i_h, i_s, i_v = idx

        h_val = (
            i_h + 0.5
        ) * h_bin_width

        s_val = (
            i_s + 0.5
        ) * s_bin_width

        v_val = (
            i_v + 0.5
        ) * v_bin_width

        frek = hist_3d[
            i_h,
            i_s,
            i_v
        ]

        x, y, z = hsv_ke_xyz(
            h_val,
            s_val,
            v_val
        )

        xp, yp, zp = proyeksikan_3d(
            x,
            y,
            z
        )

        titik_data.append(
            (
                zp,
                xp,
                yp,
                h_val,
                s_val,
                v_val,
                frek
            )
        )

    titik_data.sort(
        key=lambda a: a[0]
    )

    # ========================================================
    # GAMBAR TITIK
    # ========================================================

    for data in titik_data:

        (
            depth,
            xp,
            yp,
            h_val,
            s_val,
            v_val,
            frek
        ) = data

        sx = int(
            cx + xp * skala
        )

        sy = int(
            cy - yp * skala
        )

        # warna asli dari HSV
        hsv_color = np.array(
            [
                [
                    [
                        int(h_val),
                        int(s_val),
                        int(v_val)
                    ]
                ]
            ],
            dtype=np.uint8
        )

        bgr = cv2.cvtColor(
            hsv_color,
            cv2.COLOR_HSV2BGR
        )[0][0]

        warna = (
            int(bgr[0]),
            int(bgr[1]),
            int(bgr[2])
        )

        radius = int(
            2
            + (frek - threshold) * 200
        )

        radius = max(
            2,
            min(radius, 10)
        )

        # titik
        cv2.circle(
            panel,
            (sx, sy),
            radius,
            warna,
            -1
        )

        # outline
        cv2.circle(
            panel,
            (sx, sy),
            radius,
            (255, 255, 255),
            1
        )

    # ========================================================
    # INFORMASI
    # ========================================================

    cv2.putText(
        panel,
        "H = angle",
        (x0 + 10, y0 + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (220, 220, 220),
        1
    )

    cv2.putText(
        panel,
        "S = radius",
        (x0 + 10, y0 + 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (220, 220, 220),
        1
    )

    cv2.putText(
        panel,
        "V = height",
        (x0 + 10, y0 + 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (220, 220, 220),
        1
    )

    cv2.putText(
        panel,
        f"Bins: {len(bin_indices)}",
        (x0 + 10, y0 + h - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (200, 200, 200),
        1
    )


# ============================================================
# TAMPILKAN
# ============================================================
def tampilkan(
        frame,
        fitur,
        langkah,
        hasil):

    tinggi, lebar = frame.shape[:2]

    panel_lebar = 600

    panel = np.zeros(
        (
            tinggi,
            panel_lebar,
            3
        ),
        dtype=np.uint8
    )

    panel[:] = (
        30,
        30,
        30
    )

    # ========================================================
    # JUDUL
    # ========================================================

    cv2.putText(
        panel,
        "C4.5 REALTIME",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    cv2.putText(
        panel,
        "HSV CYLINDRICAL COLOR SPACE",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1
    )

    # ========================================================
    # SCATTER
    # ========================================================

    x_scatter = (
        panel_lebar
        - SCATTER_SIZE
    ) // 2

    y_scatter = 80

    gambar_scatter_3d_panel(
        panel,
        fitur,
        pos=(
            x_scatter,
            y_scatter
        ),
        ukuran=SCATTER_SIZE
    )

    # ========================================================
    # STATISTIK
    # ========================================================

    y_info = (
        y_scatter
        + SCATTER_SIZE
        + 15
    )

    cv2.putText(
        panel,
        "Statistik Warna:",
        (20, y_info),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 255),
        1
    )

    y_info += 25

    hist_3d = np.array(
        fitur
    ).reshape(BINS_HSV)

    h_bin_centers = (
        np.arange(BINS_HSV[0])
        + 0.5
    ) * (
        180 / BINS_HSV[0]
    )

    s_bin_centers = (
        np.arange(BINS_HSV[1])
        + 0.5
    ) * (
        256 / BINS_HSV[1]
    )

    v_bin_centers = (
        np.arange(BINS_HSV[2])
        + 0.5
    ) * (
        256 / BINS_HSV[2]
    )

    total = np.sum(hist_3d)

    if total > 0:

        h_mean = np.sum(
            hist_3d
            * h_bin_centers[
                :, None, None
            ]
        ) / total

        s_mean = np.sum(
            hist_3d
            * s_bin_centers[
                None, :, None
            ]
        ) / total

        v_mean = np.sum(
            hist_3d
            * v_bin_centers[
                None, None, :
            ]
        ) / total

        cv2.putText(
            panel,
            f"H mean: {h_mean:.1f}  "
            f"S mean: {s_mean:.1f}  "
            f"V mean: {v_mean:.1f}",
            (20, y_info),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

        y_info += 25

    # ========================================================
    # GARIS PEMISAH
    # ========================================================

    y_garis = y_info + 5

    cv2.line(
        panel,
        (20, y_garis),
        (580, y_garis),
        (100, 100, 100),
        1
    )

    # ========================================================
    # HASIL
    # ========================================================

    kotak_hasil_y1 = tinggi - 80
    kotak_hasil_y2 = tinggi - 20

    cv2.rectangle(
        panel,
        (15, kotak_hasil_y1),
        (585, kotak_hasil_y2),
        (60, 60, 60),
        -1
    )

    cv2.rectangle(
        panel,
        (15, kotak_hasil_y1),
        (585, kotak_hasil_y2),
        (0, 255, 0),
        2
    )

    cv2.putText(
        panel,
        "KESIMPULAN:",
        (30, kotak_hasil_y1 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    cv2.putText(
        panel,
        str(hasil),
        (180, kotak_hasil_y1 + 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 0),
        2
    )

    # ========================================================
    # GABUNG
    # ========================================================

    output = np.hstack(
        (
            frame,
            panel
        )
    )

    return output


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":

    # ========================================================
    # LOAD MODEL
    # ========================================================

    try:

        with open(
            MODEL_PATH,
            "rb"
        ) as f:

            model = pickle.load(f)

    except Exception as e:

        print(
            "Gagal membuka model:",
            e
        )

        print(
            "Pastikan model sudah dilatih "
            "dengan fitur histogram HSV."
        )

        exit()

    print("=" * 60)

    print(
        "MODEL C4.5 "
        "(HISTOGRAM HSV) BERHASIL DIMUAT"
    )

    print("Kelas:")

    for kelas in model.classes_:

        print(
            " -",
            kelas
        )

    print()

    print(
        "Tekan Q untuk keluar."
    )

    print(
        "Drag mouse pada area HSV "
        "untuk memutar."
    )

    print("=" * 60)

    # ========================================================
    # KAMERA
    # ========================================================

    kamera = cv2.VideoCapture(0)

    if not kamera.isOpened():

        print(
            "Kamera tidak dapat dibuka."
        )

        exit()

    kamera.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    kamera.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    # ========================================================
    # WINDOW
    # ========================================================

    window_name = (
        "C4.5 - Deteksi Realtime "
        "(HSV Cylindrical)"
    )

    cv2.namedWindow(
        window_name
    )

    cv2.setMouseCallback(
        window_name,
        mouse_callback
    )

    # ========================================================
    # LOOP
    # ========================================================

    while True:

        ret, frame = kamera.read()

        if not ret:

            print(
                "Gagal mengambil frame."
            )

            break

        frame = cv2.flip(
            frame,
            1
        )

        frame = cv2.resize(
            frame,
            UKURAN_FRAME
        )

        # --------------------------------
        # EKSTRAKSI
        # --------------------------------

        fitur = ekstrak_fitur_frame(
            frame
        )

        # --------------------------------
        # DECISION TREE
        # --------------------------------

        langkah, hasil = telusuri_tree(
            model,
            fitur
        )

        # --------------------------------
        # TAMPILKAN
        # --------------------------------

        output = tampilkan(
            frame,
            fitur,
            langkah,
            hasil
        )

        cv2.imshow(
            window_name,
            output
        )

        tombol = (
            cv2.waitKey(1)
            & 0xFF
        )

        if tombol == ord("q"):

            break

    # ========================================================
    # CLEANUP
    # ========================================================

    kamera.release()

    cv2.destroyAllWindows()