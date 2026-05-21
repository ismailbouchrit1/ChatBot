/* ===== Admin Panel ===== */
document.addEventListener('DOMContentLoaded', async () => {
    let allClasses = [];

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => { c.style.display = 'none'; c.classList.remove('active'); });
            btn.classList.add('active');
            const tab = document.getElementById('tab-' + btn.dataset.tab);
            if (tab) { tab.style.display = 'block'; tab.classList.add('active'); }
            if (btn.dataset.tab === 'alerts') loadAdminAlerts();
            if (btn.dataset.tab === 'reports') loadReports();
            if (btn.dataset.tab === 'settings') loadSettings();
        });
    });

    // Load dashboard stats
    try {
        const data = await api('/api/dashboard/admin');
        document.getElementById('statStudents').textContent = data.total_students;
        document.getElementById('statTeachers').textContent = data.total_teachers;
        document.getElementById('statConversations').textContent = data.total_conversations;
        document.getElementById('statAlerts').textContent = data.pending_alerts;
    } catch (e) { console.error(e); }

    // Load classes for selects
    async function loadClasses() {
        try {
            const data = await api('/api/classes');
            allClasses = data.classes;
            const sel = document.getElementById('userClass');
            sel.innerHTML = '<option value="">Aucune</option>' +
                allClasses.map(c => `<option value="${c.id}">${c.name} (${c.level})</option>`).join('');
        } catch (e) { console.error(e); }
    }
    await loadClasses();

    // Load users
    async function loadUsers(role) {
        try {
            const url = role ? `/api/users?role=${role}` : '/api/users';
            const data = await api(url);
            const tbody = document.getElementById('usersBody');
            tbody.innerHTML = data.users.map(u => `
                <tr>
                    <td>${u.full_name}</td>
                    <td>${u.email}</td>
                    <td><span class="status-badge ${u.role === 'ADMIN' ? 'status-active' : ''}">${u.role}</span></td>
                    <td>${u.class_name || '-'}</td>
                    <td><span class="status-badge ${u.is_active ? 'status-active' : 'status-inactive'}">${u.is_active ? 'Actif' : 'Inactif'}</span></td>
                    <td class="actions-cell">
                        <button onclick="editUser('${u.id}')" title="Modifier"><i data-lucide="pencil" style="width:16px;height:16px"></i></button>
                        <button class="danger" onclick="toggleUser('${u.id}', ${u.is_active})" title="${u.is_active ? 'Desactiver' : 'Activer'}"><i data-lucide="${u.is_active ? 'user-x' : 'user-check'}" style="width:16px;height:16px"></i></button>
                    </td>
                </tr>
            `).join('');
            lucide.createIcons();
        } catch (e) { console.error(e); }
    }
    await loadUsers();

    document.getElementById('userRoleFilter').addEventListener('change', (e) => loadUsers(e.target.value));

    // Store users data for editing
    let usersData = [];
    async function refreshUsers(role) {
        const url = role ? `/api/users?role=${role}` : '/api/users';
        const data = await api(url);
        usersData = data.users;
        await loadUsers(role);
    }

    // Add user modal
    document.getElementById('addUserBtn').addEventListener('click', () => {
        document.getElementById('userModalTitle').textContent = 'Ajouter un utilisateur';
        document.getElementById('userForm').reset();
        document.getElementById('editUserId').value = '';
        document.getElementById('userPassword').placeholder = 'Mot de passe requis';
        document.getElementById('userPassword').required = true;
        document.getElementById('userModal').style.display = 'flex';
        lucide.createIcons();
    });
    document.getElementById('closeUserModal').addEventListener('click', () => {
        document.getElementById('userModal').style.display = 'none';
    });

    // Edit user
    window.editUser = async function(userId) {
        try {
            const data = await api('/api/users');
            const user = data.users.find(u => u.id === userId);
            if (!user) return;
            document.getElementById('userModalTitle').textContent = 'Modifier l\'utilisateur';
            document.getElementById('editUserId').value = user.id;
            document.getElementById('userFullName').value = user.full_name;
            document.getElementById('userEmail').value = user.email;
            document.getElementById('userRole').value = user.role;
            document.getElementById('userClass').value = user.class_id || '';
            document.getElementById('userPassword').placeholder = 'Laisser vide pour ne pas changer';
            document.getElementById('userPassword').required = false;
            document.getElementById('userModal').style.display = 'flex';
            lucide.createIcons();
        } catch (e) { showToast('Erreur', 'error'); }
    };

    // Toggle user active status
    window.toggleUser = async function(userId, isActive) {
        if (!confirm(isActive ? 'Desactiver cet utilisateur ?' : 'Reactiver cet utilisateur ?')) return;
        try {
            if (isActive) {
                await api(`/api/users/${userId}`, { method: 'DELETE' });
            } else {
                await api(`/api/users/${userId}`, {
                    method: 'PUT', body: JSON.stringify({ is_active: true })
                });
            }
            showToast('Utilisateur mis a jour');
            loadUsers(document.getElementById('userRoleFilter').value);
        } catch (e) { showToast('Erreur', 'error'); }
    };

    // Save user form
    document.getElementById('userForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const editId = document.getElementById('editUserId').value;
        const payload = {
            full_name: document.getElementById('userFullName').value,
            email: document.getElementById('userEmail').value,
            role: document.getElementById('userRole').value,
            class_id: document.getElementById('userClass').value || null,
        };
        const pw = document.getElementById('userPassword').value;
        if (pw) payload.password = pw;

        try {
            if (editId) {
                await api(`/api/users/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
            } else {
                if (!pw) { showToast('Mot de passe requis', 'error'); return; }
                payload.password = pw;
                await api('/api/users', { method: 'POST', body: JSON.stringify(payload) });
            }
            showToast('Utilisateur enregistre');
            document.getElementById('userModal').style.display = 'none';
            loadUsers(document.getElementById('userRoleFilter').value);
        } catch (e) { showToast(e.message, 'error'); }
    });

    // Classes tab
    async function loadClassesTable() {
        try {
            const data = await api('/api/dashboard/admin');
            const tbody = document.getElementById('classesBody');
            tbody.innerHTML = data.classes.map(c => `
                <tr><td>${c.name}</td><td>${c.level}</td><td>${c.student_count}</td></tr>
            `).join('');
        } catch (e) { console.error(e); }
    }
    loadClassesTable();

    document.getElementById('addClassBtn').addEventListener('click', () => {
        document.getElementById('classModal').style.display = 'flex';
        lucide.createIcons();
    });

    document.getElementById('classForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            await api('/api/classes', {
                method: 'POST',
                body: JSON.stringify({
                    name: document.getElementById('className').value,
                    level: document.getElementById('classLevel').value,
                })
            });
            showToast('Classe creee');
            document.getElementById('classModal').style.display = 'none';
            document.getElementById('classForm').reset();
            loadClassesTable();
            loadClasses();
        } catch (e) { showToast(e.message, 'error'); }
    });

    // Admin alerts tab
    async function loadAdminAlerts() {
        try {
            const data = await api('/api/alerts');
            const list = document.getElementById('adminAlertsList');
            if (data.alerts.length === 0) {
                list.innerHTML = '<p class="empty-state">Aucune alerte.</p>';
                return;
            }
            list.innerHTML = data.alerts.map(a => `
                <div class="alert-item">
                    ${severityBadge(a.severity)}
                    <div class="alert-info">
                        <strong>${a.student_name || 'Eleve'}</strong>
                        <p>${a.alert_excerpt}</p>
                        <small>${formatDate(a.detected_at)}</small>
                    </div>
                    <div class="alert-status">${statusBadge(a.status)}</div>
                </div>
            `).join('');
        } catch (e) { console.error(e); }
        lucide.createIcons();
    }

    // Reports tab
    async function loadReports() {
        try {
            const stats = await api('/api/alerts/stats');
            const ctx = document.getElementById('alertSeverityChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Critique', 'Elevee', 'Moderee'],
                    datasets: [{
                        label: 'Nombre d\'alertes',
                        data: [stats.by_severity.CRITIQUE, stats.by_severity.ELEVEE, stats.by_severity.MODEREE],
                        backgroundColor: ['#C0392B', '#E67E22', '#F39C12'],
                        borderRadius: 6,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                }
            });

            const adminData = await api('/api/dashboard/admin');
            const classReport = document.getElementById('classReport');
            classReport.innerHTML = adminData.classes.map(c =>
                `<div class="setting-row"><span class="setting-label">${c.name} (${c.level})</span><span>${c.student_count} eleves</span></div>`
            ).join('');
        } catch (e) { console.error(e); }
        lucide.createIcons();
    }

    // Settings tab
    async function loadSettings() {
        try {
            const data = await api('/api/admin/settings');
            const s = data.settings || {};
            document.getElementById('alertRecipientDefault').value = s.alert_recipient_default || '';
            document.getElementById('alertRecipientCritique').value = s.alert_recipient_critique || '';
            document.getElementById('alertRecipientElevee').value = s.alert_recipient_elevee || '';
            document.getElementById('alertRecipientModeree').value = s.alert_recipient_moderee || '';
            document.getElementById('dataRetentionDays').value = s.data_retention_days || 0;
        } catch (e) { console.error(e); }
    }

    const settingsForm = document.getElementById('settingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                await api('/api/admin/settings', {
                    method: 'PUT',
                    body: JSON.stringify({
                        alert_recipient_default: document.getElementById('alertRecipientDefault').value,
                        alert_recipient_critique: document.getElementById('alertRecipientCritique').value,
                        alert_recipient_elevee: document.getElementById('alertRecipientElevee').value,
                        alert_recipient_moderee: document.getElementById('alertRecipientModeree').value,
                        data_retention_days: Number(document.getElementById('dataRetentionDays').value || 0),
                    })
                });
                showToast('Parametres enregistres');
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }

    const cleanupBtn = document.getElementById('runCleanupBtn');
    if (cleanupBtn) {
        cleanupBtn.addEventListener('click', async () => {
            if (!confirm('Nettoyer les anciennes donnees maintenant ?')) return;
            try {
                const data = await api('/api/admin/cleanup', { method: 'POST', body: JSON.stringify({}) });
                const result = data.result || {};
                showToast(`Nettoyage termine: ${result.deleted_conversations || 0} conversations supprimees`);
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }
});
