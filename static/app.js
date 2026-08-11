// VisionTrack AI Frontend JavaScript Engine

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    checkAuthStatus();
    loadStats();
    loadPersons();
    loadVideosList();
    loadAttendanceList();
    loadAnalyticsCharts();
});

// Check Admin Authentication Status
let activeToken = localStorage.getItem('admin_token') || '';

async function checkAuthStatus() {
    const modal = document.getElementById('login-modal');
    try {
        const res = await fetch(`/api/auth-status?token=${encodeURIComponent(activeToken)}`);
        const data = await res.json();

        if (data.authenticated) {
            if (modal) modal.style.display = 'none';
            if (data.token) {
                activeToken = data.token;
                localStorage.setItem('admin_token', activeToken);
            }
            const userEl = document.getElementById('session-username');
            if (userEl) userEl.innerText = data.user || 'admin';
        } else {
            if (modal) modal.style.display = 'none';
        }
    } catch (err) {
        if (modal) modal.style.display = 'none';
    }
}

// Admin Login Form Submit
document.getElementById('form-admin-login').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const alertBox = document.getElementById('login-alert');

    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    alertBox.style.display = 'none';

    try {
        const res = await fetch('/api/login', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok && data.success) {
            activeToken = data.token;
            localStorage.setItem('admin_token', activeToken);
            document.getElementById('login-modal').style.display = 'none';
            document.getElementById('session-username').innerText = data.username;
            loadStats();
            loadPersons();
        } else {
            alertBox.className = 'alert-box error';
            alertBox.style.display = 'block';
            alertBox.innerText = data.detail || 'Invalid login credentials.';
        }
    } catch (err) {
        alertBox.className = 'alert-box error';
        alertBox.style.display = 'block';
        alertBox.innerText = 'Network error during login.';
    }
});

// Admin Logout
async function logoutAdmin() {
    try {
        const formData = new FormData();
        formData.append('session', activeToken);
        await fetch('/api/logout', { method: 'POST', body: formData });
    } catch (err) {}

    activeToken = '';
    localStorage.removeItem('admin_token');
    document.getElementById('login-modal').style.display = 'flex';
}

// View Navigation Logic
function switchView(targetView) {
    if (!targetView) return;
    const navButtons = document.querySelectorAll('.nav-btn');
    const viewPanels = document.querySelectorAll('.view-panel');

    navButtons.forEach(b => {
        if (b.getAttribute('data-view') === targetView) {
            b.classList.add('active');
        } else {
            b.classList.remove('active');
        }
    });

    viewPanels.forEach(p => {
        if (p.id === targetView) {
            p.classList.add('active');
            p.style.display = 'block';
        } else {
            p.classList.remove('active');
            p.style.display = 'none';
        }
    });

    try {
        if (targetView === 'view-dashboard') {
            loadStats();
            loadPersons();
            if (typeof loadAuditLogs === 'function') loadAuditLogs();
            if (typeof loadTelegramSettings === 'function') loadTelegramSettings();
            if (typeof loadSchedulerSettings === 'function') loadSchedulerSettings();
            if (typeof loadWebhookSettings === 'function') loadWebhookSettings();
            if (typeof loadAnalyticsCharts === 'function') loadAnalyticsCharts();
        } else if (targetView === 'view-video') {
            loadVideosList();
        } else if (targetView === 'view-attendance') {
            loadAttendanceList();
        } else if (targetView === 'view-webcam') {
            loadLiveAttendanceLogs();
        }
    } catch (err) {
        console.warn('Sub-task load notice:', err);
    }
}
window.switchView = switchView;

function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetView = btn.getAttribute('data-view');
            switchView(targetView);
        });
    });
}

// Load System Statistics
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        document.getElementById('hardware-engine').innerText = `Hardware: ${data.hardware}`;
        document.getElementById('stat-hardware').innerText = data.hardware;
        document.getElementById('stat-persons').innerText = data.enrolled_persons;
        document.getElementById('stat-vectors').innerText = data.total_vectors;
        document.getElementById('stat-reports').innerText = data.csv_reports;

        document.getElementById('sidebar-enrolled').innerText = data.enrolled_persons;
        document.getElementById('sidebar-vectors').innerText = data.total_vectors;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

// Load Persons Database Table
async function loadPersons() {
    const tbody = document.getElementById('persons-table-body');
    tbody.innerHTML = '<tr><td colspan="4" class="text-center">Loading database...</td></tr>';

    try {
        const res = await fetch('/api/persons');
        const data = await res.json();

        if (!data.persons || data.persons.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center">No enrolled persons found.</td></tr>';
            return;
        }

        tbody.innerHTML = data.persons.map(p => `
            <tr>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td><span style="background:rgba(251,191,36,0.15); padding:0.2rem 0.6rem; border-radius:12px; font-size:0.85rem; border:1px solid rgba(251,191,36,0.3); color:#fde047;">${escapeHtml(p.department || 'General')}</span></td>
                <td>${escapeHtml(p.role || 'Member')}</td>
                <td>${p.count} vector(s)</td>
                <td>${p.enrolled_at}</td>
                <td>
                    <a href="/api/generate-id-card/${encodeURIComponent(p.name)}" target="_blank" class="btn btn-secondary" style="padding:0.4rem 0.8rem; font-size:0.8rem; margin-right:0.3rem;">🆔 Smart ID Badge</a>
                    <button class="btn btn-danger" style="padding:0.4rem 0.8rem; font-size:0.8rem;" onclick="deletePerson('${escapeHtml(p.name)}')">🗑️ Delete</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading persons database.</td></tr>';
    }
}

// Delete Person
async function deletePerson(name) {
    if (!confirm(`Are you sure you want to delete '${name}' from the database?`)) return;

    try {
        const res = await fetch(`/api/person/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadStats();
            loadPersons();
        } else {
            alert(`Error: ${data.detail}`);
        }
    } catch (err) {
        alert('Failed to delete person.');
    }
}

