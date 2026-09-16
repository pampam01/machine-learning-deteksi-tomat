<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

// Filter tanggal, sesi & sort
$filter_date = $_GET['tanggal'] ?? '';
$filter_session = $_GET['sesi'] ?? '';
$sort_by = $_GET['sort'] ?? 'tanggal_desc';

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

// Order SQL
$order_sql = "ORDER BY tanggal DESC, session_id DESC";
if ($sort_by === 'tanggal_asc') {
    $order_sql = "ORDER BY tanggal ASC, session_id ASC";
} elseif ($sort_by === 'total_desc') {
    $order_sql = "ORDER BY total_semua DESC, tanggal DESC";
} elseif ($sort_by === 'matang_desc') {
    $order_sql = "ORDER BY total_matang DESC, tanggal DESC";
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
    $order_sql
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
            
            <select name="sesi" title="Filter Sesi">
                <option value="">Semua Sesi</option>
                <?php if ($sessions_list && $sessions_list->num_rows > 0): ?>
                    <?php while ($s = $sessions_list->fetch_assoc()): ?>
                        <option value="<?= $s['session_id'] ?>" <?= ($filter_session == $s['session_id']) ? 'selected' : '' ?>>
                            Sesi #<?= $s['session_id'] ?>
                        </option>
                    <?php endwhile; ?>
                <?php endif; ?>
            </select>

            <select name="sort" title="Urutkan Berdasarkan" onchange="this.form.submit()">
                <option value="tanggal_desc" <?= $sort_by === 'tanggal_desc' ? 'selected' : '' ?>>⏱️ Tanggal Terbaru</option>
                <option value="tanggal_asc" <?= $sort_by === 'tanggal_asc' ? 'selected' : '' ?>>⏳ Tanggal Terlama</option>
                <option value="total_desc" <?= $sort_by === 'total_desc' ? 'selected' : '' ?>>🍅 Total Terbanyak</option>
                <option value="matang_desc" <?= $sort_by === 'matang_desc' ? 'selected' : '' ?>>🔴 Matang Terbanyak</option>
            </select>

            <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            <?php if (!empty($filter_date) || !empty($filter_session) || $sort_by !== 'tanggal_desc'): ?>
                <a href="<?= BASE_URL ?>/pages/rekap-harian" class="btn btn-outline btn-sm">Reset</a>
            <?php endif; ?>
        </form>
    </div>

    <div class="table-responsive">
        <?php if ($result && $result->num_rows > 0): ?>
        <table id="rekapTable">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('rekapTable', 0, 'num')">No <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('rekapTable', 1, 'str')">Tanggal <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('rekapTable', 2, 'num')">Sesi Hitungan <span class="sort-indicator"></span></th>
                    <th>Waktu (Mulai - Selesai)</th>
                    <th class="sortable" onclick="sortTable('rekapTable', 4, 'num')">Total Matang <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('rekapTable', 5, 'num')">Total Setengah <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('rekapTable', 6, 'num')">Total Belum <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('rekapTable', 7, 'num')">Total Sesi <span class="sort-indicator"></span></th>
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
                        <span class="badge badge-matang">🔴 <?= number_format($row['total_matang']) ?></span>
                    </td>
                    <td>
                        <span class="badge badge-setengah">🟡 <?= number_format($row['total_setengah']) ?></span>
                    </td>
                    <td>
                        <span class="badge badge-belum">🟢 <?= number_format($row['total_belum']) ?></span>
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
