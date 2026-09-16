<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';

redirectIfLoggedIn();

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';

    if (empty($username) || empty($password)) {
        $error = 'Username dan password harus diisi.';
    } else {
        $stmt = $conn->prepare("SELECT id, username, password, nama FROM admin WHERE username = ?");
        $stmt->bind_param("s", $username);
        $stmt->execute();
        $result = $stmt->get_result();

        if ($result->num_rows === 1) {
            $admin = $result->fetch_assoc();
            if (password_verify($password, $admin['password'])) {
                $_SESSION['admin_id'] = $admin['id'];
                $_SESSION['admin_username'] = $admin['username'];
                $_SESSION['admin_nama'] = $admin['nama'];
                header('Location: ' . BASE_URL . '/pages/dashboard');
                exit();
            } else {
                $error = 'Password salah.';
            }
        } else {
            $error = 'Username tidak ditemukan.';
        }
        $stmt->close();
    }
}

$css_path = dirname(__DIR__) . '/assets/css/style.css';
$css_ver = file_exists($css_path) ? filemtime($css_path) : time();
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Login - Sistem IoT Klasifikasi Kematangan Tomat">
    <title>Login - Tomata IoT</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css?v=<?= $css_ver ?>">
</head>
<body class="login-page">
    <div class="login-container">
        <div class="login-header">
            <span class="login-icon">🍅</span>
            <h2>Tomata IoT</h2>
            <p>Sistem Klasifikasi Kematangan Tomat</p>
        </div>

        <?php if ($error): ?>
            <div class="alert alert-error">
                ⚠️ <?= htmlspecialchars($error) ?>
            </div>
        <?php endif; ?>

        <form method="POST" action="" id="loginForm">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="Masukkan username" 
                       value="<?= htmlspecialchars($username ?? '') ?>" required autofocus>
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Masukkan password" required>
            </div>

            <button type="submit" class="btn btn-primary btn-login">Masuk</button>
        </form>
    </div>
</body>
</html>