// Form 1: File Enrollment
document.getElementById('form-file-enroll').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('enroll-name-file').value.trim();
    const fileInput = document.getElementById('enroll-file');
    const alertBox = document.getElementById('file-enroll-alert');

    if (!name || fileInput.files.length === 0) return;

    const formData = new FormData();
    formData.append('name', name);
    formData.append('file', fileInput.files[0]);

    alertBox.className = 'alert-box';
    alertBox.style.display = 'block';
    alertBox.innerText = 'Extracting facial embeddings...';

    try {
        const res = await fetch('/api/enroll', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            alertBox.className = 'alert-box success';
            alertBox.innerText = data.message;
            document.getElementById('form-file-enroll').reset();
            loadStats();
        } else {
            alertBox.className = 'alert-box error';
            alertBox.innerText = data.detail || 'Enrollment failed.';
        }
    } catch (err) {
        alertBox.className = 'alert-box error';
        alertBox.innerText = 'Network error during enrollment.';
    }
});

// Webcam Enrollment
let enrollStream = null;

async function startEnrollWebcam() {
    const video = document.getElementById('enroll-webcam-video');
    try {
        enrollStream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = enrollStream;
    } catch (err) {
        alert('Cannot access webcam: ' + err.message);
    }
}

async function captureAndEnrollWebcam() {
    const name = document.getElementById('enroll-name-cam').value.trim();
    const alertBox = document.getElementById('cam-enroll-alert');

    if (!name) {
        alert('Please enter person name first.');
        return;
    }

    const video = document.getElementById('enroll-webcam-video');
    const canvas = document.getElementById('enroll-canvas');

    if (!video.srcObject) {
        alert('Please start camera first.');
        return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const base64Data = canvas.toDataURL('image/jpeg');

    const formData = new FormData();
    formData.append('name', name);
    formData.append('image_base64', base64Data);

    alertBox.className = 'alert-box';
    alertBox.style.display = 'block';
    alertBox.innerText = 'Processing camera capture...';

    try {
        const res = await fetch('/api/enroll', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            alertBox.className = 'alert-box success';
            alertBox.innerText = data.message;
            loadStats();
        } else {
            alertBox.className = 'alert-box error';
            alertBox.innerText = data.detail || 'Webcam enrollment failed.';
        }
    } catch (err) {
        alertBox.className = 'alert-box error';
        alertBox.innerText = 'Network error during capture.';
    }
}

// Form 3: Bulk Batch Enrollment
document.getElementById('form-batch-enroll').addEventListener('submit', async (e) => {
    e.preventDefault();
    const filesInput = document.getElementById('batch-files');
    const alertBox = document.getElementById('batch-enroll-alert');
    const resultsDiv = document.getElementById('batch-enroll-results');

    if (filesInput.files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < filesInput.files.length; i++) {
        formData.append('files', filesInput.files[i]);
    }

    alertBox.className = 'alert-box';
    alertBox.style.display = 'block';
    alertBox.innerText = `Processing bulk registration for ${filesInput.files.length} photo(s)...`;
    resultsDiv.innerHTML = '';

    try {
        const res = await fetch('/api/enroll-batch', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            alertBox.className = 'alert-box success';
            alertBox.innerText = `Bulk Enrollment Completed! Successfully registered ${data.results.filter(r=>r.success).length}/${data.results.length} photo(s).`;

            let tableHtml = `
                <table class="data-table">
                    <thead><tr><th>File Name</th><th>Extracted Person Name</th><th>Status</th></tr></thead>
                    <tbody>
            `;
            data.results.forEach(r => {
                const statusBadge = r.success
                    ? `<span class="status-dot yellow" style="display:inline-block; margin-right:4px;"></span>Registered`
                    : `<span style="color:#ef4444;">Failed (${escapeHtml(r.message)})</span>`;
                tableHtml += `<tr><td>${escapeHtml(r.filename)}</td><td><strong>${escapeHtml(r.name)}</strong></td><td>${statusBadge}</td></tr>`;
            });
            tableHtml += '</tbody></table>';
            resultsDiv.innerHTML = tableHtml;

            document.getElementById('form-batch-enroll').reset();
            loadStats();
        } else {
            alertBox.className = 'alert-box error';
            alertBox.innerText = data.detail || 'Bulk enrollment failed.';
        }
    } catch (err) {
        alertBox.className = 'alert-box error';
        alertBox.innerText = 'Network error during bulk enrollment.';
    }
});

// Load Videos List
async function loadVideosList() {
    const select = document.getElementById('video-select-existing');
    try {
        const res = await fetch('/api/videos');
        const data = await res.json();

        select.innerHTML = '<option value="">-- Select from input_videos --</option>';
        if (data.input_videos) {
            data.input_videos.forEach(v => {
                select.innerHTML += `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`;
            });
        }
    } catch (err) {
        console.error('Failed to load videos:', err);
    }
}

// Submit Video Processing
document.getElementById('form-process-video').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('video-file-input');
    const selectExisting = document.getElementById('video-select-existing').value;
    const threshold = document.getElementById('video-thresh').value;
    const interval = document.getElementById('video-interval').value;

    const alertBox = document.getElementById('video-output-alert');
    const progressBox = document.getElementById('video-progress-container');
    const progressBar = document.getElementById('video-progress-bar');
    const progressText = document.getElementById('video-progress-text');

    const formData = new FormData();
    formData.append('threshold', threshold);
    formData.append('submit_every_n', interval);

    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    } else if (selectExisting) {
        formData.append('filename', selectExisting);
    } else {
        alert('Please select or upload a video file.');
        return;
    }

    progressBox.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.innerText = 'Initializing analysis...';
    alertBox.style.display = 'none';
    document.getElementById('video-result-panel').style.display = 'none';

    try {
        const res = await fetch('/api/process-video', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            pollJobStatus(data.job_id);
        } else {
            alertBox.className = 'alert-box error';
            alertBox.innerText = data.detail || 'Failed to start video processing.';
            progressBox.style.display = 'none';
        }
    } catch (err) {
        alertBox.className = 'alert-box error';
        alertBox.innerText = 'Network error starting video job.';
        progressBox.style.display = 'none';
    }
});

