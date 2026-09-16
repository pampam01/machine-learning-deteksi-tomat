        </div><!-- /.content-wrapper -->
    </main><!-- /.main-content -->

    <!-- Modal Detail Fitur (HSV & RGB) -->
    <div class="modal-overlay" id="modalDetailFitur">
        <div class="modal-container" style="max-width: 520px;">
            <div class="modal-header">
                <h3>📊 Rincian Nilai Fitur (HSV & RGB)</h3>
                <button type="button" class="modal-close" onclick="closeModal('modalDetailFitur')">&times;</button>
            </div>
            <div class="modal-body" id="modalDetailFiturBody" style="padding: 20px;">
                <!-- Konten dinamis diisi JS -->
            </div>
            <div class="modal-footer" style="padding: 12px 20px; text-align: right; background: var(--gray-50); border-top: 1px solid var(--gray-200);">
                <button type="button" class="btn btn-outline btn-sm" onclick="closeModal('modalDetailFitur')">Tutup</button>
            </div>
        </div>
    </div>

    <?php
    $js_path = dirname(__DIR__) . '/assets/js/main.js';
    $js_ver = file_exists($js_path) ? filemtime($js_path) : time();
    ?>
    <script src="<?= BASE_URL ?>/assets/js/main.js?v=<?= $js_ver ?>"></script>
</body>
</html>
<?php ob_end_flush(); ?>
