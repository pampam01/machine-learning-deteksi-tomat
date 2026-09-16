<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/database.php';
requireLogin();

include __DIR__ . '/../includes/header.php';
?>

<div class="page-header">
    <div>
        <h2>🧪 Simulator & Tes Input Data</h2>
        <p>Gunakan halaman ini untuk menguji pengiriman data klasifikasi tomat ke Web API secara langsung tanpa memerlukan kamera atau ESP32.</p>
    </div>
</div>

<div class="stats-grid" style="margin-bottom: 24px;">
    <div class="stat-card matang" style="cursor: pointer;" onclick="quickSend('Matang')">
        <div class="stat-header">
            <span class="stat-label">Klik Cepat Tes</span>
            <span class="stat-icon">🔴</span>
        </div>
        <div class="stat-value" style="font-size: 1.25rem;">+1 Matang</div>
        <p style="font-size: 0.8rem; color: #666; margin-top: 8px;">Kirim 1 buah tomat Matang (Merah)</p>
    </div>

    <div class="stat-card setengah" style="cursor: pointer;" onclick="quickSend('Setengah Matang')">
        <div class="stat-header">
            <span class="stat-label">Klik Cepat Tes</span>
            <span class="stat-icon">🟡</span>
        </div>
        <div class="stat-value" style="font-size: 1.25rem;">+1 Setengah</div>
        <p style="font-size: 0.8rem; color: #666; margin-top: 8px;">Kirim 1 tomat Setengah Matang (Kuning)</p>
    </div>

    <div class="stat-card belum" style="cursor: pointer;" onclick="quickSend('Belum Matang')">
        <div class="stat-header">
            <span class="stat-label">Klik Cepat Tes</span>
            <span class="stat-icon">🟢</span>
        </div>
        <div class="stat-value" style="font-size: 1.25rem;">+1 Belum Matang</div>
        <p style="font-size: 0.8rem; color: #666; margin-top: 8px;">Kirim 1 buah tomat Mentah (Hijau)</p>
    </div>

    <div class="stat-card total" style="cursor: pointer;" onclick="toggleAutoSim()">
        <div class="stat-header">
            <span class="stat-label">Mode Otomatis</span>
            <span class="stat-icon" id="autoSimIcon">⚙️</span>
        </div>
        <div class="stat-value" style="font-size: 1.25rem;" id="autoSimText">Mulai Auto Sim</div>
        <p style="font-size: 0.8rem; color: #666; margin-top: 8px;" id="autoSimDesc">Kirim acak tiap 3 detik</p>
    </div>
</div>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px;">
    <!-- Form Custom Data -->
    <div class="table-container" style="padding: 24px;">
        <h3 style="margin-bottom: 16px; font-size: 1.1rem; color: var(--gray-900);">📝 Form Input Kustom</h3>
        <form id="customTestForm" onsubmit="handleCustomSubmit(event)">
            <div class="form-group">
                <label for="inputJenis">Kategori Kematangan</label>
                <select id="inputJenis" name="jenis" style="width: 100%; padding: 10px 12px; border: 1px solid var(--gray-300); border-radius: var(--border-radius-sm); font-size: 0.95rem;" required>
                    <option value="Matang">Matang (Merah)</option>
                    <option value="Setengah Matang">Setengah Matang (Oranye/Kuning)</option>
                    <option value="Belum Matang">Belum Matang (Hijau/Mentah)</option>
                </select>
            </div>

            <div class="form-group">
                <label for="inputJumlah">Jumlah Tomat</label>
                <input type="number" id="inputJumlah" name="jumlah" value="1" min="1" max="100" style="width: 100%; padding: 10px 12px; border: 1px solid var(--gray-300); border-radius: var(--border-radius-sm); font-size: 0.95rem;" required>
            </div>

            <div class="form-group">
                <label for="inputFitur">Nilai Fitur HSV / Catatan (Opsional)</label>
                <input type="text" id="inputFitur" name="fitur" placeholder="Contoh: HSV: (12, 185, 205) | RGB: (215, 45, 30)" value="HSV: (12, 185, 205) | RGB: (215, 45, 30)" style="width: 100%; padding: 10px 12px; border: 1px solid var(--gray-300); border-radius: var(--border-radius-sm); font-size: 0.95rem;">
            </div>

            <div class="form-group">
                <label for="inputFoto">Upload Foto Tomat (Opsional)</label>
                <input type="file" id="inputFoto" name="foto" accept="image/*" style="width: 100%; padding: 8px; border: 1px dashed var(--gray-300); border-radius: var(--border-radius-sm); font-size: 0.85rem;">
            </div>

            <div style="display: flex; gap: 12px; margin-top: 20px;">
                <button type="submit" id="btnSubmitCustom" class="btn btn-primary" style="flex: 1;">🚀 Kirim Data ke API</button>
                <a href="<?= BASE_URL ?>/pages/dashboard" class="btn btn-outline" style="text-align: center; display: inline-flex; align-items: center; justify-content: center;">📊 Lihat Dashboard</a>
            </div>
        </form>
    </div>

    <!-- Output Console & Live Response -->
    <div class="table-container" style="padding: 24px; display: flex; flex-direction: column;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 style="font-size: 1.1rem; color: var(--gray-900);">📡 Respon Server (API Logger)</h3>
            <button type="button" onclick="clearLog()" class="btn btn-outline btn-sm">Bersihkan Log</button>
        </div>

        <div id="apiStatusBadge" style="margin-bottom: 12px; display: none;">
            <span class="badge badge-matang" id="statusBadgeText">✅ Sukses</span>
        </div>

        <pre id="apiResponseBox" style="flex: 1; min-height: 250px; max-height: 380px; overflow-y: auto; background: #1e1e1e; color: #4ec9b0; padding: 16px; border-radius: 8px; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.85rem; line-height: 1.5; white-space: pre-wrap; word-break: break-all;">Menunggu pengiriman data...</pre>
    </div>
