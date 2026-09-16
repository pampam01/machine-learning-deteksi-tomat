<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

$error = '';
$success = '';

// Proses Hapus Data Tunggal
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];

    if ($action === 'delete') {
        $id = intval($_POST['id'] ?? 0);
        $stmt = $conn->prepare("DELETE FROM riwayat_klasifikasi WHERE id = ?");
        $stmt->bind_param("i", $id);
        if ($stmt->execute()) {
            $success = 'Data riwayat berhasil dihapus.';
        } else {
            $error = 'Gagal menghapus data riwayat.';
        }
        $stmt->close();
    }

    if ($action === 'delete_all') {
        $filter_del = $_POST['filter_tanggal'] ?? '';
        if (!empty($filter_del)) {
            $stmt = $conn->prepare("DELETE FROM riwayat_klasifikasi WHERE tanggal = ?");
            $stmt->bind_param("s", $filter_del);
            if ($stmt->execute()) {
                $success = 'Semua data riwayat untuk tanggal ' . date('d/m/Y', strtotime($filter_del)) . ' berhasil dihapus.';
            } else {
                $error = 'Gagal menghapus data.';
            }
            $stmt->close();
        } else {
            if ($conn->query("TRUNCATE TABLE riwayat_klasifikasi")) {
                $success = 'Semua data riwayat berhasil dibersihkan.';
            } else {
                $error = 'Gagal menghapus semua data.';
            }
        }
    }
}

// Filter tanggal & Sort
$filter_date = $_GET['tanggal'] ?? '';
$sort_by = $_GET['sort'] ?? 'terbaru';

// Pagination
$per_page = 20;
$page = max(1, intval($_GET['page'] ?? 1));
$offset = ($page - 1) * $per_page;

// Query total data
$count_query = "SELECT COUNT(*) AS total FROM riwayat_klasifikasi";
$data_query = "SELECT * FROM riwayat_klasifikasi";

if (!empty($filter_date)) {
    $count_query .= " WHERE tanggal = '" . $conn->real_escape_string($filter_date) . "'";
    $data_query .= " WHERE tanggal = '" . $conn->real_escape_string($filter_date) . "'";
}

// Order clause
switch ($sort_by) {
    case 'terlama':
        $data_query .= " ORDER BY tanggal ASC, waktu ASC, id ASC";
        break;
    case 'matang':
        $data_query .= " ORDER BY total_matang DESC, id DESC";
        break;
    case 'setengah':
        $data_query .= " ORDER BY total_setengah DESC, id DESC";
        break;
    case 'belum':
        $data_query .= " ORDER BY total_belum DESC, id DESC";
        break;
    case 'terbaru':
    default:
        $data_query .= " ORDER BY tanggal DESC, waktu DESC, id DESC";
        break;
}
$data_query .= " LIMIT $per_page OFFSET $offset";

$total_result = $conn->query($count_query);
$total_rows = $total_result ? intval($total_result->fetch_assoc()['total']) : 0;
$total_pages = ceil($total_rows / $per_page);

$result = $conn->query($data_query);

include __DIR__ . '/../includes/header.php';
?>

<div class="page-header page-header-flex">
    <div>
        <h2>Riwayat Data</h2>
        <p>Detail log data klasifikasi tomat beserta total hitungan kumulatif</p>
    </div>
    <div class="header-actions">
        <a href="<?= BASE_URL ?>/pages/export_excel.php<?= !empty($filter_date) ? '?tanggal=' . urlencode($filter_date) : '' ?>" class="btn btn-excel">
            📊 Export ke Excel
        </a>
        <?php if ($total_rows > 0): ?>
        <button type="button" class="btn btn-danger" onclick="confirmDeleteAll('<?= htmlspecialchars($filter_date) ?>')">
            🗑️ Hapus Semua
        </button>
        <?php endif; ?>
    </div>
</div>

<?php if ($error): ?>
    <div class="alert alert-error">⚠️ <?= htmlspecialchars($error) ?></div>
<?php endif; ?>

<?php if ($success): ?>
    <div class="alert alert-success">✅ <?= htmlspecialchars($success) ?></div>
<?php endif; ?>