// Poll Video Job Progress
function pollJobStatus(jobId) {
    const progressBar = document.getElementById('video-progress-bar');
    const progressText = document.getElementById('video-progress-text');
    const alertBox = document.getElementById('video-output-alert');
    const resultPanel = document.getElementById('video-result-panel');
    const resultTitle = document.getElementById('video-result-title');
    const downloadBtn = document.getElementById('btn-download-video');
    const videoPlayer = document.getElementById('video-result-player');
    const summaryDiv = document.getElementById('video-attendance-summary');

    const timer = setInterval(async () => {
        try {
            const res = await fetch(`/api/job-status/${jobId}`);
            const data = await res.json();

            if (data.status === 'processing') {
                progressBar.style.width = `${data.progress}%`;
                progressText.innerText = `Processing frame ${data.current_frame}/${data.total_frames} (${data.progress}%)...`;
            } else if (data.status === 'completed') {
                clearInterval(timer);
                progressBar.style.width = '100%';
                progressText.innerText = `Complete! Processed in ${data.total_time}s.`;

                alertBox.className = 'alert-box success';
                alertBox.style.display = 'block';
                alertBox.innerText = `Video processing complete! Saved as '${data.output_file}' (${data.total_time}s).`;

                const videoUrl = data.output_url || (`/output_videos/${encodeURIComponent(data.output_file)}`);

                resultPanel.style.display = 'block';
                resultTitle.innerHTML = `🎬 Output Video File: <code style="color:#34d399;">${escapeHtml(data.output_file)}</code>`;
                downloadBtn.href = videoUrl;
                downloadBtn.setAttribute('download', data.output_file);
                videoPlayer.src = videoUrl;
                videoPlayer.load();

                if (data.attendance && Object.keys(data.attendance).length > 0) {
                    let attRows = '';
                    for (const [name, info] of Object.entries(data.attendance)) {
                        attRows += `<tr><td><strong>${escapeHtml(name)}</strong></td><td><span class="status-dot green"></span>Present</td><td>${info.timestamp}</td><td>${info.video_time}</td><td>Frame #${info.frame}</td></tr>`;
                    }
                    summaryDiv.innerHTML = `
                        <h4 style="margin-top:1rem; margin-bottom:0.5rem; color:#34d399;">📝 Video Attendance Summary</h4>
                        <table class="data-table">
                            <thead><tr><th>Person Name</th><th>Status</th><th>Timestamp</th><th>Video Timestamp</th><th>Frame #</th></tr></thead>
                            <tbody>${attRows}</tbody>
                        </table>
                    `;
                } else {
                    summaryDiv.innerHTML = '<p style="color:var(--text-muted); margin-top:0.8rem;">No registered faces were identified in this video.</p>';
                }

                loadStats();
                loadAttendanceList();
            } else if (data.status === 'error') {
                clearInterval(timer);
                alertBox.className = 'alert-box error';
                alertBox.style.display = 'block';
                alertBox.innerText = `Processing error: ${data.message}`;
            }
        } catch (err) {
            clearInterval(timer);
            console.error('Job polling error:', err);
        }
    }, 1000);
}

// Live Surveillance Camera Feed
let liveActive = false;
let liveStream = null;
let liveInterval = null;
let spokenSet = new Set();

function speakGreeting(text) {
    const voiceCheck = document.getElementById('live-voice-enable');
    if (!voiceCheck || !voiceCheck.checked || !('speechSynthesis' in window)) return;

    if (spokenSet.has(text)) return;
    spokenSet.add(text);
    setTimeout(() => spokenSet.delete(text), 15000);

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}

