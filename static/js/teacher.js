/* ===== Teacher Dashboard ===== */
document.addEventListener('DOMContentLoaded', async () => {
    const alertFilter = document.getElementById('alertFilter');
    const alertsList = document.getElementById('alertsList');
    const alertModal = document.getElementById('alertModal');
    const alertModalBody = document.getElementById('alertModalBody');
    const closeAlertModal = document.getElementById('closeAlertModal');

    // Load dashboard stats
    try {
        const data = await api('/api/dashboard/teacher');
        document.getElementById('totalStudents').textContent = data.total_students;
        document.getElementById('activeStudents').textContent = data.active_this_week;
        document.getElementById('pendingAlerts').textContent = data.pending_alerts;

        // Wellbeing gauge
        const classScore = data.class_wellbeing_score || 0;
        const fill = document.getElementById('classWellbeingFill');
        const value = document.getElementById('classWellbeingValue');
        if (fill && value) {
            const pct = Math.min(100, Math.max(0, classScore * 10));
            fill.style.width = `${pct}%`;
            value.textContent = `${classScore}/10`;
            fill.classList.remove('ok', 'watch', 'alert');
            fill.classList.add(classScore >= 6 ? 'ok' : classScore >= 4 ? 'watch' : 'alert');
        }

        // Per-student wellbeing list
        const listEl = document.getElementById('studentWellbeingList');
        if (listEl && data.student_wellbeing) {
            listEl.innerHTML = data.student_wellbeing.map(s => `
                <div class="wellbeing-item">
                    <span class="wellbeing-name">${s.name}</span>
                    <span class="wellbeing-score ${s.status}">${s.score}/10</span>
                </div>
            `).join('');
        }

        // Emotion distribution chart
        const emotions = data.emotion_distribution;
        if (Object.keys(emotions).length > 0) {
            const COLORS = {
                'serein': '#148F77', 'bien': '#2E86C1', 'stresse': '#F39C12',
                'anxieux': '#E67E22', 'triste': '#5DADE2', 'en_colere': '#C0392B',
                'fatigue': '#8E44AD', 'confus': '#7D3C98'
            };
            const ctx = document.getElementById('emotionDistChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(emotions).map(e => e.replace('_', ' ')),
                    datasets: [{
                        data: Object.values(emotions),
                        backgroundColor: Object.keys(emotions).map(e => COLORS[e] || '#999'),
                        borderWidth: 2,
                        borderColor: '#fff',
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        }

        // Word cloud
        const cloudEl = document.getElementById('teacherWordcloud');
        const noCloud = document.getElementById('noTeacherWordcloud');
        if (cloudEl && data.themes_wordcloud && data.themes_wordcloud.length > 0) {
            WordCloud(cloudEl, {
                list: data.themes_wordcloud,
                gridSize: 8,
                weightFactor: 5,
                color: '#1B4F72',
                backgroundColor: '#FFFFFF',
                rotateRatio: 0.2,
            });
        } else if (noCloud) {
            noCloud.style.display = 'block';
        }
    } catch (e) { console.error(e); }

    // Load alerts
    async function loadAlerts(status) {
        try {
            const url = status ? `/api/alerts?status=${status}` : '/api/alerts';
            const data = await api(url);
            if (data.alerts.length === 0) {
                alertsList.innerHTML = '<p class="empty-state">Aucune alerte pour le moment.</p>';
                return;
            }
            alertsList.innerHTML = data.alerts.map(a => `
                <div class="alert-item" data-id="${a.id}">
                    ${severityBadge(a.severity)}
                    <div class="alert-info">
                        <strong>${a.student_name || 'Eleve'}</strong>
                        <p>${a.alert_excerpt}</p>
                        <small>${formatDate(a.detected_at)}${a.student_class ? ' - ' + a.student_class : ''}</small>
                    </div>
                    <div class="alert-status">${statusBadge(a.status)}</div>
                </div>
            `).join('');

            // Click to open detail
            alertsList.querySelectorAll('.alert-item').forEach(el => {
                el.addEventListener('click', () => {
                    const alert = data.alerts.find(a => a.id === el.dataset.id);
                    if (alert) showAlertDetail(alert);
                });
            });
        } catch (e) {
            alertsList.innerHTML = '<p class="empty-state">Erreur de chargement.</p>';
        }
        lucide.createIcons();
    }

    function showAlertDetail(alert) {
        alertModalBody.innerHTML = `
            <div class="alert-detail-grid">
                <div class="alert-detail-row">
                    <span class="alert-detail-label">Eleve</span>
                    <span class="alert-detail-value">${alert.student_name}</span>
                </div>
                <div class="alert-detail-row">
                    <span class="alert-detail-label">Classe</span>
                    <span class="alert-detail-value">${alert.student_class || 'N/A'}</span>
                </div>
                <div class="alert-detail-row">
                    <span class="alert-detail-label">Gravite</span>
                    <span class="alert-detail-value">${severityBadge(alert.severity)}</span>
                </div>
                <div class="alert-detail-row">
                    <span class="alert-detail-label">Date</span>
                    <span class="alert-detail-value">${formatDate(alert.detected_at)}</span>
                </div>
                <div class="alert-detail-row">
                    <span class="alert-detail-label">Statut</span>
                    <span class="alert-detail-value">${statusBadge(alert.status)}</span>
                </div>
            </div>
            <div class="alert-detail-excerpt">${alert.alert_excerpt}</div>
            <div class="alert-resolution">
                <label><strong>Note de suivi</strong></label>
                <textarea class="form-input" id="resolutionNote" placeholder="Ajouter une note...">${alert.resolution_note || ''}</textarea>
                <div class="form-actions" style="margin-top:12px;">
                    ${alert.status !== 'EN_TRAITEMENT' ? `<button class="btn btn-outline btn-sm" onclick="updateAlert('${alert.id}','EN_TRAITEMENT')">Prendre en charge</button>` : ''}
                    ${alert.status !== 'RESOLUE' ? `<button class="btn btn-primary btn-sm" onclick="updateAlert('${alert.id}','RESOLUE')">Marquer resolue</button>` : ''}
                </div>
            </div>
        `;
        alertModal.style.display = 'flex';
        lucide.createIcons();
    }

    window.updateAlert = async function(alertId, status) {
        const note = document.getElementById('resolutionNote')?.value || '';
        try {
            await api(`/api/alerts/${alertId}`, {
                method: 'PUT',
                body: JSON.stringify({ status, resolution_note: note })
            });
            showToast('Alerte mise a jour');
            alertModal.style.display = 'none';
            loadAlerts(alertFilter.value);
        } catch (e) { showToast('Erreur', 'error'); }
    };

    closeAlertModal.addEventListener('click', () => alertModal.style.display = 'none');
    alertFilter.addEventListener('change', () => loadAlerts(alertFilter.value));

    loadAlerts();
});
