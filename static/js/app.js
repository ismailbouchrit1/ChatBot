/* ===== Shared App Utilities ===== */

// Sidebar toggle
document.addEventListener('DOMContentLoaded', () => {
    const hamburger = document.getElementById('hamburger');
    const sidebar = document.getElementById('sidebar');
    const sidebarClose = document.getElementById('sidebarClose');

    if (hamburger && sidebar) {
        hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
    if (sidebarClose && sidebar) {
        sidebarClose.addEventListener('click', () => sidebar.classList.remove('open'));
    }

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                await api('/api/auth/logout', { method: 'POST', body: JSON.stringify({}) });
            } catch (e) { /* ignore */ }
            window.location.href = '/';
        });
    }
});

// API helper
async function api(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (method !== 'GET') {
        const csrf = getCookie('csrf_token');
        if (csrf) headers['X-CSRF-Token'] = csrf;
    }
    const res = await fetch(url, { ...options, headers });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erreur serveur');
    return data;
}

// Cookie helper
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
}

// Toast notification
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// Format date
function formatDate(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatTime(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// Severity badge HTML
function severityBadge(severity) {
    const cls = { 'CRITIQUE': 'badge-critique', 'ELEVEE': 'badge-elevee', 'MODEREE': 'badge-moderee' };
    return `<span class="alert-badge ${cls[severity] || ''}">${severity}</span>`;
}

function statusBadge(status) {
    const cls = { 'NOUVELLE': 'badge-nouvelle', 'EN_TRAITEMENT': 'badge-en_traitement', 'RESOLUE': 'badge-resolue' };
    const labels = { 'NOUVELLE': 'Nouvelle', 'EN_TRAITEMENT': 'En traitement', 'RESOLUE': 'Resolue' };
    return `<span class="alert-badge ${cls[status] || ''}">${labels[status] || status}</span>`;
}
