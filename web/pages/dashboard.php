<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

// Ambil rekap berdasarkan tanggal (default: hari ini)
$filter_date = $_GET['tanggal'] ?? date('Y-m-d');

// Dapatkan current_session_id aktif & cek pergantian hari
$today = date('Y-m-d');
$date_res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'last_session_date'");
$last_session_date = ($date_res && $drow = $date_res->fetch_assoc()) ? $drow['setting_value'] : '';

$session_res = $conn->query("SELECT setting_value FROM app_settings WHERE setting_key = 'current_session_id'");
$current_session_id = 1;
if ($session_res && $row = $session_res->fetch_assoc()) {
    $current_session_id = intval($row['setting_value']);
}

if ($last_session_date !== $today) {
    $current_session_id = 1;
}

// Rekap awal berdasarkan tanggal
$query = "SELECT 
    COALESCE(SUM(CASE WHEN jenis = 'Matang' THEN jumlah ELSE 0 END), 0) AS total_matang,
    COALESCE(SUM(CASE WHEN jenis = 'Setengah Matang' THEN jumlah ELSE 0 END), 0) AS total_setengah,
    COALESCE(SUM(CASE WHEN jenis = 'Belum Matang' THEN jumlah ELSE 0 END), 0) AS total_belum,
    COALESCE(SUM(jumlah), 0) AS total_semua
    FROM riwayat_klasifikasi 
    WHERE tanggal = ?";

$stmt = $conn->prepare($query);
$stmt->bind_param("s", $filter_date);
$stmt->execute();
$rekap = $stmt->get_result()->fetch_assoc();
$stmt->close();

// Format tanggal Indonesia
$hari = ['Minggu','Senin','Selasa','Rabu','Kamis','Jumat','Sabtu'];
$bulan = ['','Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'];
$timestamp = strtotime($filter_date);
$tanggal_indo = $hari[date('w', $timestamp)] . ', ' . date('d', $timestamp) . ' ' . $bulan[(int)date('m', $timestamp)] . ' ' . date('Y', $timestamp);

include __DIR__ . '/../includes/header.php';
?>

<div class="page-header page-header-flex">
    <div>
        <div class="page-title-row">
            <h2>Dashboard</h2>
            <span class="live-badge">
                <span class="pulse-dot"></span> LIVE
            </span>
        </div>
        <p>Monitoring klasifikasi kematangan tomat secara realtime & sesi hitungan aktif</p>
    </div>
</div>

<div id="toastNotification" class="toast-notification"></div>

<div class="dashboard-date">
    <div class="dashboard-date-wrapper">
        <div class="dashboard-date-left">
            <h3 style="margin: 0; color: #fff;">📅 <?= $tanggal_indo ?></h3>
            <span class="counter-badge" id="sessionBadge">Sesi Hitungan: #<?= $current_session_id ?></span>
        </div>
        <form class="filter-form" method="GET" action="">
            <input type="date" name="tanggal" value="<?= htmlspecialchars($filter_date) ?>" id="filterTanggal">
            <button type="submit" class="btn btn-primary btn-sm">Filter</button>
            <?php if (isset($_GET['tanggal'])): ?>
                <a href="<?= BASE_URL ?>/pages/dashboard.php" class="btn btn-outline-white btn-sm">Reset</a>
            <?php endif; ?>
        </form>
    </div>
</div>

<!-- Stats Cards -->
<div class="stats-grid">
    <div class="stat-card matang">
        <div class="stat-icon">🔴</div>
        <div class="stat-label">Total Matang</div>
        <div class="stat-value" id="statMatang"><?= number_format($rekap['total_matang']) ?></div>
    </div>

    <div class="stat-card setengah">
        <div class="stat-icon">🟡</div>
        <div class="stat-label">Total Setengah Matang</div>
        <div class="stat-value" id="statSetengah"><?= number_format($rekap['total_setengah']) ?></div>
    </div>

    <div class="stat-card belum">
        <div class="stat-icon">🟢</div>
        <div class="stat-label">Total Belum Matang</div>
        <div class="stat-value" id="statBelum"><?= number_format($rekap['total_belum']) ?></div>
    </div>

    <div class="stat-card total">
        <div class="stat-icon">🍅</div>
        <div class="stat-label">Total Semua</div>
        <div class="stat-value" id="statSemua"><?= number_format($rekap['total_semua']) ?></div>
    </div>
</div>

