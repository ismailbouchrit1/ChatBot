/* ===== Student Dashboard ===== */
document.addEventListener('DOMContentLoaded', async () => {
    const EMOTION_COLORS = {
        'serein': '#148F77', 'bien': '#2E86C1', 'stresse': '#F39C12',
        'anxieux': '#E67E22', 'triste': '#5DADE2', 'en_colere': '#C0392B',
        'fatigue': '#8E44AD', 'confus': '#7D3C98'
    };
    const EMOTION_VALUES = {
        'serein': 8, 'bien': 7, 'stresse': 4, 'anxieux': 3,
        'triste': 2, 'en_colere': 2, 'fatigue': 3, 'confus': 4
    };

    try {
        const data = await api('/api/dashboard/student');
        document.getElementById('totalMessages').textContent = data.total_messages;
        document.getElementById('sessionsMonth').textContent = data.sessions_this_month;

        // Emotion chart
        const timeline = data.emotions_timeline;
        if (timeline && timeline.length > 0) {
            const ctx = document.getElementById('emotionChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: timeline.map(e => e.date),
                    datasets: [{
                        label: 'Bien-etre',
                        data: timeline.map(e => EMOTION_VALUES[e.emotion] || 5),
                        borderColor: '#2E86C1',
                        backgroundColor: 'rgba(46,134,193,0.1)',
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: timeline.map(e => EMOTION_COLORS[e.emotion] || '#2E86C1'),
                        pointRadius: 6,
                        pointHoverRadius: 8,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const em = timeline[ctx.dataIndex].emotion;
                                    return em ? em.replace('_', ' ') : '';
                                }
                            }
                        }
                    },
                    scales: {
                        y: { min: 0, max: 10, ticks: { display: false }, grid: { color: '#E0E6ED' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        } else {
            document.getElementById('noEmotionData').style.display = 'block';
            document.getElementById('emotionChart').style.display = 'none';
        }

        // Word cloud
        const wordcloudEl = document.getElementById('studentWordcloud');
        const noWordcloud = document.getElementById('noWordcloud');
        if (wordcloudEl && data.themes_wordcloud && data.themes_wordcloud.length > 0) {
            WordCloud(wordcloudEl, {
                list: data.themes_wordcloud,
                gridSize: 8,
                weightFactor: 5,
                color: '#1B4F72',
                backgroundColor: '#FFFFFF',
                rotateRatio: 0.2,
            });
        } else if (noWordcloud) {
            noWordcloud.style.display = 'block';
        }
    } catch (e) {
        showToast('Erreur de chargement du tableau de bord', 'error');
    }

    // Language preference
    const langPref = document.getElementById('langPref');
    if (langPref) {
        langPref.addEventListener('change', async () => {
            try {
                await api('/api/settings', {
                    method: 'PUT',
                    body: JSON.stringify({ language_pref: langPref.value })
                });
                showToast('Langue mise a jour');
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }

    // Delete data
    const deleteBtn = document.getElementById('deleteDataBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            if (!confirm('Etes-vous sur de vouloir supprimer tout votre historique ? Cette action est irreversible.')) return;
            try {
                await api('/api/settings/delete-data', {
                    method: 'POST',
                    body: JSON.stringify({})
                });
                showToast('Donnees supprimees');
                setTimeout(() => location.reload(), 1000);
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }

    // Notifications toggle
    const notifToggle = document.getElementById('notifToggle');
    if (notifToggle) {
        notifToggle.addEventListener('change', async () => {
            try {
                await api('/api/settings', {
                    method: 'PUT',
                    body: JSON.stringify({ notifications_enabled: notifToggle.checked })
                });
                showToast('Preferences mises a jour');
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }

    // Export data
    const exportBtn = document.getElementById('exportDataBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            window.location.href = '/api/settings/export-data';
        });
    }

    // Deactivate account
    const deactivateBtn = document.getElementById('deactivateBtn');
    if (deactivateBtn) {
        deactivateBtn.addEventListener('click', async () => {
            if (!confirm('Desactiver votre compte ? Vous pourrez le reactiver via l'administration.')) return;
            try {
                await api('/api/settings/deactivate', { method: 'POST', body: JSON.stringify({}) });
                window.location.href = '/';
            } catch (e) { showToast('Erreur', 'error'); }
        });
    }
});
