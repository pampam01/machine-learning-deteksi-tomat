<?php
/**
 * Entry Point - Tomata IoT
 * Redirect ke dashboard (jika login) atau ke login page
 */
require_once __DIR__ . '/includes/auth.php';

if (isLoggedIn()) {
    header('Location: ' . BASE_URL . '/pages/dashboard');
} else {
    header('Location: ' . BASE_URL . '/pages/login');
}
exit();
?>