<!-- Data Masuk Realtime -->
<div class="table-container">
    <div class="table-header">
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <h3>📥 Data Masuk Realtime</h3>
            <span class="badge" style="background:#E3F2FD; color:#1565C0; border:1px solid #BBDEFB; font-size:0.75rem; font-weight:600;">⏱️ Auto-update: 10 Detik</span>
            <span class="status-time" id="lastUpdateTime">Memuat data...</span>
        </div>

        <div class="actions" style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
            <button type="button" class="btn btn-warning" id="btnResetCounter" onclick="handleResetCounter()">
                🔄 Reset Counter
            </button>
            <button type="button" class="btn btn-outline btn-sm" id="btnClearData" onclick="clearIncomingData()">
                🧹 Bersihkan Data Masuk
            </button>
        </div>
    </div>
    <div class="table-responsive">
        <table id="recentTable">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('recentTable', 0, 'num')">No <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('recentTable', 1, 'str')">Tanggal <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('recentTable', 2, 'str')">Waktu <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('recentTable', 3, 'str')">Jenis Klasifikasi <span class="sort-indicator"></span></th>
                    <th>Nilai Fitur (HSV & RGB)</th>
                    <th class="sortable" onclick="sortTable('recentTable', 5, 'num')">Total Matang <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('recentTable', 6, 'num')">Total Setengah <span class="sort-indicator"></span></th>
                    <th class="sortable" onclick="sortTable('recentTable', 7, 'num')">Total Belum <span class="sort-indicator"></span></th>
                    <th>Foto</th>
                </tr>
            </thead>
            <tbody id="recentTableBody">
                <tr>
                    <td colspan="9" class="text-center py-4">Memuat data realtime...</td>
                </tr>
            </tbody>
        </table>
        <div id="emptyDataState" class="empty-state" style="display: none;">
            <div class="empty-icon">📭</div>
            <p id="emptyStateMessage">Belum ada data masuk pada tanggal ini</p>
        </div>
    </div>
</div>

<script>
const BASE_URL = '<?= BASE_URL ?>';
const filterDate = '<?= $filter_date ?>';
let clearedUntilId = 0;
let isFirstLoad = true;

// Toast notification helper
function showToast(message, type = 'success') {
    const toast = document.getElementById('toastNotification');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast-notification show ' + type;
    setTimeout(() => {
        toast.className = 'toast-notification';
    }, 3500);
}

// Format badge jenis klasifikasi
function getBadgeHtml(jenis) {
    let badgeClass = 'badge-matang';
    let icon = '🔴';
    if (jenis === 'Setengah Matang') {
        badgeClass = 'badge-setengah';
        icon = '🟡';
    } else if (jenis === 'Belum Matang') {
        badgeClass = 'badge-belum';
        icon = '🟢';
    }
    return `<span class="badge ${badgeClass}">${icon} ${jenis}</span>`;
}

// Bersihkan data masuk dari tampilan dashboard
function clearIncomingData() {
    const rows = document.querySelectorAll('#recentTableBody tr[data-id]');
    if (rows.length > 0) {
        const topId = parseInt(rows[0].getAttribute('data-id')) || 0;
        clearedUntilId = topId;
        localStorage.setItem('clearedUntilId_' + filterDate, topId);
    }
    renderEmptyState('Tampilan data masuk telah dibersihkan. Menunggu data baru...');
    showToast('Tampilan data masuk berhasil dibersihkan.', 'info');
}

function renderEmptyState(msg) {
    const tbody = document.getElementById('recentTableBody');
    tbody.innerHTML = '';
    const emptyState = document.getElementById('emptyDataState');
    const emptyMsg = document.getElementById('emptyStateMessage');
    if (emptyState && emptyMsg) {
        emptyMsg.textContent = msg || 'Belum ada data masuk pada tanggal ini';
        emptyState.style.display = 'block';
    }
}

