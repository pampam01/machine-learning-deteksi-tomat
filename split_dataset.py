import os
from PIL import Image

# =========================
# CONFIG
# =========================
ROOT = "d:/PTRIDIKC/clone_github/2026-tiara-deteksi tomat c4.5/Tomato.v3i.yolov8/train"

IMAGE_DIR = os.path.join(ROOT, "images")
LABEL_DIR = os.path.join(ROOT, "labels")
OUTPUT_DIR = os.path.join(ROOT, "crops")


# =========================
# PROCESS
# =========================
os.makedirs(OUTPUT_DIR, exist_ok=True)

image_ext = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

for label_file in os.listdir(LABEL_DIR):

    if not label_file.endswith(".txt"):
        continue

    name = os.path.splitext(label_file)[0]

    # Cari gambar dengan nama yang sama
    image_path = None

    for ext in image_ext:
        path = os.path.join(IMAGE_DIR, name + ext)
        if os.path.exists(path):
            image_path = path
            break

    if image_path is None:
        print(f"Gambar tidak ditemukan: {name}")
        continue

    # Buka gambar
    image = Image.open(image_path)
    img_w, img_h = image.size

    # Baca label
    label_path = os.path.join(LABEL_DIR, label_file)

    with open(label_path, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):

        data = line.strip().split()

        if len(data) != 5:
            continue

        class_id = int(data[0])

        x_center = float(data[1])
        y_center = float(data[2])
        width = float(data[3])
        height = float(data[4])

        # YOLO normalized -> pixel
        x_center *= img_w
        y_center *= img_h
        width *= img_w
        height *= img_h

        # Bounding box
        x1 = int(x_center - width / 2)
        y1 = int(y_center - height / 2)
        x2 = int(x_center + width / 2)
        y2 = int(y_center + height / 2)

        # Batasi agar tidak keluar gambar
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(img_w, x2)
        y2 = min(img_h, y2)

        # Crop
        crop = image.crop((x1, y1, x2, y2))

        # Folder berdasarkan class
        class_dir = os.path.join(
            OUTPUT_DIR,
            str(class_id)
        )

        os.makedirs(class_dir, exist_ok=True)

        # Nama crop
        output_name = f"{name}_{i}.jpg"
        output_path = os.path.join(class_dir, output_name)

        crop.save(output_path)

        print(f"Crop: {output_path}")

print("Selesai.")