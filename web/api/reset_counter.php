<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET');

require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';

$today = date('Y-m-d');

// Cek tanggal sesi terakhir
$date_res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'last_session_date'");
$last_session_date = ($date_res && $drow = $date_res->fetch_assoc()) ? $drow['setting_value'] : '';

// Ambil current_session_id
$res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'current_session_id'");
$current_session_id = 1;
if ($res && $row = $res->fetch_assoc()) {
    $current_session_id = intval($row['setting_value']);
}

// Jika hari baru, sesi baru mulai dari 2 jika ditekan reset (karena 1 sudah lewat/reset), jika sama hari, increment + 1
if ($last_session_date !== $today) {
    $new_session_id = 2;
    $conn->query("UPDATE app_settings SET setting_value = '$today' WHERE setting_key = 'last_session_date'");
} else {
    $new_session_id = $current_session_id + 1;
}

$stmt = $conn->prepare("UPDATE app_settings SET setting_value = ? WHERE setting_key = 'current_session_id'");
$new_val = (string)$new_session_id;
$stmt->bind_param("s", $new_val);

if ($stmt->execute()) {
    echo json_encode([
        'status' => 'success',
        'message' => 'Counter hitungan berhasil direset.',
        'session_id' => $new_session_id,
        'totals' => [
            'total_matang' => 0,
            'total_setengah' => 0,
            'total_belum' => 0,
            'total_semua' => 0
        ]
    ]);
} else {
    http_response_code(500);
    echo json_encode([
        'status' => 'error',
        'message' => 'Gagal mereset counter: ' . $conn->error
    ]);
}

$stmt->close();
$conn->close();
?>
