        </div><!-- /.content-wrapper -->
    </main><!-- /.main-content -->

    <?php
    $js_path = dirname(__DIR__) . '/assets/js/main.js';
    $js_ver = file_exists($js_path) ? filemtime($js_path) : time();
    ?>
    <script src="<?= BASE_URL ?>/assets/js/main.js?v=<?= $js_ver ?>"></script>
</body>
</html>
<?php ob_end_flush(); ?>