<div class="table-container">
    <div class="table-header">
        <h3>📋 Data Riwayat (Total: <?= number_format($total_rows) ?> data)</h3>
        <form class="filter-form" method="GET" action="">
            <input type="date" name="tanggal" value="<?= htmlspecialchars($filter_date) ?>" id="filterTanggal" title="Filter Tanggal">
            
            <select name="sort" title="Urutkan Berdasarkan" onchange="this.form.submit()">
                <option value="terbaru" <?= $sort_by === 'terbaru' ? 'selected' : '' ?>>⏱️ Urutkan: Terbaru</option>
                <option value="terlama" <?= $sort_by === 'terlama' ? 'selected' : '' ?>>⏳ Urutkan: Terlama</option>
                <option value="matang" <?= $sort_by === 'matang' ? 'selected' : '' ?>>🔴 Total Matang Terbanyak</option>
                <option value="setengah" <?= $sort_by === 'setengah' ? 'selected' : '' ?>>🟡 Total Setengah Terbanyak</option>
                <option value="belum" <?= $sort_by === 'belum' ? 'selected' : '' ?>>🟢 Total Belum Terbanyak</option>
            </select>

            <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            <?php if (!empty($filter_date) || $sort_by !== 'terbaru'): ?>
                <a href="<?= BASE_URL ?>/pages/riwayat" class="btn btn-outline btn-sm">Reset</a>
            <?php endif; ?>
        </form>
    </div>

    <div class="table-responsive">
        <?php if ($result && $result->num_rows > 0): ?>
        <table id="riwayatTable">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('riwayatTable', 0, 'num')">No <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 1, 'str')">Tanggal <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 2, 'str')">Waktu <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 3, 'str')">Jenis Klasifikasi <span class="sort-indicator"></span></th>
                    <th>Nilai Fitur (HSV & RGB)</th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 5, 'num')">Total Matang <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 6, 'num')">Total Setengah <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('riwayatTable', 7, 'num')">Total Belum <span class="sort-indicator"></span></th>
                    <th>Foto</th>
                    <th>Aksi</th>
                </tr>
            </thead>
            <tbody>
                <?php $no = $offset + 1; while ($row = $result->fetch_assoc()): ?>
                <tr>
                    <td><?= $no++ ?></td>
                    <td><?= date('d/m/Y', strtotime($row['tanggal'])) ?></td>
                    <td><strong><?= date('H:i:s', strtotime($row['waktu'])) ?></strong></td>
                    <td>
                        <?php
                        $badge_class = 'badge-matang';
                        $icon = '🔴';
                        if ($row['jenis'] === 'Setengah Matang') {
                            $badge_class = 'badge-setengah';
                            $icon = '🟡';
                        } elseif ($row['jenis'] === 'Belum Matang') {
                            $badge_class = 'badge-belum';
                            $icon = '🟢';
                        }
                        ?>
                        <span class="badge <?= $badge_class ?>"><?= $icon ?> <?= htmlspecialchars($row['jenis']) ?></span>
                    </td>
                    <td class="fitur-cell">
                        <?php if (!empty($row['fitur'])): 
                            $fitur_raw = $row['fitur'];
                            $fitur_short = strlen($fitur_raw) > 28 ? substr($fitur_raw, 0, 26) . '...' : $fitur_raw;
                        ?>
                            <span class="fitur-badge" onclick="showFiturModal('<?= rawurlencode($fitur_raw) ?>')" title="Klik untuk rincian HSV & RGB: <?= htmlspecialchars($fitur_raw) ?>">
                                📊 <?= htmlspecialchars($fitur_short) ?>
                            </span>
                        <?php else: ?>
                            <span style="color:#aaa;">—</span>
                        <?php endif; ?>
                    </td>
                    <td><span class="badge badge-matang">🔴 <?= number_format($row['total_matang']) ?></span></td>
                    <td><span class="badge badge-setengah">🟡 <?= number_format($row['total_setengah']) ?></span></td>
                    <td><span class="badge badge-belum">🟢 <?= number_format($row['total_belum']) ?></span></td>
                    <td>
                        <?php if (!empty($row['foto'])): ?>
                            <a href="<?= BASE_URL ?>/<?= htmlspecialchars($row['foto']) ?>" target="_blank">
                                <img src="<?= BASE_URL ?>/<?= htmlspecialchars($row['foto']) ?>"
                                     alt="foto"
                                     style="height:36px; border-radius:4px; cursor:pointer; object-fit:cover;"
                                     title="Klik untuk memperbesar">
                            </a>
                        <?php else: ?>
                            <span style="color:#aaa;">—</span>
                        <?php endif; ?>
                    </td>
                    <td>
                        <form method="POST" action="" style="display:inline" onsubmit="return confirm('Yakin ingin menghapus baris data ini?');">
                            <input type="hidden" name="action" value="delete">
                            <input type="hidden" name="id" value="<?= $row['id'] ?>">
                            <button type="submit" class="btn btn-danger btn-sm" title="Hapus baris ini">
                                🗑️ Hapus
                            </button>
                        </form>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>

        <!-- Pagination -->
        <?php if ($total_pages > 1): 
            $query_params = [];
            if (!empty($filter_date)) $query_params[] = 'tanggal=' . urlencode($filter_date);
            if (!empty($sort_by)) $query_params[] = 'sort=' . urlencode($sort_by);
            $query_str = !empty($query_params) ? '&' . implode('&', $query_params) : '';
        ?>
        <div class="pagination">
            <?php if ($page > 1): ?>
                <a href="?page=<?= $page - 1 ?><?= $query_str ?>">← Prev</a>
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
                    <a href="?page=<?= $i ?><?= $query_str ?>"><?= $i ?></a>
                <?php endif; ?>
            <?php endfor; ?>

            <?php if ($page < $total_pages): ?>
                <a href="?page=<?= $page + 1 ?><?= $query_str ?>">Next →</a>
            <?php else: ?>
                <span class="disabled">Next →</span>
            <?php endif; ?>
        </div>
        <?php endif; ?>

        <?php else: ?>
        <div class="empty-state">
            <div class="empty-icon">📭</div>
            <p>Belum ada data riwayat<?= !empty($filter_date) ? ' untuk tanggal ' . date('d/m/Y', strtotime($filter_date)) : '' ?></p>
        </div>
        <?php endif; ?>
    </div>
</div>

<!-- Hidden Form for Delete All -->
<form id="formDeleteAll" method="POST" action="" style="display: none;">
    <input type="hidden" name="action" value="delete_all">
    <input type="hidden" name="filter_tanggal" id="delFilterTanggal" value="">
</form>

<script>
function confirmDeleteAll(filterDate) {
    let msg = 'Apakah Anda YAKIN ingin menghapus SEMUA data riwayat? Tindakan ini permanen dan tidak dapat dibatalkan!';
    if (filterDate) {
        msg = `Apakah Anda YAKIN ingin menghapus SEMUA data riwayat untuk tanggal ${filterDate}? Tindakan ini permanen!`;
    }
    if (confirm(msg)) {
        document.getElementById('delFilterTanggal').value = filterDate || '';
        document.getElementById('formDeleteAll').submit();
    }
}
</script>

<?php include __DIR__ . '/../includes/footer.php'; ?>