</div>

<script>
const API_URL = '<?= BASE_URL ?>/api/klasifikasi.php';
let autoSimInterval = null;

// Fungsi Quick Send
function quickSend(jenis) {
    let fiturDummy = 'H: 15.0, S: 200, V: 180';
    if (jenis === 'Matang') {
        fiturDummy = 'H: 8.5, S: 215, V: 190 (R:89.2% K:9.8% H:1.0%)';
    } else if (jenis === 'Setengah Matang') {
        fiturDummy = 'H: 23.4, S: 195, V: 188 (R:22.5% K:65.0% H:12.5%)';
    } else if (jenis === 'Belum Matang') {
        fiturDummy = 'H: 54.1, S: 182, V: 165 (R:1.0% K:11.5% H:87.5%)';
    }

    const payload = {
        jenis: jenis,
        jumlah: 1,
        fitur: fiturDummy
    };

    sendDataJson(payload);
}

// Kirim data JSON
function sendDataJson(data) {
    const box = document.getElementById('apiResponseBox');
    box.textContent = '⏳ Mengirim ke ' + API_URL + '...\n\nPayload:\n' + JSON.stringify(data, null, 2);

    fetch(API_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(async res => {
        const text = await res.text();
        let parsed;
        try {
            parsed = JSON.parse(text);
        } catch(e) {
            parsed = text;
        }
        updateLog(res.status, parsed);
    })
    .catch(err => {
        updateLog('ERROR', { error: err.message });
    });
}

// Kirim Form dengan Multipart (mendukung upload gambar)
function handleCustomSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSubmitCustom');
    btn.disabled = true;
    btn.textContent = '⏳ Mengirim...';

    const form = document.getElementById('customTestForm');
    const formData = new FormData(form);

    const box = document.getElementById('apiResponseBox');
    box.textContent = '⏳ Mengirim FormData ke ' + API_URL + '...';

    fetch(API_URL, {
        method: 'POST',
        body: formData
    })
    .then(async res => {
        btn.disabled = false;
        btn.textContent = '🚀 Kirim Data ke API';
        const text = await res.text();
        let parsed;
        try {
            parsed = JSON.parse(text);
        } catch(e) {
            parsed = text;
        }
        updateLog(res.status, parsed);
    })
    .catch(err => {
        btn.disabled = false;
        btn.textContent = '🚀 Kirim Data ke API';
        updateLog('ERROR', { error: err.message });
    });
}

function updateLog(status, data) {
    const box = document.getElementById('apiResponseBox');
    const badge = document.getElementById('apiStatusBadge');
    const badgeText = document.getElementById('statusBadgeText');

    badge.style.display = 'block';
    if (status === 200 || status === 201 || (data && data.status === 'success')) {
        badgeText.className = 'badge badge-matang';
        badgeText.textContent = `✅ Status: ${status} (Berhasil Disimpan)`;
    } else {
        badgeText.className = 'badge badge-belum';
        badgeText.textContent = `❌ Status: ${status} (Gagal)`;
    }

    const timestamp = new Date().toLocaleTimeString('id-ID');
    const formatted = typeof data === 'object' ? JSON.stringify(data, null, 2) : data;
    box.textContent = `[${timestamp}] Response Code: ${status}\n\n${formatted}\n\n-------------------------\n` + box.textContent;
}

function clearLog() {
    document.getElementById('apiResponseBox').textContent = 'Log dibersihkan. Siap menerima data baru...';
    document.getElementById('apiStatusBadge').style.display = 'none';
}

// Simulasi Pengiriman Otomatis Tiap 3 Detik
function toggleAutoSim() {
    const textEl = document.getElementById('autoSimText');
    const descEl = document.getElementById('autoSimDesc');
    const iconEl = document.getElementById('autoSimIcon');

    if (autoSimInterval) {
        clearInterval(autoSimInterval);
        autoSimInterval = null;
        textEl.textContent = 'Mulai Auto Sim';
        descEl.textContent = 'Kirim acak tiap 3 detik';
        iconEl.textContent = '⚙️';
    } else {
        const classes = ['Matang', 'Setengah Matang', 'Belum Matang'];
        autoSimInterval = setInterval(() => {
            const randomJenis = classes[Math.floor(Math.random() * classes.length)];
            let fiturStr = '';
            if (randomJenis === 'Matang') {
                fiturStr = `H: ${(7 + Math.random()*3).toFixed(1)}, S: ${Math.floor(200 + Math.random()*40)}, V: ${Math.floor(175 + Math.random()*30)} (R:89% K:10% H:1%)`;
            } else if (randomJenis === 'Setengah Matang') {
                fiturStr = `H: ${(22 + Math.random()*5).toFixed(1)}, S: ${Math.floor(190 + Math.random()*30)}, V: ${Math.floor(180 + Math.random()*25)} (R:25% K:63% H:12%)`;
            } else {
                fiturStr = `H: ${(50 + Math.random()*8).toFixed(1)}, S: ${Math.floor(170 + Math.random()*35)}, V: ${Math.floor(160 + Math.random()*30)} (R:1% K:12% H:87%)`;
            }
            const payload = {
                jenis: randomJenis,
                jumlah: 1,
                fitur: fiturStr
            };
            sendDataJson(payload);
        }, 3000);

        textEl.textContent = 'Hentikan Auto Sim';
        descEl.textContent = '🟢 Sedang berjalan (3 detik/data)...';
        iconEl.textContent = '⏹️';
    }
}
</script>

<?php include __DIR__ . '/../includes/footer.php'; ?>
