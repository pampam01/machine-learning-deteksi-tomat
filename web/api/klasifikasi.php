<?php
/**
 * API Endpoint untuk IoT Device
 * Menerima data klasifikasi tomat dari ESP32/Arduino
 * 
 * Method: POST
 * Content-Type: multipart/form-data (jika kirim foto) atau application/json
 * 
 * Parameter:
 *   - jenis     (string): "Matang", "Setengah Matang", atau "Belum Matang"
 *   - jumlah    (int, optional): Jumlah tomat (default: 1)
 *   - fitur     (string, optional): Nilai fitur, mis. "{1,2,4,24}"
 *   - foto      (file, optional): File gambar (jpg/png/bmp)
 * 
 * Response (JSON):
 *   - status: "success" atau "error"
 *   - message: Pesan keterangan
 *   - data: Detail data yang tersimpan
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET');
header('Access-Control-Allow-Headers: Content-Type');

// Handle preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

require_once __DIR__ . '/../config/database.php';

// Hanya terima POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode([
        'status' => 'error',
        'message' => 'Method not allowed. Gunakan POST.'
    ]);
    exit();
}

// Ambil data dari JSON body, form data, atau GET parameter
$raw_input = file_get_contents('php://input');
$input = json_decode($raw_input, true);

if (!is_array($input) || empty($input)) {
    // Coba dari $_POST atau $_REQUEST
    $input = !empty($_POST) ? $_POST : $_REQUEST;
}

// Ambil nilai jenis dari berbagai alternatif key
$raw_jenis = $input['jenis'] ?? $input['label'] ?? $input['klasifikasi'] ?? $input['kategori'] ?? $input['class'] ?? $input['status'] ?? $_GET['jenis'] ?? '';
$jumlah    = intval($input['jumlah'] ?? $_GET['jumlah'] ?? 1);

/**
 * Normalisasi nilai jenis (case-insensitive, alias, numeric)
 */
function normalizeJenis($val) {
    if ($val === null || $val === '') return null;
    
    // Support jika dikirim angka (0 = Belum Matang, 1 = Setengah Matang, 2 = Matang)
    if (is_numeric($val)) {
        $num = intval($val);
        if ($num === 0) return 'Belum Matang';
        if ($num === 1) return 'Setengah Matang';
        if ($num === 2) return 'Matang';
    }

    $clean = strtolower(trim((string)$val));
    $clean = str_replace(['_', '-'], ' ', $clean);

    if (in_array($clean, ['matang', 'ripe', 'red'])) {
        return 'Matang';
    }
    if (in_array($clean, ['setengah matang', 'setengah', 'half ripe', 'half', 'orange', 'yellow'])) {
        return 'Setengah Matang';
    }
    if (in_array($clean, ['belum matang', 'belum', 'mentah', 'unripe', 'raw', 'green'])) {
        return 'Belum Matang';
    }

    return null;
}

$jenis = normalizeJenis($raw_jenis);

// Validasi jenis
if (!$jenis) {
    http_response_code(400);
    echo json_encode([
        'status' => 'error',
        'message' => 'Parameter "jenis" tidak valid (diterima: "' . htmlspecialchars((string)$raw_jenis) . '"). Gunakan salah satu dari: Matang, Setengah Matang, atau Belum Matang.'
    ], JSON_UNESCAPED_UNICODE);
    exit();
}

// Validasi jumlah
if ($jumlah < 1) {
    $jumlah = 1;
}

// Ambil nilai fitur (string bebas, mis. "{1,2,4,24}")
$fitur = isset($input['fitur']) && $input['fitur'] !== '' ? trim($input['fitur']) : null;

