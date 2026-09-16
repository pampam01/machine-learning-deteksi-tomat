// =============================================
// Tomata IoT - JavaScript Utama
// =============================================

document.addEventListener('DOMContentLoaded', function () {

    // === Sidebar Toggle (Mobile & Tablet) ===
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleButtons = document.querySelectorAll('.sidebar-toggle, .topbar-toggle, #sidebarToggle, #mobileToggle');

    function toggleSidebar() {
        if (!sidebar) return;
        const isActive = sidebar.classList.toggle('active');
        if (overlay) overlay.classList.toggle('active', isActive);
        document.body.style.overflow = (isActive && window.innerWidth <= 992) ? 'hidden' : '';
    }

    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    toggleButtons.forEach(btn => {
        btn.addEventListener('click', toggleSidebar);
    });

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // Tutup sidebar otomatis saat link menu diklik pada layar kecil
    document.querySelectorAll('.sidebar-menu a').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 992) closeSidebar();
        });
    });

    // Escape key listener untuk menutup modal dan sidebar
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeSidebar();
            document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
            document.body.style.overflow = '';
        }
    });

    // === Modal System ===
    window.openModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    };

    window.closeModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    // Close modal on overlay click
    document.querySelectorAll('.modal-overlay').forEach(modal => {
        modal.addEventListener('click', function (e) {
            if (e.target === this) {
                this.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // === Konfirmasi Hapus ===
    window.confirmDelete = function (form, name) {
        if (confirm('Yakin ingin menghapus ' + name + '?')) {
            form.submit();
        }
        return false;
    };

    // === Auto-hide alerts ===
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            alert.style.transition = 'all 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 4000);
    });

    // === Modal Detail Fitur HSV & RGB ===
    window.showFiturModal = function (encodedStr) {
        try {
            const rawStr = decodeURIComponent(encodedStr);
            const modalBody = document.getElementById('modalDetailFiturBody');
            if (!modalBody) return;

            let html = `
                <div style="margin-bottom: 16px;">
                    <label style="font-size:0.8rem; font-weight:600; color:var(--gray-600); text-transform:uppercase;">Data Fitur (HSV & RGB)</label>
                    <div style="background:#212121; color:#A5D6A7; padding:12px 14px; border-radius:8px; font-family:monospace; font-size:0.85rem; word-break:break-all; max-height:220px; overflow-y:auto; margin-top:6px; line-height:1.5;">
                        ${escapeHtml(rawStr)}
                    </div>
                </div>
                <div style="background:#F1F8E9; border-left:4px solid #4CAF50; padding:10px 14px; border-radius:4px; font-size:0.85rem; color:#1B5E20;">
                    💡 Nilai fitur ini merupakan hasil ekstraksi histogram warna HSV & RGB yang menjadi acuan keputusan klasifikasi kematangan pohon C4.5.
                </div>
            `;
            modalBody.innerHTML = html;
            window.openModal('modalDetailFitur');
        } catch (e) {
            console.error('Error opening fitur modal:', e);
        }
    };

    function escapeHtml(str) {
        return (str || '').replace(/[&<>"']/g, function (m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
        });
    }

    // === Global Table Sorting Function ===
    window.sortTable = function (tableIdOrElem, colIndex, type) {
        let table = typeof tableIdOrElem === 'string' ? document.getElementById(tableIdOrElem) : tableIdOrElem;
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length <= 1) return;

        const thead = table.querySelector('thead');
        const thList = thead ? thead.querySelectorAll('th') : [];
        const clickedTh = thList[colIndex];

        let isAsc = true;
        if (clickedTh) {
            if (clickedTh.classList.contains('asc')) {
                isAsc = false;
                clickedTh.classList.remove('asc');
                clickedTh.classList.add('desc');
            } else {
                isAsc = true;
                thList.forEach(th => th.classList.remove('asc', 'desc'));
                clickedTh.classList.add('asc');
            }
        }

        rows.sort((rowA, rowB) => {
            const cellA = rowA.children[colIndex] ? rowA.children[colIndex].innerText.trim() : '';
            const cellB = rowB.children[colIndex] ? rowB.children[colIndex].innerText.trim() : '';

            if (type === 'num') {
                const numA = parseFloat(cellA.replace(/[^0-9.-]/g, '')) || 0;
                const numB = parseFloat(cellB.replace(/[^0-9.-]/g, '')) || 0;
                return isAsc ? numA - numB : numB - numA;
            }

            return isAsc ? cellA.localeCompare(cellB, 'id', { numeric: true }) : cellB.localeCompare(cellA, 'id', { numeric: true });
        });

        rows.forEach(r => tbody.appendChild(r));
    };

});
