// VisionTrack AI Frontend JavaScript Engine

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    checkAuthStatus();
    loadStats();
    loadPersons();
    loadVideosList();
    loadAttendanceList();
});

// Check Admin Authentication Status
let activeToken = localStorage.getItem('admin_token') || '';

async function checkAuthStatus() {
    const modal = document.getElementById('login-modal');
    try {
        const res = await fetch(`/api/auth-status?token=${encodeURIComponent(activeToken)}`);
        const data = await res.json();

        if (data.authenticated) {
            modal.style.display = 'none';
            document.getElementById('session-username').innerText = data.user || 'admin';
        } else {
            modal.style.display = 'flex';
        }
    } catch (err) {
        modal.style.display = 'flex';
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
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const viewPanels = document.querySelectorAll('.view-panel');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetView = btn.getAttribute('data-view');

            navButtons.forEach(b => b.classList.remove('active'));
            viewPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetView).classList.add('active');

            if (targetView === 'view-dashboard') {
                loadStats();
                loadPersons();
            } else if (targetView === 'view-video') {
                loadVideosList();
            } else if (targetView === 'view-attendance') {
                loadAttendanceList();
            }
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

async function toggleLiveSurveillance() {
    const btn = document.getElementById('btn-toggle-live');
    const video = document.getElementById('live-webcam-element');
    const imgOutput = document.getElementById('live-annotated-output');
    const canvas = document.getElementById('live-canvas');

    if (!liveActive) {
        try {
            liveStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video.srcObject = liveStream;
            liveActive = true;
            btn.className = 'btn btn-danger';
            btn.innerText = '⏹️ Stop Camera Feed';

            liveInterval = setInterval(async () => {
                if (!liveActive) return;

                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                const frameBase64 = canvas.toDataURL('image/jpeg', 0.7);

                try {
                    const res = await fetch('/api/recognize-frame', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image: frameBase64, threshold: 0.50 })
                    });
                    const data = await res.json();
                    if (data.annotated_image) {
                        imgOutput.src = data.annotated_image;
                    }
                } catch (err) {
                    console.error('Live frame recognition error:', err);
                }
            }, 300);

        } catch (err) {
            alert('Cannot access camera: ' + err.message);
        }
    } else {
        liveActive = false;
        clearInterval(liveInterval);
        if (liveStream) liveStream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        imgOutput.src = '';
        btn.className = 'btn btn-primary';
        btn.innerText = '🔴 Turn On Camera Feed';
    }
}

// Load Attendance Reports List
async function loadAttendanceList() {
    const select = document.getElementById('select-csv-log');
    try {
        const res = await fetch('/api/attendance');
        const data = await res.json();

        select.innerHTML = '<option value="">-- Select Report --</option>';
        if (data.files && data.files.length > 0) {
            data.files.forEach(f => {
                select.innerHTML += `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`;
            });
            select.value = data.files[0];
            loadAttendanceDetails(data.files[0]);
        } else {
            select.innerHTML = '<option value="">No attendance reports found</option>';
            document.getElementById('attendance-table-body').innerHTML = '<tr><td colspan="5" class="text-center">No attendance reports available.</td></tr>';
        }
    } catch (err) {
        console.error('Failed to load attendance list:', err);
    }
}

// Load Attendance Log File Details
async function loadAttendanceDetails(filename) {
    if (!filename) return;

    const downloadBtn = document.getElementById('btn-download-csv');
    const downloadPdfBtn = document.getElementById('btn-download-pdf');

    downloadBtn.href = `/api/download-attendance/${encodeURIComponent(filename)}`;
    downloadBtn.style.display = 'inline-flex';

    if (downloadPdfBtn) {
        downloadPdfBtn.href = `/api/generate-pdf/${encodeURIComponent(filename)}`;
        downloadPdfBtn.style.display = 'inline-flex';
    }

    try {
        const res = await fetch(`/api/download-attendance/${encodeURIComponent(filename)}`);
        const text = await res.text();

        const lines = text.trim().split('\n');
        if (lines.length <= 1) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">CSV file is empty.</td></tr>';
            return;
        }

        const rows = lines.slice(1).map(line => {
            const cols = line.split(',').map(c => c.replace(/"/g, ''));
            return `
                <tr>
                    <td><strong>${escapeHtml(cols[0] || '')}</strong></td>
                    <td><span class="status-dot yellow" style="display:inline-block; margin-right:4px;"></span>${escapeHtml(cols[1] || 'Present')}</td>
                    <td>${escapeHtml(cols[2] || '')}</td>
                    <td>${escapeHtml(cols[3] || '')}</td>
                    <td>${escapeHtml(cols[4] || '')}</td>
                </tr>
            `;
        }).join('');

        tbody.innerHTML = rows;

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error reading CSV file.</td></tr>';
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
