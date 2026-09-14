<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

$error = '';
$success = '';

// Proses tambah admin
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];

    if ($action === 'add') {
        $username = trim($_POST['username'] ?? '');
        $password = $_POST['password'] ?? '';
        $nama = trim($_POST['nama'] ?? '');

        if (empty($username) || empty($password) || empty($nama)) {
            $error = 'Semua field harus diisi.';
        } else {
            // Cek username unik
            $check = $conn->prepare("SELECT id FROM admin WHERE username = ?");
            $check->bind_param("s", $username);
            $check->execute();
            if ($check->get_result()->num_rows > 0) {
                $error = 'Username sudah digunakan.';
            } else {
                $hashed = password_hash($password, PASSWORD_DEFAULT);
                $stmt = $conn->prepare("INSERT INTO admin (username, password, nama) VALUES (?, ?, ?)");
                $stmt->bind_param("sss", $username, $hashed, $nama);
                if ($stmt->execute()) {
                    $success = 'Admin berhasil ditambahkan.';
                } else {
                    $error = 'Gagal menambahkan admin.';
                }
                $stmt->close();
            }
            $check->close();
        }
    }

    if ($action === 'edit') {
        $id = intval($_POST['id'] ?? 0);
        $username = trim($_POST['username'] ?? '');
        $nama = trim($_POST['nama'] ?? '');
        $password = $_POST['password'] ?? '';

        if (empty($username) || empty($nama)) {
            $error = 'Username dan nama harus diisi.';
        } else {
            // Cek username unik (exclude current)
            $check = $conn->prepare("SELECT id FROM admin WHERE username = ? AND id != ?");
            $check->bind_param("si", $username, $id);
            $check->execute();
            if ($check->get_result()->num_rows > 0) {
                $error = 'Username sudah digunakan.';
            } else {
                if (!empty($password)) {
                    $hashed = password_hash($password, PASSWORD_DEFAULT);
                    $stmt = $conn->prepare("UPDATE admin SET username = ?, password = ?, nama = ? WHERE id = ?");
                    $stmt->bind_param("sssi", $username, $hashed, $nama, $id);
                } else {
                    $stmt = $conn->prepare("UPDATE admin SET username = ?, nama = ? WHERE id = ?");
                    $stmt->bind_param("ssi", $username, $nama, $id);
                }
                if ($stmt->execute()) {
                    $success = 'Data admin berhasil diperbarui.';
                    // Update session jika edit diri sendiri
                    if ($id == $_SESSION['admin_id']) {
                        $_SESSION['admin_username'] = $username;
                        $_SESSION['admin_nama'] = $nama;
                    }
                } else {
                    $error = 'Gagal memperbarui data admin.';
                }
                $stmt->close();
            }
            $check->close();
        }
    }

    if ($action === 'delete') {
        $id = intval($_POST['id'] ?? 0);
        if ($id == $_SESSION['admin_id']) {
            $error = 'Tidak dapat menghapus akun yang sedang digunakan.';
        } else {
            $stmt = $conn->prepare("DELETE FROM admin WHERE id = ?");
            $stmt->bind_param("i", $id);
            if ($stmt->execute()) {
                $success = 'Admin berhasil dihapus.';
            } else {
                $error = 'Gagal menghapus admin.';
            }
            $stmt->close();
        }
    }
}

// Ambil semua admin
$admins = $conn->query("SELECT id, username, nama, created_at FROM admin ORDER BY id ASC");

include __DIR__ . '/../includes/header.php';
?>

<div class="page-header">
    <h2>Data Admin</h2>
    <p>Kelola akun administrator</p>
</div>

<?php if ($error): ?>
    <div class="alert alert-error">⚠️ <?= htmlspecialchars($error) ?></div>
<?php endif; ?>

<?php if ($success): ?>
    <div class="alert alert-success">✅ <?= htmlspecialchars($success) ?></div>
<?php endif; ?>