// Load Real-Time Camera Attendance Logs
async function loadLiveAttendanceLogs() {
    const tbody = document.getElementById('live-attendance-table-body');
    if (!tbody) return;

    try {
        const res = await fetch('/api/attendance');
        const data = await res.json();
        const logs = data.logs || data.latest_logs || [];

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No attendance records logged today yet.</td></tr>';
            return;
        }

        const recentLogs = logs.slice(-15).reverse();

        tbody.innerHTML = recentLogs.map(log => `
            <tr>
                <td><strong>${escapeHtml(log.person_name || log.Name || log.name || 'Unknown')}</strong></td>
                <td><span style="background:rgba(34,197,94,0.15); padding:0.2rem 0.6rem; border-radius:12px; font-size:0.85rem; border:1px solid rgba(34,197,94,0.3); color:#4ade80;">${escapeHtml(log.Status || 'Present')}</span></td>
                <td>${escapeHtml(log.timestamp || log.Timestamp || log.time || 'N/A')}</td>
                <td><span style="background:rgba(37,99,235,0.15); padding:0.2rem 0.6rem; border-radius:12px; font-size:0.85rem; color:#60a5fa;">${escapeHtml(log.source_file || 'Live Camera Feed')}</span></td>
                <td><strong>${log.confidence ? (log.confidence * 100).toFixed(0) + '%' : '100%'}</strong></td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Failed to load real-time camera logs.</td></tr>';
    }
}

async function toggleLiveSurveillance() {
    const btn = document.getElementById('btn-toggle-live');
    const video = document.getElementById('live-webcam-element');
    const imgOutput = document.getElementById('live-annotated-output');
    const canvas = document.getElementById('live-canvas');
    const alertBox = document.getElementById('live-surveillance-alert');

            }

            // Ideal resolution constraints for maximum camera hardware compatibility
            liveStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 } }
            });
            video.srcObject = liveStream;
            video.style.display = 'block'; // Show raw camera feed immediately
            try { await video.play(); } catch(e) {}
            liveActive = true;
            btn.className = 'btn btn-danger';
            btn.innerText = '⏹️ Stop Camera Feed';

            liveInterval = setInterval(async () => {
                if (!liveActive) return;
                if (!video.videoWidth || !video.videoHeight) return;

                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                const frameBase64 = canvas.toDataURL('image/jpeg', 0.7);

                try {
                    const checkSpoof = document.getElementById('live-anti-spoof-enable') ? document.getElementById('live-anti-spoof-enable').checked : true;
                    const res = await fetch('/api/recognize-frame', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image: frameBase64, threshold: 0.50, check_spoof: checkSpoof })
                    });
                    const data = await res.json();
                    if (data.annotated_image) {
                        imgOutput.src = data.annotated_image;
                        imgOutput.style.display = 'block';
                        video.style.display = 'none'; // Switch to AI annotated stream
                    }

                    if (data.marked_names && data.marked_names.length > 0) {
                        if (alertBox) {
                            alertBox.style.display = 'block';
                            alertBox.className = 'alert-box alert-success';
                            alertBox.innerHTML = `✅ <strong>Attendance Marked:</strong> ${data.marked_names.join(', ')} logged at ${new Date().toLocaleTimeString()}`;
                        }
                    } else if (alertBox && alertBox.className.includes('alert-info')) {
                        alertBox.style.display = 'none';
                    }

                    if (data.detections && data.detections.length > 0) {
                        data.detections.forEach(det => {
                            if (det.name.includes("SPOOF")) {
                                speakGreeting("Warning! Anti-spoofing attack detected!");
                            } else if (det.name !== "Unknown") {
                                const cleanName = det.name.split(' ')[0].replace(/[^a-zA-Z]/g, '');
                                speakGreeting(`Welcome back, ${cleanName}! Attendance logged.`);
                            } else {
                                speakGreeting("Security Alert: Unrecognized person detected.");
                            }
                        });
                    }
                } catch (err) {
                    console.error('Live frame recognition error:', err);
                }
            }, 300);

        } catch (err) {
            console.error('Camera access error:', err);
            if (alertBox) {
                alertBox.style.display = 'block';
                alertBox.className = 'alert-box alert-danger';
                let errMsg = err.message;
                if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                    errMsg = 'Camera is locked by another application (Zoom / Skype / Windows Camera App). Please close other camera apps and click "Turn On Camera Feed" again.';
                } else if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    errMsg = 'Camera permission was blocked. Please click the camera icon in your browser address bar and select "Allow".';
                }
                alertBox.innerText = `❌ ${errMsg}`;
            } else {
                alert(`Cannot access camera: ${err.message}`);
            }
        }
    } else {
        liveActive = false;
        clearInterval(liveInterval);
        if (liveStream) liveStream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        video.style.display = 'none';
        imgOutput.src = '';
        imgOutput.style.display = 'none';
        btn.className = 'btn btn-primary';
        btn.innerText = '🔴 Turn On Camera Feed';
        if (alertBox) alertBox.style.display = 'none';
    }
}

// Load Attendance Reports List
async function loadAttendanceList() {
    const select = document.getElementById('select-csv-log');
    if (!select) return;

    try {
        const res = await fetch('/api/attendance');
        const data = await res.json();

        if (data.files && data.files.length > 0) {
            select.innerHTML = data.files.map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('');
            select.value = data.files[0];
            setTimeout(() => loadAttendanceDetails(data.files[0]), 50);
        } else {
            select.innerHTML = '<option value="">No attendance reports found</option>';
            const tbody = document.getElementById('attendance-table-body');
            if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-center">No attendance reports available.</td></tr>';
        }
    } catch (err) {
        console.error('Failed to load attendance list:', err);
    }
}

// Load Attendance Log File Details
async function loadAttendanceDetails(filename) {
    if (!filename) {
        const sel = document.getElementById('select-csv-log');
        filename = sel ? sel.value : '';
    }
    if (!filename) return;

    const tbody = document.getElementById('attendance-table-body');
    const downloadBtn = document.getElementById('btn-download-csv');
    const downloadPdfBtn = document.getElementById('btn-download-pdf');
    const downloadExcelBtn = document.getElementById('btn-download-excel');

    if (downloadBtn) {
        downloadBtn.href = `/api/download-attendance/${encodeURIComponent(filename)}`;
        downloadBtn.style.display = 'inline-flex';
    }
    if (downloadPdfBtn) {
        downloadPdfBtn.href = `/api/generate-pdf/${encodeURIComponent(filename)}`;
        downloadPdfBtn.style.display = 'inline-flex';
    }
    if (downloadExcelBtn) {
        downloadExcelBtn.href = `/api/generate-excel/${encodeURIComponent(filename)}`;
        downloadExcelBtn.style.display = 'inline-flex';
    }

    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Loading attendance records...</td></tr>';
    }

    try {
        const res = await fetch(`/api/attendance-details/${encodeURIComponent(filename)}`);
        const data = await res.json();
        const records = data.records || [];

        if (records.length === 0) {
            if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-center">No attendance records found in report.</td></tr>';
            return;
        }

        const rows = records.map(r => {
            const name = r.person_name || r.Name || r.name || '';
            const status = r.status || r.Status || 'Present';
            const timestamp = r.timestamp || r.Timestamp || r.time || '';
            const video_time = r.video_time || r['Video Time'] || 'N/A';
            const frame = r.frame_number !== undefined ? r.frame_number : (r.Frame !== undefined ? r.Frame : '0');

            return `
                <tr>
                    <td><strong>${escapeHtml(name)}</strong></td>
                    <td><span class="status-dot green" style="display:inline-block; margin-right:4px;"></span>${escapeHtml(status)}</td>
                    <td>${escapeHtml(timestamp)}</td>
                    <td>${escapeHtml(video_time)}</td>
                    <td>${escapeHtml(frame)}</td>
                </tr>
            `;
        }).join('');

        if (tbody) tbody.innerHTML = rows;

    } catch (err) {
        console.error('Error fetching attendance details:', err);
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading attendance report details.</td></tr>';
    }
}

// Utility: Escape HTML strings
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Load Interactive Chart.js Analytics
let trendChart = null;
let deptChart = null;

async function loadAnalyticsCharts() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();

        // 1. Line Chart: Daily Attendance Trends
        const trendCanvas = document.getElementById('chart-attendance-trend');
        if (trendCanvas) {
            const trendCtx = trendCanvas.getContext('2d');
            const hasTrend = data.daily_trends && data.daily_trends.length > 0;
            const labels = hasTrend ? data.daily_trends.map(t => t.date) : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Today'];
            const values = hasTrend ? data.daily_trends.map(t => t.count) : [0, 0, 0, 0, 0, 0, data.peak_metrics ? data.peak_metrics.total_logs : 0];

            if (trendChart) trendChart.destroy();
            trendChart = new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Check-ins / Present Attendees',
                        data: values,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(37, 99, 235, 0.25)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 6,
                        pointHoverRadius: 8,
                        pointBackgroundColor: '#2563eb',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#38bdf8', font: { family: 'Outfit', size: 12, weight: 'bold' } }
                        },
                        tooltip: {
                            backgroundColor: '#0b1120',
                            titleColor: '#38bdf8',
                            bodyColor: '#f8fafc',
                            borderColor: '#2563eb',
                            borderWidth: 1,
                            padding: 10,
                            callbacks: {
                                label: function(context) {
                                    return ` 👤 ${context.parsed.y} Attendee(s) Checked-in`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Date', color: '#38bdf8', font: { size: 11 } },
                            ticks: { color: '#94a3b8', font: { size: 11 } },
                            grid: { color: 'rgba(37, 99, 235, 0.15)' }
                        },
                        y: {
                            title: { display: true, text: 'Attendees Count', color: '#38bdf8', font: { size: 11 } },
                            ticks: { color: '#94a3b8', precision: 0, font: { size: 11 } },
                            grid: { color: 'rgba(37, 99, 235, 0.15)' },
                            beginAtZero: true
                        }
                    }
                }
            });
        }

        // 2. Doughnut Chart: Department Breakdown
        const deptCanvas = document.getElementById('chart-department-breakdown');
        if (deptCanvas) {
            const deptCtx = deptCanvas.getContext('2d');
            const hasDepts = data.department_breakdown && data.department_breakdown.length > 0;
            const deptLabels = hasDepts ? data.department_breakdown.map(d => d.department) : ['AI Engineering', 'General', 'Operations'];
            const deptValues = hasDepts ? data.department_breakdown.map(d => d.count) : [1, 1, 0];

            if (deptChart) deptChart.destroy();
            deptChart = new Chart(deptCtx, {
                type: 'doughnut',
                data: {
                    labels: deptLabels,
                    datasets: [{
                        label: 'Attendees',
                        data: deptValues,
                        backgroundColor: ['#2563eb', '#38bdf8', '#10b981', '#6366f1', '#a855f7'],
                        borderWidth: 2,
                        borderColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#f8fafc', font: { family: 'Outfit', size: 12 } }
                        },
                        tooltip: {
                            backgroundColor: '#0b1120',
                            titleColor: '#38bdf8',
                            bodyColor: '#f8fafc',
                            borderColor: '#38bdf8',
                            borderWidth: 1,
                            padding: 10,
                            callbacks: {
                                label: function(context) {
                                    return ` 🏢 ${context.label}: ${context.parsed} Person(s)`;
                                }
                            }
                        }
                    }
                }
            });
        }

        if (data.peak_metrics) {
            const peakEl = document.getElementById('stat-peak-hour');
            const punctEl = document.getElementById('stat-punctuality');
            if (peakEl) peakEl.innerText = data.peak_metrics.peak_hour || '09:00 AM';
            if (punctEl) punctEl.innerText = (data.peak_metrics.punctuality_pct || 100) + '%';

            // Late Arrivals rendering
            const lateBody = document.getElementById('late-arrivals-body');
            if (lateBody) {
                const lates = data.peak_metrics.late_arrivals || [];
                if (lates.length > 0) {
                    lateBody.innerHTML = lates.map(l => `
                        <tr>
                            <td><strong>${escapeHtml(l.person_name)}</strong></td>
                            <td><span style="color:#ef4444; font-weight:bold;">${escapeHtml(l.arrival_time)}</span></td>
                            <td><span class="status-dot red"></span>Late Arrival</td>
                        </tr>
                    `).join('');
                } else {
                    lateBody.innerHTML = '<tr><td colspan="3" class="text-center">No late arrivals logged today.</td></tr>';
                }
            }

            // Absence Streaks rendering
            const absBody = document.getElementById('absence-streaks-body');
            if (absBody) {
                const streaks = data.peak_metrics.absence_streaks || [];
                if (streaks.length > 0) {
                    absBody.innerHTML = streaks.map(s => `
                        <tr>
                            <td><strong>${escapeHtml(s.person_name)}</strong></td>
                            <td>${escapeHtml(s.department)}</td>
                            <td><span style="color:#f59e0b; font-weight:bold;">${s.days_absent} Days</span></td>
                            <td>${escapeHtml(s.last_seen)}</td>
                        </tr>
                    `).join('');
                } else {
                    absBody.innerHTML = '<tr><td colspan="4" class="text-center">No absence streaks detected.</td></tr>';
                }
            }
        }

    } catch (err) {
        console.error('Failed to load analytics charts:', err);
    }
}

// RTSP CCTV Stream Form Submit
const formRtsp = document.getElementById('form-process-rtsp');
if (formRtsp) {
    formRtsp.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('rtsp-url-input').value.trim();
        const duration = document.getElementById('rtsp-duration').value;
        const alertBox = document.getElementById('rtsp-alert');

        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-info';
        alertBox.innerText = '🎥 Connecting to RTSP / IP CCTV Camera stream... Please wait.';

        const formData = new FormData();
        formData.append('rtsp_url', url);
        formData.append('duration_seconds', duration);

        try {
            const res = await fetch('/api/process-rtsp', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alertBox.className = 'alert-box alert-success';
                alertBox.innerText = `✅ RTSP Stream complete! Tracked ${data.present_persons.length} attendees (${data.present_persons.join(', ') || 'None'}).`;
                loadAttendanceList();
            } else {
                alertBox.className = 'alert-box alert-danger';
                alertBox.innerText = `❌ RTSP Stream Error: ${data.detail || 'Could not connect'}`;
            }
        } catch (err) {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Error connecting to RTSP stream: ${err.message}`;
        }
    });
}



