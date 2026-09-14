<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once __DIR__ . '/../config/database.php';

$filter_date = $_GET['tanggal'] ?? date('Y-m-d');

$today = date('Y-m-d');

// Cek tanggal sesi terakhir
$date_res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'last_session_date'");
$last_session_date = ($date_res && $drow = $date_res->fetch_assoc()) ? $drow['setting_value'] : '';

// Dapatkan current_session_id aktif
$session_res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'current_session_id'");
$current_session_id = 1;
if ($session_res && $row = $session_res->fetch_assoc()) {
    $current_session_id = intval($row['setting_value']);
}

// Jika berganti hari, sesi aktif kembali ke Sesi #1
if ($last_session_date !== $today) {
    $current_session_id = 1;
}

// Rekap berdasarkan tanggal yang dipilih
$query_date = "SELECT 
    COALESCE(SUM(CASE WHEN jenis = 'Matang' THEN jumlah ELSE 0 END), 0) AS total_matang,
    COALESCE(SUM(CASE WHEN jenis = 'Setengah Matang' THEN jumlah ELSE 0 END), 0) AS total_setengah,
    COALESCE(SUM(CASE WHEN jenis = 'Belum Matang' THEN jumlah ELSE 0 END), 0) AS total_belum,
    COALESCE(SUM(jumlah), 0) AS total_semua
    FROM riwayat_klasifikasi 
    WHERE tanggal = ?";

$stmt = $conn->prepare($query_date);
$stmt->bind_param("s", $filter_date);
$stmt->execute();
$date_rekap = $stmt->get_result()->fetch_assoc();
$stmt->close();

// Rekap counter kumulatif untuk sesi aktif pada tanggal yang dipilih
$last_stmt = $conn->prepare("SELECT total_matang, total_setengah, total_belum FROM riwayat_klasifikasi WHERE tanggal = ? AND session_id = ? ORDER BY id DESC LIMIT 1");
$last_stmt->bind_param("si", $filter_date, $current_session_id);
$last_stmt->execute();
$last_row = $last_stmt->get_result()->fetch_assoc();
$last_stmt->close();

$counter_matang = $last_row ? intval($last_row['total_matang']) : 0;
$counter_setengah = $last_row ? intval($last_row['total_setengah']) : 0;
$counter_belum = $last_row ? intval($last_row['total_belum']) : 0;
$counter_semua = $counter_matang + $counter_setengah + $counter_belum;

// Ambil 10 data terbaru untuk tanggal yang dipilih
$recent_stmt = $conn->prepare("SELECT id, tanggal, waktu, jenis, jumlah, session_id, total_matang, total_setengah, total_belum, fitur, foto, created_at FROM riwayat_klasifikasi WHERE tanggal = ? ORDER BY id DESC LIMIT 10");
$recent_stmt->bind_param("s", $filter_date);
$recent_stmt->execute();
$recent_res = $recent_stmt->get_result();

$recent_data = [];
while ($r = $recent_res->fetch_assoc()) {
    $recent_data[] = [
        'id'             => intval($r['id']),
        'tanggal'        => $r['tanggal'],
        'waktu'          => date('H:i:s', strtotime($r['waktu'])),
        'jenis'          => $r['jenis'],
        'jumlah'         => intval($r['jumlah']),
        'session_id'     => intval($r['session_id']),
        'total_matang'   => intval($r['total_matang']),
        'total_setengah' => intval($r['total_setengah']),
        'total_belum'    => intval($r['total_belum']),
        'fitur'          => $r['fitur'],
        'foto'           => $r['foto']
    ];
}
$recent_stmt->close();
$conn->close();

echo json_encode([
    'status' => 'success',
    'filter_date' => $filter_date,
    'session_id' => $current_session_id,
    'date_totals' => [
        'total_matang' => intval($date_rekap['total_matang']),
        'total_setengah' => intval($date_rekap['total_setengah']),
        'total_belum' => intval($date_rekap['total_belum']),
        'total_semua' => intval($date_rekap['total_semua'])
    ],
    'counter_totals' => [
        'total_matang' => $counter_matang,
        'total_setengah' => $counter_setengah,
        'total_belum' => $counter_belum,
        'total_semua' => $counter_semua
    ],
    'recent' => $recent_data,
    'server_time' => date('H:i:s')
]);
?>
