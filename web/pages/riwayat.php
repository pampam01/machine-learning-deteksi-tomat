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

// Filter tanggal
$filter_date = $_GET['tanggal'] ?? '';

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

$data_query .= " ORDER BY tanggal DESC, waktu DESC, id DESC LIMIT $per_page OFFSET $offset";

$total_result = $conn->query($count_query);
$total_rows = $total_result->fetch_assoc()['total'];
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
            <input type="date" name="tanggal" value="<?= htmlspecialchars($filter_date) ?>" id="filterTanggal">
            <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            <?php if (!empty($filter_date)): ?>
                <a href="<?= BASE_URL ?>/pages/riwayat.php" class="btn btn-outline btn-sm">Reset</a>
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
                    <th>Waktu</th>
                    <th>Jenis Klasifikasi</th>
                    <th>Nilai Fitur</th>
                    <th>Total Matang</th>
                    <th>Total Setengah Matang</th>
                    <th>Total Belum Matang</th>
                    <th>Foto</th>
                    <th>Aksi</th>
                </tr>
            </thead>
            <tbody>
                <?php $no = $offset + 1; while ($row = $result->fetch_assoc()): ?>
                <tr>
                    <td><?= $no++ ?></td>
                    <td><?= date('d/m/Y', strtotime($row['tanggal'])) ?></td>
                    <td><?= date('H:i:s', strtotime($row['waktu'])) ?></td>
                    <td>
                        <?php
                        $badge_class = '';
                        if ($row['jenis'] === 'Matang') $badge_class = 'badge-matang';
                        elseif ($row['jenis'] === 'Setengah Matang') $badge_class = 'badge-setengah';
                        else $badge_class = 'badge-belum';
                        ?>
                        <span class="badge <?= $badge_class ?>"><?= htmlspecialchars($row['jenis']) ?></span>
                    </td>
                    <td>
                        <?php if (!empty($row['fitur'])): ?>
                            <code style="font-size:0.82em;"><?= htmlspecialchars($row['fitur']) ?></code>
                        <?php else: ?>
                            <span style="color:#aaa;">—</span>
                        <?php endif; ?>
                    </td>
                    <td><span class="badge badge-matang">🟢 <?= number_format($row['total_matang']) ?></span></td>
                    <td><span class="badge badge-setengah">🟠 <?= number_format($row['total_setengah']) ?></span></td>
                    <td><span class="badge badge-belum">🔴 <?= number_format($row['total_belum']) ?></span></td>
                    <td>
                        <?php if (!empty($row['foto'])): ?>
                            <a href="<?= BASE_URL ?>/<?= htmlspecialchars($row['foto']) ?>" target="_blank">
                                <img src="<?= BASE_URL ?>/<?= htmlspecialchars($row['foto']) ?>"
                                     alt="foto"
                                     style="height:40px;border-radius:4px;cursor:pointer;"
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
        <?php if ($total_pages > 1): ?>
        <div class="pagination">
            <?php if ($page > 1): ?>
                <a href="?page=<?= $page - 1 ?><?= !empty($filter_date) ? '&tanggal=' . urlencode($filter_date) : '' ?>">← Prev</a>
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
                    <a href="?page=<?= $i ?><?= !empty($filter_date) ? '&tanggal=' . urlencode($filter_date) : '' ?>"><?= $i ?></a>
                <?php endif; ?>
            <?php endfor; ?>

            <?php if ($page < $total_pages): ?>
                <a href="?page=<?= $page + 1 ?><?= !empty($filter_date) ? '&tanggal=' . urlencode($filter_date) : '' ?>">Next →</a>
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