// ---------------------------------------------------------
// OSINT REVERSE SEARCH HANDLER
// ---------------------------------------------------------

// Reverse Image Search Form Submit
const formReverseSearch = document.getElementById('form-reverse-search');
if (formReverseSearch) {
    formReverseSearch.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('search-photo-input');
        const urlInput = document.getElementById('search-url-input').value.trim();
        const alertBox = document.getElementById('search-alert');
        const resultsContainer = document.getElementById('search-results-container');
        const resultsList = document.getElementById('search-results-list');

        if (!fileInput.files[0] && !urlInput) {
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = '⚠️ Please upload a target photo or enter an image URL.';
            return;
        }

        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-info';
        alertBox.innerText = '🔎 Extracting 512-D vector embedding & executing reverse facial match...';

        const formData = new FormData();
        if (fileInput.files[0]) {
            formData.append('file', fileInput.files[0]);
        } else if (urlInput) {
            formData.append('image_url', urlInput);
        }

        try {
            const res = await fetch('/api/reverse-search', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok && data.face_detected) {
                alertBox.className = 'alert-box alert-success';
                alertBox.innerText = `✅ Reverse Facial Search Complete! Found ${data.osint_matches.length} matching profiles out of ${data.total_osint_indexed} indexed profiles.`;

                resultsContainer.style.display = 'block';

                if (data.osint_matches.length === 0 && (!data.internal_match || data.internal_match.name === 'Unknown')) {
                    resultsList.innerHTML = `
                        <div class="card-panel" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3);">
                            <h4 class="text-danger">❌ No Profile Match Found</h4>
                            <p style="color:var(--text-muted); font-size:0.9rem;">This candidate face does not match any indexed profiles or internal database records.</p>
                        </div>
                    `;
                    return;
                }

                let html = '';
                if (data.internal_match && data.internal_match.name !== 'Unknown') {
                    html += `
                        <div class="card-panel" style="background: rgba(251, 191, 36, 0.1); border-color: #fbbf24; margin-bottom: 1rem;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <span class="badge yellow">Internal Database Match</span>
                                    <h3 style="margin-top:0.3rem;">${escapeHtml(data.internal_match.name)}</h3>
                                </div>
                                <div style="text-align:right;">
                                    <span style="font-size:1.4rem; font-weight:700; color:#fbbf24;">${data.internal_match.similarity_score}%</span>
                                    <div style="font-size:0.75rem; color:var(--text-muted);">Cosine Similarity</div>
                                </div>
                            </div>
                        </div>
                    `;
                }

                data.osint_matches.forEach(m => {
                    html += `
                        <div class="card-panel" style="margin-bottom: 1rem; border-color: rgba(245, 158, 11, 0.3);">
                            <div style="display:flex; gap:1rem; align-items:center;">
                                ${m.avatar_url ? `<img src="${escapeHtml(m.avatar_url)}" style="width:64px; height:64px; border-radius:50%; object-fit:cover; border:2px solid #fbbf24;" alt="Avatar">` : '<div style="width:64px; height:64px; border-radius:50%; background:#333; display:flex; align-items:center; justify-content:center; font-size:1.5rem;">👤</div>'}
                                <div style="flex:1;">
                                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                                        <div>
                                            <span class="badge yellow">${escapeHtml(m.platform || 'Social Web')}</span>
                                            <h3 style="margin-top:0.2rem; font-size:1.2rem;">${escapeHtml(m.name)} <span style="font-size:0.9rem; color:var(--text-muted); font-weight:normal;">(@${escapeHtml(m.username)})</span></h3>
                                        </div>
                                        <div style="text-align:right;">
                                            <span style="font-size:1.3rem; font-weight:700; color:#fbbf24;">${m.similarity_score}%</span>
                                            <div style="font-size:0.75rem; color:var(--text-muted);">Vector Match</div>
                                        </div>
                                    </div>
                                    <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.3rem;">${escapeHtml(m.bio)}</p>
                                    <div style="margin-top:0.5rem; display:flex; gap:1rem; align-items:center;">
                                        <span style="font-size:0.8rem; color:var(--text-muted);">📍 ${escapeHtml(m.location)}</span>
                                        ${m.profile_url ? `<a href="${escapeHtml(m.profile_url)}" target="_blank" class="btn btn-secondary" style="font-size:0.8rem; padding:0.2rem 0.6rem;">🔗 View ${escapeHtml(m.platform)} Profile</a>` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });

                resultsList.innerHTML = html;

            } else {
                alertBox.className = 'alert-box alert-danger';
                alertBox.innerText = `❌ ${data.detail || data.message || 'Reverse search failed.'}`;
            }
        } catch (err) {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Error executing reverse search: ${err.message}`;
        }
    });
}

// Load System Security Audit Logs

async function loadAuditLogs() {
    const tbody = document.getElementById('audit-table-body');
    if (!tbody) return;

    try {
        const res = await fetch('/api/audit-logs');
        const data = await res.json();

        if (data.logs && data.logs.length > 0) {
            tbody.innerHTML = data.logs.map(log => `
                <tr>
                    <td><small style="color:var(--text-muted);">${escapeHtml(log.timestamp || '')}</small></td>
                    <td><span class="badge yellow">${escapeHtml(log.action || 'SYSTEM')}</span></td>
                    <td>${escapeHtml(log.details || '')}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No security audit logs recorded yet.</td></tr>';
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Failed to load audit logs.</td></tr>';
    }
}

// Load & Save Telegram Push Alert Settings
async function loadTelegramSettings() {
    try {
        const res = await fetch('/api/telegram/settings');
        const config = await res.json();

        const tokenInput = document.getElementById('telegram-bot-token');
        const chatInput = document.getElementById('telegram-chat-id');
        const enableCheck = document.getElementById('telegram-enable');

        if (tokenInput) tokenInput.value = config.bot_token || '';
        if (chatInput) chatInput.value = config.chat_id || '';
        if (enableCheck) enableCheck.checked = config.enabled || false;
    } catch (err) {
        console.error('Failed to load Telegram settings:', err);
    }
}

async function saveTelegramSettings(e) {
    if (e) e.preventDefault();
    const botToken = document.getElementById('telegram-bot-token').value.trim();
    const chatId = document.getElementById('telegram-chat-id').value.trim();
    const enabled = document.getElementById('telegram-enable').checked;
    const alertBox = document.getElementById('telegram-alert');

    alertBox.style.display = 'block';
    alertBox.className = 'alert-box alert-info';
    alertBox.innerText = '💾 Saving Telegram settings...';

    try {
        const res = await fetch('/api/telegram/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, bot_token: botToken, chat_id: chatId })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alertBox.className = 'alert-box alert-success';
            alertBox.innerText = '✅ Saved Telegram push alert settings successfully!';
        } else {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = '❌ Failed to save Telegram settings.';
        }
    } catch (err) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Error saving Telegram settings: ${err.message}`;
    }
}

// Load & Save Automated Daily Report Dispatcher Settings
async function loadSchedulerSettings() {
    try {
        const res = await fetch('/api/schedule/settings');
        const config = await res.json();

        const timeInput = document.getElementById('schedule-dispatch-time');
        const emailInput = document.getElementById('schedule-recipient-email');
        const enableCheck = document.getElementById('schedule-enable');

        if (timeInput) timeInput.value = config.dispatch_time || '18:00';
        if (emailInput) emailInput.value = config.recipient_email || '';
        if (enableCheck) enableCheck.checked = config.enabled || false;
    } catch (err) {
        console.error('Failed to load scheduler settings:', err);
    }
}

async function triggerManualDispatch() {
    const alertBox = document.getElementById('schedule-alert');
    alertBox.style.display = 'block';
    alertBox.className = 'alert-box alert-info';
    alertBox.innerText = '⚡ Compiling PDF & Excel reports and sending instant email dispatch...';

    try {
        const res = await fetch('/api/schedule/trigger-now', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
            alertBox.className = 'alert-box alert-success';
            alertBox.innerText = `✅ Instant Dispatch Complete! Compiled ${data.pdf} & ${data.excel}.`;
        } else {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = '❌ Failed to execute instant dispatch.';
        }
    } catch (err) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Error executing dispatch: ${err.message}`;
    }
}

const formSchedulerConfig = document.getElementById('form-scheduler-config');
if (formSchedulerConfig) {
    formSchedulerConfig.addEventListener('submit', async (e) => {
        e.preventDefault();
        const dispatchTime = document.getElementById('schedule-dispatch-time').value;
        const recipientEmail = document.getElementById('schedule-recipient-email').value.trim();
        const enabled = document.getElementById('schedule-enable').checked;
        const alertBox = document.getElementById('schedule-alert');

        try {
            const res = await fetch('/api/schedule/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, dispatch_time: dispatchTime, recipient_email: recipientEmail })
            });
            const data = await res.json();
            alertBox.style.display = 'block';
            if (res.ok && data.success) {
                alertBox.className = 'alert-box alert-success';
                alertBox.innerText = '✅ Saved report scheduler settings successfully!';
            } else {
                alertBox.className = 'alert-box alert-danger';
                alertBox.innerText = '❌ Failed to save scheduler settings.';
            }
        } catch (err) {
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Error saving scheduler settings: ${err.message}`;
        }
    });
}