// Reset Counter Action
function handleResetCounter() {
    if (!confirm('Apakah Anda yakin ingin mereset counter hitungan? Hitungan kumulatif untuk data baru berikutnya akan dimulai kembali dari 0.')) {
        return;
    }

    const btn = document.getElementById('btnResetCounter');
    btn.disabled = true;
    btn.textContent = '⏳ Memproses...';

    fetch(BASE_URL + '/api/reset_counter.php', {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = '🔄 Reset Counter';
        if (data.status === 'success') {
            showToast('✅ Counter hitungan berhasil direset! Sesi baru #' + data.session_id);
            if (document.getElementById('sessionBadge')) {
                document.getElementById('sessionBadge').textContent = 'Sesi Hitungan: #' + data.session_id;
            }
            fetchRealtimeData();
        } else {
            showToast('❌ ' + (data.message || 'Gagal mereset counter'), 'error');
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '🔄 Reset Counter';
        showToast('❌ Terjadi kesalahan jaringan saat mereset counter', 'error');
    });
}

// Fetch realtime dashboard data
function fetchRealtimeData() {
    fetch(`${BASE_URL}/api/dashboard_realtime.php?tanggal=${filterDate}&t=${Date.now()}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                // Update stats cards
                document.getElementById('statMatang').textContent = Number(data.date_totals.total_matang).toLocaleString('id-ID');
                document.getElementById('statSetengah').textContent = Number(data.date_totals.total_setengah).toLocaleString('id-ID');
                document.getElementById('statBelum').textContent = Number(data.date_totals.total_belum).toLocaleString('id-ID');
                document.getElementById('statSemua').textContent = Number(data.date_totals.total_semua).toLocaleString('id-ID');

                if (document.getElementById('sessionBadge')) {
                    document.getElementById('sessionBadge').textContent = 'Sesi Hitungan: #' + data.session_id;
                }

                // Update server time
                const timeEl = document.getElementById('lastUpdateTime');
                if (timeEl) {
                    timeEl.textContent = `Diperbarui: ${data.server_time}`;
                }

                // Filter out cleared items if user clicked "Bersihkan"
                const savedCleared = parseInt(localStorage.getItem('clearedUntilId_' + filterDate)) || 0;
                if (savedCleared > clearedUntilId) {
                    clearedUntilId = savedCleared;
                }

                const visibleRows = data.recent.filter(item => item.id > clearedUntilId);
                const tbody = document.getElementById('recentTableBody');
                const emptyState = document.getElementById('emptyDataState');

                if (visibleRows.length > 0) {
                    emptyState.style.display = 'none';
                    let html = '';
                    visibleRows.forEach((row, idx) => {
                        const fotoHtml = row.foto
                            ? `<a href="${BASE_URL}/${row.foto}" target="_blank"><img src="${BASE_URL}/${row.foto}" alt="foto" style="height:36px; border-radius:4px; cursor:pointer; object-fit:cover;"></a>`
                            : '<span style="color:#aaa;">—</span>';

                        let fiturHtml = '<span style="color:#aaa;">—</span>';
                        if (row.fitur) {
                            const rawFitur = row.fitur;
                            let shortFitur = rawFitur;
                            if (shortFitur.length > 28) {
                                shortFitur = shortFitur.substring(0, 26) + '...';
                            }
                            const safeRaw = encodeURIComponent(rawFitur);
                            fiturHtml = `<span class="fitur-badge" onclick="showFiturModal('${safeRaw}')" title="Klik untuk rincian HSV & RGB: ${escapeHtml(rawFitur)}">📊 ${escapeHtml(shortFitur)}</span>`;
                        }

                        html += `
                            <tr data-id="${row.id}" class="${idx === 0 && !isFirstLoad ? 'row-highlight' : ''}">
                                <td>${idx + 1}</td>
                                <td>${row.tanggal}</td>
                                <td><strong>${row.waktu}</strong></td>
                                <td>${getBadgeHtml(row.jenis)}</td>
                                <td class="fitur-cell">${fiturHtml}</td>
                                <td><span class="badge badge-matang">🔴 ${row.total_matang}</span></td>
                                <td><span class="badge badge-setengah">🟡 ${row.total_setengah}</span></td>
                                <td><span class="badge badge-belum">🟢 ${row.total_belum}</span></td>
                                <td>${fotoHtml}</td>
                            </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                } else {
                    renderEmptyState(clearedUntilId > 0 ? 'Tampilan data masuk telah dibersihkan. Menunggu data baru...' : 'Belum ada data masuk pada tanggal ini');
                }

                isFirstLoad = false;
            }
        })
        .catch(err => {
            console.error('Error fetching realtime data:', err);
        });
}

// Inisialisasi polling berkala tiap 10 detik
document.addEventListener('DOMContentLoaded', () => {
    fetchRealtimeData();
    setInterval(fetchRealtimeData, 10000); // 10 detik (10000 ms)
});
</script>

<?php include __DIR__ . '/../includes/footer.php'; ?>