// Handle upload foto (multipart/form-data)
$foto_path = null;
if (isset($_FILES['foto']) && $_FILES['foto']['error'] === UPLOAD_ERR_OK) {
    $upload_dir = __DIR__ . '/../uploads/foto/';
    if (!is_dir($upload_dir)) {
        mkdir($upload_dir, 0755, true);
    }
    $ext = strtolower(pathinfo($_FILES['foto']['name'], PATHINFO_EXTENSION));
    $allowed_ext = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp'];
    if (in_array($ext, $allowed_ext)) {
        $filename = date('YmdHis') . '_' . uniqid() . '.' . $ext;
        $dest     = $upload_dir . $filename;
        if (move_uploaded_file($_FILES['foto']['tmp_name'], $dest)) {
            $foto_path = 'uploads/foto/' . $filename;
        }
    }
}

// Simpan ke database
$tanggal = !empty($input['tanggal_override']) ? $input['tanggal_override'] : date('Y-m-d');
$waktu   = date('H:i:s');

// Cek tanggal sesi terakhir & reset ke Sesi 1 jika berganti hari
$date_res         = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'last_session_date'");
$last_session_date = ($date_res && $drow = $date_res->fetch_assoc()) ? $drow['setting_value'] : '';

$session_res       = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'current_session_id'");
$current_session_id = 1;
if ($session_res && $row = $session_res->fetch_assoc()) {
    $current_session_id = intval($row['setting_value']);
}

// Jika berganti hari, kembalikan sesi ke Sesi #1
if ($last_session_date !== $tanggal) {
    $current_session_id = 1;
    $conn->query("UPDATE app_settings SET setting_value = '1' WHERE setting_key = 'current_session_id'");
    $conn->query("UPDATE app_settings SET setting_value = '$tanggal' WHERE setting_key = 'last_session_date'");
}

// Ambil total kumulatif terakhir untuk tanggal dan session_id saat ini
$last_stmt = $conn->prepare("SELECT total_matang, total_setengah, total_belum FROM riwayat_klasifikasi WHERE tanggal = ? AND session_id = ? ORDER BY id DESC LIMIT 1");
$last_stmt->bind_param("si", $tanggal, $current_session_id);
$last_stmt->execute();
$last_row = $last_stmt->get_result()->fetch_assoc();
$last_stmt->close();

$total_matang   = $last_row ? intval($last_row['total_matang'])   : 0;
$total_setengah = $last_row ? intval($last_row['total_setengah']) : 0;
$total_belum    = $last_row ? intval($last_row['total_belum'])    : 0;

if ($jenis === 'Matang') {
    $total_matang += $jumlah;
} elseif ($jenis === 'Setengah Matang') {
    $total_setengah += $jumlah;
} elseif ($jenis === 'Belum Matang') {
    $total_belum += $jumlah;
}

$stmt = $conn->prepare(
    "INSERT INTO riwayat_klasifikasi
     (tanggal, waktu, jenis, jumlah, session_id, total_matang, total_setengah, total_belum, fitur, foto)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
);
$stmt->bind_param(
    "sssiiiiiss",
    $tanggal, $waktu, $jenis, $jumlah,
    $current_session_id,
    $total_matang, $total_setengah, $total_belum,
    $fitur, $foto_path
);

if ($stmt->execute()) {
    http_response_code(201);
    echo json_encode([
        'status'  => 'success',
        'message' => 'Data klasifikasi berhasil disimpan.',
        'data'    => [
            'id'             => $stmt->insert_id,
            'tanggal'        => $tanggal,
            'waktu'          => $waktu,
            'jenis'          => $jenis,
            'jumlah'         => $jumlah,
            'session_id'     => $current_session_id,
            'total_matang'   => $total_matang,
            'total_setengah' => $total_setengah,
            'total_belum'    => $total_belum,
            'fitur'          => $fitur,
            'foto'           => $foto_path
        ]
    ]);
} else {
    http_response_code(500);
    echo json_encode([
        'status'  => 'error',
        'message' => 'Gagal menyimpan data: ' . $conn->error
    ]);
}

$stmt->close();
$conn->close();
?>