// --- Multi-Angle Consent Self-Enrollment Submit Handler ---
const formMultiEnroll = document.getElementById('form-multi-enroll');
if (formMultiEnroll) {
    formMultiEnroll.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('multi-name').value.trim();
        const dept = document.getElementById('multi-dept').value.trim();
        const role = document.getElementById('multi-role').value.trim();
        const files = document.getElementById('multi-files').files;
        const consent = document.getElementById('multi-consent-check').checked;
        const alertBox = document.getElementById('multi-enroll-alert');

        if (!consent) {
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = '⚠️ Biometric self-enrollment requires explicit consent checkbox confirmation.';
            return;
        }

        if (!files || files.length === 0) {
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = '⚠️ Please select at least 3 to 5 multi-angle selfie photos.';
            return;
        }

        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-info';
        alertBox.innerText = `⌛ Extracting 512-D ArcFace vectors across ${files.length} photo angles for '${name}'...`;

        const formData = new FormData();
        formData.append('name', name);
        formData.append('department', dept || 'General');
        formData.append('role', role || 'Member');
        formData.append('consent', consent ? 'true' : 'false');
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        try {
            const res = await fetch('/api/enroll-multi-angle', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok && data.success) {
                alertBox.className = 'alert-box alert-success';
                alertBox.innerText = `✅ ${data.message}`;
                formMultiEnroll.reset();
                loadPersons();
                loadStats();
            } else {
                alertBox.className = 'alert-box alert-danger';
                alertBox.innerText = `❌ ${data.detail || 'Multi-angle enrollment failed.'}`;
            }
        } catch (err) {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Network error during multi-angle enrollment: ${err.message}`;
        }
    });
}

// --- My Data & Privacy Management ---
async function lookupMyData() {
    const name = document.getElementById('mydata-name-input').value.trim();
    const alertBox = document.getElementById('mydata-alert');
    const resultsBox = document.getElementById('mydata-results');

    if (!name) {
        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = '⚠️ Please enter an enrolled person name to view records.';
        return;
    }

    alertBox.style.display = 'none';
    resultsBox.style.display = 'block';
    resultsBox.innerHTML = '<p class="text-center">🔍 Searching biometric data store...</p>';

    try {
        const res = await fetch(`/api/my-data/${encodeURIComponent(name)}`);
        const data = await res.json();

        if (res.ok && data.success) {
            const p = data.person;
            const historyHtml = data.attendance_history.length > 0
                ? data.attendance_history.slice(0, 10).map(h => `
                    <tr>
                        <td>${escapeHtml(h.timestamp)}</td>
                        <td>${escapeHtml(h.status)}</td>
                        <td>${Math.round((h.confidence || 1.0) * 100)}%</td>
                    </tr>
                `).join('')
                : '<tr><td colspan="3" class="text-center">No attendance logs.</td></tr>';

            resultsBox.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:0.5rem; margin-bottom:0.8rem;">
                    <h4 style="color:var(--accent-gold); margin:0;">👤 Stored Data Record: ${escapeHtml(p.name)}</h4>
                    <span style="background:rgba(16,185,129,0.2); color:#10b981; padding:0.2rem 0.5rem; border-radius:4px; font-size:0.75rem;">Consent Verified</span>
                </div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:0.5rem; margin-bottom:1rem; font-size:0.85rem;">
                    <div><strong>Department:</strong> ${escapeHtml(p.department)}</div>
                    <div><strong>Role:</strong> ${escapeHtml(p.role)}</div>
                    <div><strong>Vectors Stored:</strong> ${p.vector_count} (512-D)</div>
                    <div><strong>Enrolled On:</strong> ${escapeHtml(p.created_at)}</div>
                </div>
                <h5 style="margin-bottom:0.4rem; font-size:0.85rem;">Recent Attendance Check-in Logs (${data.attendance_history.length} Total)</h5>
                <table class="data-table" style="font-size:0.8rem;">
                    <thead>
                        <tr><th>Timestamp</th><th>Status</th><th>Confidence</th></tr>
                    </thead>
                    <tbody>${historyHtml}</tbody>
                </table>
            `;
        } else {
            resultsBox.style.display = 'none';
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ ${data.detail || 'No record found for this name.'}`;
        }
    } catch (err) {
        resultsBox.style.display = 'none';
        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Error retrieving data: ${err.message}`;
    }
}