<div class="table-container">
    <div class="table-header">
        <h3>👤 Daftar Admin</h3>
        <button class="btn btn-primary btn-sm" onclick="openModal('modalTambah')">+ Tambah Admin</button>
    </div>

    <div class="table-responsive">
        <?php if ($admins && $admins->num_rows > 0): ?>
        <table>
            <thead>
                <tr>
                    <th>No</th>
                    <th>Username</th>
                    <th>Nama</th>
                    <th>Dibuat</th>
                    <th>Aksi</th>
                </tr>
            </thead>
            <tbody>
                <?php $no = 1; while ($row = $admins->fetch_assoc()): ?>
                <tr>
                    <td><?= $no++ ?></td>
                    <td><strong><?= htmlspecialchars($row['username']) ?></strong></td>
                    <td><?= htmlspecialchars($row['nama']) ?></td>
                    <td><?= date('d/m/Y', strtotime($row['created_at'])) ?></td>
                    <td>
                        <div class="actions">
                            <button class="btn btn-outline btn-sm" 
                                onclick="editAdmin(<?= $row['id'] ?>, '<?= htmlspecialchars($row['username'], ENT_QUOTES) ?>', '<?= htmlspecialchars($row['nama'], ENT_QUOTES) ?>')">
                                ✏️ Edit
                            </button>
                            <?php if ($row['id'] != $_SESSION['admin_id']): ?>
                            <form method="POST" style="display:inline" onsubmit="return confirmDelete(this, '<?= htmlspecialchars($row['nama'], ENT_QUOTES) ?>')">
                                <input type="hidden" name="action" value="delete">
                                <input type="hidden" name="id" value="<?= $row['id'] ?>">
                                <button type="submit" class="btn btn-danger btn-sm">🗑️ Hapus</button>
                            </form>
                            <?php endif; ?>
                        </div>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
        <?php else: ?>
        <div class="empty-state">
            <div class="empty-icon">👤</div>
            <p>Belum ada data admin</p>
        </div>
        <?php endif; ?>
    </div>
</div>

<!-- Modal Tambah Admin -->
<div class="modal-overlay" id="modalTambah">
    <div class="modal">
        <div class="modal-header">
            <h3>Tambah Admin Baru</h3>
            <button class="modal-close" onclick="closeModal('modalTambah')">×</button>
        </div>
        <form method="POST" action="">
            <div class="modal-body">
                <input type="hidden" name="action" value="add">
                <div class="form-group">
                    <label for="addNama">Nama Lengkap</label>
                    <input type="text" id="addNama" name="nama" placeholder="Masukkan nama" required>
                </div>
                <div class="form-group">
                    <label for="addUsername">Username</label>
                    <input type="text" id="addUsername" name="username" placeholder="Masukkan username" required>
                </div>
                <div class="form-group">
                    <label for="addPassword">Password</label>
                    <input type="password" id="addPassword" name="password" placeholder="Masukkan password" required>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeModal('modalTambah')">Batal</button>
                <button type="submit" class="btn btn-primary">Simpan</button>
            </div>
        </form>
    </div>
</div>

<!-- Modal Edit Admin -->
<div class="modal-overlay" id="modalEdit">
    <div class="modal">
        <div class="modal-header">
            <h3>Edit Admin</h3>
            <button class="modal-close" onclick="closeModal('modalEdit')">×</button>
        </div>
        <form method="POST" action="">
            <div class="modal-body">
                <input type="hidden" name="action" value="edit">
                <input type="hidden" name="id" id="editId">
                <div class="form-group">
                    <label for="editNama">Nama Lengkap</label>
                    <input type="text" id="editNama" name="nama" required>
                </div>
                <div class="form-group">
                    <label for="editUsername">Username</label>
                    <input type="text" id="editUsername" name="username" required>
                </div>
                <div class="form-group">
                    <label for="editPassword">Password Baru (kosongkan jika tidak diubah)</label>
                    <input type="password" id="editPassword" name="password" placeholder="Kosongkan jika tidak diubah">
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeModal('modalEdit')">Batal</button>
                <button type="submit" class="btn btn-primary">Simpan</button>
            </div>
        </form>
    </div>
</div>

<script>
function editAdmin(id, username, nama) {
    document.getElementById('editId').value = id;
    document.getElementById('editUsername').value = username;
    document.getElementById('editNama').value = nama;
    document.getElementById('editPassword').value = '';
    openModal('modalEdit');
}
</script>

<?php include __DIR__ . '/../includes/footer.php'; ?>
