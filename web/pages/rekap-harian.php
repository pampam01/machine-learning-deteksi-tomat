<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

// Filter tanggal & sesi
$filter_date = $_GET['tanggal'] ?? '';
$filter_session = $_GET['sesi'] ?? '';

// Pagination
$per_page = 15;
$page = max(1, intval($_GET['page'] ?? 1));
$offset = ($page - 1) * $per_page;

// Kondisi WHERE
$where_clauses = [];
if (!empty($filter_date)) {
    $where_clauses[] = "tanggal = '" . $conn->real_escape_string($filter_date) . "'";
}
if (!empty($filter_session)) {
    $where_clauses[] = "session_id = " . intval($filter_session);
}

$where_sql = '';
if (count($where_clauses) > 0) {
    $where_sql = " WHERE " . implode(" AND ", $where_clauses);
}

// Query total data grup (tanggal + session_id)
$count_query = "SELECT COUNT(*) AS total FROM (
    SELECT tanggal, session_id 
    FROM riwayat_klasifikasi 
    $where_sql
    GROUP BY tanggal, session_id
) AS t";

$total_result = $conn->query($count_query);
$total_rows = $total_result ? intval($total_result->fetch_assoc()['total']) : 0;
$total_pages = ceil($total_rows / $per_page);

// Query rekap per tanggal dan per sesi
$query = "SELECT 
    tanggal,
    session_id,
    MIN(waktu) AS waktu_mulai,
    MAX(waktu) AS waktu_selesai,
    SUM(CASE WHEN jenis = 'Matang' THEN jumlah ELSE 0 END) AS total_matang,
    SUM(CASE WHEN jenis = 'Setengah Matang' THEN jumlah ELSE 0 END) AS total_setengah,
    SUM(CASE WHEN jenis = 'Belum Matang' THEN jumlah ELSE 0 END) AS total_belum,
    SUM(jumlah) AS total_semua
    FROM riwayat_klasifikasi
    $where_sql
    GROUP BY tanggal, session_id
    ORDER BY tanggal DESC, session_id DESC
    LIMIT $per_page OFFSET $offset";

$result = $conn->query($query);

// Ambil daftar sesi unik untuk opsi filter dropdown
$sessions_list = $conn->query("SELECT DISTINCT session_id FROM riwayat_klasifikasi ORDER BY session_id DESC");

include __DIR__ . '/../includes/header.php';
?>

<div class="page-header">
    <h2>Rekap Harian & Sesi</h2>
    <p>Ringkasan klasifikasi tomat yang dibedakan per tanggal dan per sesi counter</p>
</div>

<div class="table-container">
    <div class="table-header">
        <h3>📅 Rekap Per Tanggal & Sesi</h3>
        <form class="filter-form" method="GET" action="">
            <input type="date" name="tanggal" value="<?= htmlspecialchars($filter_date) ?>" id="filterTanggal" title="Filter Tanggal">
            
            <select name="sesi" style="padding: 8px 12px; border: 1px solid var(--gray-300); border-radius: var(--border-radius-sm); font-family: inherit; font-size: 0.85rem; color: var(--gray-700);">
                <option value="">Semua Sesi</option>
                <?php if ($sessions_list && $sessions_list->num_rows > 0): ?>
                    <?php while ($s = $sessions_list->fetch_assoc()): ?>
                        <option value="<?= $s['session_id'] ?>" <?= ($filter_session == $s['session_id']) ? 'selected' : '' ?>>
                            Sesi #<?= $s['session_id'] ?>
                        </option>
                    <?php endwhile; ?>
                <?php endif; ?>
            </select>

            <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            <?php if (!empty($filter_date) || !empty($filter_session)): ?>
                <a href="<?= BASE_URL ?>/pages/rekap-harian.php" class="btn btn-outline btn-sm">Reset</a>
            <?php endif; ?>
        </form>
    </div>

    <div class="table-responsive">
        <?php if ($result && $result->num_rows > 0): ?>
        <table>
            <thead>
                <tr>
                    <th>No</th>
                    <th>Tanggal</th>
                    <th>Sesi Hitungan</th>
                    <th>Waktu (Mulai - Selesai)</th>
                    <th>Total Matang</th>
                    <th>Total Setengah Matang</th>
                    <th>Total Belum Matang</th>
                    <th>Total Sesi</th>
                </tr>
            </thead>
            <tbody>
                <?php $no = $offset + 1; while ($row = $result->fetch_assoc()): ?>
                <tr>
                    <td><?= $no++ ?></td>
                    <td><?= date('d/m/Y', strtotime($row['tanggal'])) ?></td>
                    <td>
                        <span class="badge" style="background: #E3F2FD; color: #0D47A1; font-weight: 700; border: 1px solid #BBDEFB;">
                            Sesi #<?= $row['session_id'] ?>
                        </span>
                    </td>
                    <td>
                        <?= date('H:i', strtotime($row['waktu_mulai'])) ?> - <?= date('H:i', strtotime($row['waktu_selesai'])) ?>
                    </td>
                    <td>
                        <span class="badge badge-matang">🟢 <?= number_format($row['total_matang']) ?></span>
                    </td>
                    <td>
                        <span class="badge badge-setengah">🟠 <?= number_format($row['total_setengah']) ?></span>
                    </td>
                    <td>
                        <span class="badge badge-belum">🔴 <?= number_format($row['total_belum']) ?></span>
                    </td>
                    <td><strong><?= number_format($row['total_semua']) ?></strong></td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>

        <!-- Pagination -->
        <?php if ($total_pages > 1): ?>
        <?php
            $query_params = [];
            if (!empty($filter_date)) $query_params['tanggal'] = $filter_date;
            if (!empty($filter_session)) $query_params['sesi'] = $filter_session;
            $query_string = !empty($query_params) ? '&' . http_build_query($query_params) : '';
        ?>
        <div class="pagination">
            <?php if ($page > 1): ?>
                <a href="?page=<?= $page - 1 ?><?= $query_string ?>">← Prev</a>
            <?php else: ?>
                <span class="disabled">← Prev</span>
            <?php endif; ?>

            <?php
            $start = max(1, $page - 2);
            $end = min($total_pages, $page + 2);
            for ($i = $start; $i <= $end; $i++):
            ?>
                <?php if ($i === $page): ?>
                    <span class="active"><?= $i ?></span>
                <?php else: ?>
                    <a href="?page=<?= $i ?><?= $query_string ?>"><?= $i ?></a>
                <?php endif; ?>
            <?php endfor; ?>

            <?php if ($page < $total_pages): ?>
                <a href="?page=<?= $page + 1 ?><?= $query_string ?>">Next →</a>
            <?php else: ?>
                <span class="disabled">Next →</span>
            <?php endif; ?>
        </div>
        <?php endif; ?>

        <?php else: ?>
        <div class="empty-state">
            <div class="empty-icon">📭</div>
            <p>Belum ada data rekap per tanggal/sesi</p>
        </div>
        <?php endif; ?>
    </div>
</div>

<?php include __DIR__ . '/../includes/footer.php'; ?>