async function purgeMyData() {
    const name = document.getElementById('mydata-name-input').value.trim();
    const alertBox = document.getElementById('mydata-alert');
    const resultsBox = document.getElementById('mydata-results');

    if (!name) {
        alertBox.style.display = 'block';
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = '⚠️ Please enter an enrolled person name to delete.';
        return;
    }

    if (!confirm(`⚠️ ARE YOU SURE?\nThis action will permanently delete all stored 512-D face vectors, consent records, and attendance logs for '${name}'. This action cannot be undone.`)) {
        return;
    }

    alertBox.style.display = 'block';
    alertBox.className = 'alert-box alert-info';
    alertBox.innerText = `🗑️ Purging stored vectors and records for '${name}'...`;

    try {
        const res = await fetch(`/api/my-data/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const data = await res.json();

        if (res.ok && data.success) {
            alertBox.className = 'alert-box alert-success';
            alertBox.innerText = `✅ ${data.message}`;
            resultsBox.style.display = 'none';
            document.getElementById('mydata-name-input').value = '';
            loadPersons();
            loadStats();
        } else {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ ${data.detail || 'Failed to purge user data.'}`;
        }
    } catch (err) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Error purging user data: ${err.message}`;
    }
}

// --- Load Confidence Alert Review Queue ---
async function loadConfidenceAlerts() {
    const tbody = document.getElementById('confidence-alerts-body');
    if (!tbody) return;

    try {
        const res = await fetch('/api/confidence-alerts');
        const data = await res.json();

        if (data.alerts && data.alerts.length > 0) {
            tbody.innerHTML = data.alerts.map(a => `
                <tr>
                    <td>${escapeHtml(a.timestamp)}</td>
                    <td><strong>${escapeHtml(a.person_name)}</strong></td>
                    <td><span style="color:${a.confidence < 0.45 ? '#ef4444' : '#fbbf24'}; font-weight:bold;">${(a.confidence * 100).toFixed(1)}%</span></td>
                    <td><span class="status-dot yellow"></span>${escapeHtml(a.status)}</td>
                    <td>${escapeHtml(a.details || 'Borderline similarity')}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No borderline alerts flagged.</td></tr>';
        }
    } catch (err) {
        console.error('Failed to load confidence alerts:', err);
    }
}

