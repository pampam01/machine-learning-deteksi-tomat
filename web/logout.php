<?php
/**
 * Logout - Hapus session dan redirect ke login
 */
require_once __DIR__ . '/includes/auth.php';
session_unset();
session_destroy();
header('Location: ' . BASE_URL . '/pages/login.php');
exit();
?>
