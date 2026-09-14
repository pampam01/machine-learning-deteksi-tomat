<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

$filter_date = $_GET['tanggal'] ?? '';

$filename = 'riwayat_klasifikasi_tomat_' . (!empty($filter_date) ? $filter_date : date('Ymd_His')) . '.xls';

header("Content-Type: application/vnd.ms-excel; charset=UTF-8");
header("Content-Disposition: attachment; filename=\"$filename\"");
header("Pragma: no-cache");
header("Expires: 0");

$query = "SELECT id, tanggal, waktu, jenis, total_matang, total_setengah, total_belum, fitur, foto FROM riwayat_klasifikasi";
if (!empty($filter_date)) {
    $query .= " WHERE tanggal = '" . $conn->real_escape_string($filter_date) . "'";
}
$query .= " ORDER BY tanggal DESC, waktu DESC";

$result = $conn->query($query);
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Export Riwayat Klasifikasi Tomat</title>
    <style>
        table {
            border-collapse: collapse;
            width: 100%;
            font-family: Arial, sans-serif;
            font-size: 12px;
        }
        th, td {
            border: 1px solid #333333;
            padding: 8px 12px;
            text-align: left;
            vertical-align: middle;
        }
        th {
            background-color: #2E7D32;
            color: #ffffff;
            font-weight: bold;
            text-align: center;
        }
        .header-title {
            font-size: 16px;
            font-weight: bold;
            text-align: center;
            padding: 10px;
        }
        .text-center { text-align: center; }
        .matang { background-color: #E8F5E9; color: #1B5E20; font-weight: bold; }
        .setengah { background-color: #FFF3E0; color: #E65100; font-weight: bold; }
        .belum { background-color: #FFEBEE; color: #C62828; font-weight: bold; }
        .foto-preview {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 4px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <table>
        <tr>
            <th colspan="9" class="header-title">
                LAPORAN RIWAYAT KLASIFIKASI KEMATANGAN TOMAT
                <?= !empty($filter_date) ? '<br>Tanggal: ' . date('d/m/Y', strtotime($filter_date)) : '<br>Semua Data' ?>
            </th>
        </tr>
        <tr>
            <th>No</th>
            <th>Tanggal</th>
            <th>Waktu</th>
            <th>Jenis Klasifikasi</th>
            <th>Nilai Fitur</th>
            <th>Total Matang</th>
            <th>Total Setengah Matang</th>
            <th>Total Belum Matang</th>
            <th>Foto</th>
        </tr>
        <?php if ($result && $result->num_rows > 0): ?>
            <?php 
            $no = 1; 
            $scheme = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
            $project_base = $scheme . '://' . $host . BASE_URL;

            while ($row = $result->fetch_assoc()): 
                $foto_html = '—';
                if (!empty($row['foto'])) {
                    $local_file = dirname(__DIR__) . '/' . ltrim($row['foto'], '/');
                    $img_web_url = $project_base . '/' . ltrim($row['foto'], '/');
                    
                    if (file_exists($local_file) && is_file($local_file)) {
                        $mime = mime_content_type($local_file) ?: 'image/jpeg';
                        $base64_data = base64_encode(file_get_contents($local_file));
                        $foto_html = '<a href="' . htmlspecialchars($img_web_url) . '" target="_blank">' .
                                     '<img src="data:' . $mime . ';base64,' . $base64_data . '" width="60" height="60" class="foto-preview" alt="Foto">' .
                                     '</a>';
                    } else {
                        $foto_html = '<a href="' . htmlspecialchars($img_web_url) . '" target="_blank">Lihat Foto</a>';
                    }
                }
            ?>
            <tr style="height: 70px;">
                <td class="text-center"><?= $no++ ?></td>
                <td class="text-center"><?= date('d/m/Y', strtotime($row['tanggal'])) ?></td>
                <td class="text-center"><?= date('H:i:s', strtotime($row['waktu'])) ?></td>
                <td class="text-center <?= $row['jenis'] === 'Matang' ? 'matang' : ($row['jenis'] === 'Setengah Matang' ? 'setengah' : 'belum') ?>">
                    <?= htmlspecialchars($row['jenis']) ?>
                </td>
                <td class="text-center"><?= htmlspecialchars($row['fitur'] ?? '—') ?></td>
                <td class="text-center matang"><?= number_format($row['total_matang']) ?></td>
                <td class="text-center setengah"><?= number_format($row['total_setengah']) ?></td>
                <td class="text-center belum"><?= number_format($row['total_belum']) ?></td>
                <td class="text-center" style="vertical-align: middle;"><?= $foto_html ?></td>
            </tr>
            <?php endwhile; ?>
        <?php else: ?>
            <tr>
                <td colspan="9" class="text-center">Tidak ada data riwayat yang ditemukan.</td>
            </tr>
        <?php endif; ?>
    </table>
</body>
</html>