// Ensure Confidence Alerts load on navigation to dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadConfidenceAlerts();
    loadPostgresSettings();
});

// --- PostgreSQL Settings & Migration Handlers ---
async function loadPostgresSettings() {
    try {
        const res = await fetch('/api/postgres/settings');
        const config = await res.json();

        if (document.getElementById('pg-host')) document.getElementById('pg-host').value = config.host || 'localhost';
        if (document.getElementById('pg-port')) document.getElementById('pg-port').value = config.port || 5432;
        if (document.getElementById('pg-database')) document.getElementById('pg-database').value = config.database || 'visiontrack_db';
        if (document.getElementById('pg-user')) document.getElementById('pg-user').value = config.user || 'postgres';
        if (document.getElementById('pg-password')) document.getElementById('pg-password').value = config.password || '';
        if (document.getElementById('pg-enable')) document.getElementById('pg-enable').checked = config.enabled || false;
    } catch (err) {
        console.error('Failed to load PostgreSQL settings:', err);
    }
}

async function testPostgresConnection() {
    const alertBox = document.getElementById('postgres-alert');
    const host = document.getElementById('pg-host').value.trim();
    const port = document.getElementById('pg-port').value.trim();
    const database = document.getElementById('pg-database').value.trim();
    const user = document.getElementById('pg-user').value.trim();
    const password = document.getElementById('pg-password').value;

    alertBox.style.display = 'block';
    alertBox.className = 'alert-box alert-info';
    alertBox.innerText = '🐘 Testing connection to PostgreSQL server...';

    try {
        const res = await fetch('/api/postgres/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, database, user, password })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alertBox.className = 'alert-box alert-success';
            alertBox.innerText = `✅ ${data.message}`;
        } else {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ ${data.detail || 'Failed to connect to PostgreSQL.'}`;
        }
    } catch (err) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Connection test error: ${err.message}`;
    }
}

async function migrateSQLiteToPostgres() {
    const alertBox = document.getElementById('postgres-alert');
    if (!confirm('⚡ Start migration of all enrolled persons, attendance check-ins, and audit logs from SQLite to PostgreSQL?')) {
        return;
    }

    alertBox.style.display = 'block';
    alertBox.className = 'alert-box alert-info';
    alertBox.innerText = '📦 Initializing PostgreSQL schema & copying SQLite data...';

    try {
        const res = await fetch('/api/postgres/migrate', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
            alertBox.className = 'alert-box alert-success';
            alertBox.innerText = `✅ ${data.message}`;
        } else {
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Migration failed: ${data.detail || 'Unknown error'}`;
        }
    } catch (err) {
        alertBox.className = 'alert-box alert-danger';
        alertBox.innerText = `❌ Error during migration: ${err.message}`;
    }
}

const formPostgresConfig = document.getElementById('form-postgres-config');
if (formPostgresConfig) {
    formPostgresConfig.addEventListener('submit', async (e) => {
        e.preventDefault();
        const alertBox = document.getElementById('postgres-alert');
        const host = document.getElementById('pg-host').value.trim();
        const port = document.getElementById('pg-port').value.trim();
        const database = document.getElementById('pg-database').value.trim();
        const user = document.getElementById('pg-user').value.trim();
        const password = document.getElementById('pg-password').value;
        const enabled = document.getElementById('pg-enable').checked;

        try {
            const res = await fetch('/api/postgres/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled, host, port, database, user, password })
            });
            const data = await res.json();
            alertBox.style.display = 'block';
            if (res.ok && data.success) {
                alertBox.className = 'alert-box alert-success';
                alertBox.innerText = '✅ Saved PostgreSQL settings successfully!';
            } else {
                alertBox.className = 'alert-box alert-danger';
                alertBox.innerText = '❌ Failed to save PostgreSQL settings.';
            }
        } catch (err) {
            alertBox.style.display = 'block';
            alertBox.className = 'alert-box alert-danger';
            alertBox.innerText = `❌ Error saving PostgreSQL settings: ${err.message}`;
        }
    });
}
