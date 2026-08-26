// Global App State
const state = {
    selectedTags: [],
    sentimentFilter: 'all',
    tagsData: [],
    dashboardData: null,
    trendData: [],
    articles: [],
    contagionAlerts: [],
    donutChartInstance: null,
    trendChartInstance: null,
};

// Mode display mappings
const MODE_MAP = {
    good: { emoji: '😊', label: 'GOOD', color: '#10B981', desc: 'Positive sentiment dominating coverage' },
    bad: { emoji: '😞', label: 'BAD', color: '#EF4444', desc: 'Negative sentiment and concerns prevailing' },
    ugly: { emoji: '💀', label: 'UGLY', color: '#7C3AED', desc: 'Critical scandal, violence, or high-risk news detected' },
    neutral: { emoji: '😐', label: 'NEUTRAL', color: '#6B7280', desc: 'Balanced or informative news coverage' },
};

// API Fetch Helpers
async function apiGet(endpoint) {
    try {
        const resp = await fetch(endpoint);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API Get Error [${endpoint}]:`, err);
        return null;
    }
}

async function apiPost(endpoint) {
    try {
        const resp = await fetch(endpoint, { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API Post Error [${endpoint}]:`, err);
        return null;
    }
}

// Helper to construct query string
function getTagsQueryParam() {
    if (state.selectedTags.length === 0) return '';
    return `tags=${encodeURIComponent(state.selectedTags.join(','))}`;
}

// 1. Fetch All Tags with Mode Badges
async function loadTags() {
    const data = await apiGet('/api/tags');
    if (data) {
        state.tagsData = data;
        renderTagsGrid();
    }
}

// 2. Fetch Dashboard Mode Data
async function loadDashboard() {
    const query = getTagsQueryParam();
    const url = query ? `/api/dashboard?${query}` : '/api/dashboard';
    const data = await apiGet(url);
    if (data) {
        state.dashboardData = data;
        renderDashboardView();
    }
}

// 3. Fetch Trends Data
async function loadTrends() {
    const query = getTagsQueryParam();
    const url = query ? `/api/trends?${query}&hours=24` : '/api/trends?hours=24';
    const data = await apiGet(url);
    if (data) {
        state.trendData = data;
        renderTrendChart();
    }
}

// 4. Fetch Articles
async function loadArticles() {
    const queryParts = [];
    const tagsQ = getTagsQueryParam();
    if (tagsQ) queryParts.push(tagsQ);
    if (state.sentimentFilter && state.sentimentFilter !== 'all') {
        queryParts.push(`sentiment=${state.sentimentFilter}`);
    }
    queryParts.push('limit=50');

    const url = `/api/articles?${queryParts.join('&')}`;
    const data = await apiGet(url);
    if (data) {
        state.articles = data;
        renderArticleFeed();
    }
}

// 5. Fetch Contagion Alerts
async function loadContagionAlerts() {
    const data = await apiGet('/api/contagion');
    if (data) {
        state.contagionAlerts = data;
        renderContagionBanner();
    }
}

// Master Refresh Function
async function refreshAllData() {
    await Promise.all([
        loadTags(),
        loadDashboard(),
        loadTrends(),
        loadArticles(),
        loadContagionAlerts(),
    ]);
    document.getElementById('last-updated-time').textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

// --- RENDER FUNCTIONS ---

// Render Domain Tags Grid (Multi-Select)
function renderTagsGrid() {
    const grid = document.getElementById('tags-grid');
    grid.innerHTML = '';

    state.tagsData.forEach(t => {
        const isSelected = state.selectedTags.includes(t.tag);
        const modeInfo = MODE_MAP[t.dominant_mode] || MODE_MAP.neutral;

        const pill = document.createElement('div');
        pill.className = `tag-pill ${isSelected ? 'active' : ''}`;
        pill.style.borderColor = isSelected ? '#6366F1' : 'rgba(255, 255, 255, 0.1)';

        pill.innerHTML = `
            <div class="tag-pill-top">
                <span class="tag-pill-title">
                    <span>${t.icon}</span>
                    <span>${t.label}</span>
                </span>
                <span class="tag-pill-mode" style="background: ${modeInfo.color}22; color: ${modeInfo.color}">
                    ${modeInfo.emoji} ${t.dominant_mode}
                </span>
            </div>
            <div class="tag-pill-bottom">
                ${t.article_count} articles
            </div>
        `;

        pill.addEventListener('click', () => toggleTagSelection(t.tag));
        grid.appendChild(pill);
    });

    renderActiveTagsBar();
}

// Toggle Tag Selection
function toggleTagSelection(tag) {
    const idx = state.selectedTags.indexOf(tag);
    if (idx >= 0) {
        state.selectedTags.splice(idx, 1);
    } else {
        state.selectedTags.push(tag);
    }
    refreshAllData();
}

// Render Active Tags Bar
function renderActiveTagsBar() {
    const bar = document.getElementById('active-tags-bar');
    const container = document.getElementById('selected-pills-container');
    const statusText = document.getElementById('tag-bar-status');

    if (state.selectedTags.length === 0) {
        bar.classList.add('hidden');
        statusText.textContent = 'Showing All Articles';
        document.getElementById('intersection-badge').classList.add('hidden');
        document.getElementById('panel-view-title').textContent = 'Overall Sentiment Breakdown (All News)';
    } else {
        bar.classList.remove('hidden');
        statusText.textContent = `Filtered by Intersection (${state.selectedTags.length} tags)`;
        document.getElementById('intersection-badge').classList.remove('hidden');
        document.getElementById('panel-view-title').textContent = `Intersection Subset Breakdown (${state.selectedTags.join(' ∩ ')})`;

        container.innerHTML = '';
        state.selectedTags.forEach(tag => {
            const tagObj = state.tagsData.find(t => t.tag === tag);
            const label = tagObj ? `${tagObj.icon} ${tagObj.label}` : tag;

            const chip = document.createElement('span');
            chip.className = 'tag-chip';
            chip.innerHTML = `
                <span>${label}</span>
                <span class="tag-chip-remove" data-tag="${tag}">✕</span>
            `;
            chip.querySelector('.tag-chip-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                toggleTagSelection(tag);
            });
            container.appendChild(chip);
        });
    }
}

// Render Dashboard View & Hero
function renderDashboardView() {
    const data = state.dashboardData;
    if (!data) return;

    // Overall Hero Banner
    const modeInfo = MODE_MAP[data.dominant_mode] || MODE_MAP.neutral;
    document.getElementById('overall-mode-emoji').textContent = modeInfo.emoji;
    document.getElementById('overall-mode-title').textContent = modeInfo.label;
    document.getElementById('overall-mode-title').style.color = modeInfo.color;
    document.getElementById('overall-mode-desc').textContent = modeInfo.desc;
    document.getElementById('overall-compound-score').textContent = data.avg_compound > 0 ? `+${data.avg_compound}` : data.avg_compound;
    document.getElementById('overall-total-count').textContent = data.total_articles;

    const uglyPct = data.total_articles > 0 ? Math.round((data.ugly_count / data.total_articles) * 100) : 0;
    document.getElementById('overall-ugly-index').textContent = `${uglyPct}%`;

    // 4 Mode Cards
    const total = data.total_articles || 1;
    updateModeCard('good', data.good_count, Math.round((data.good_count / total) * 100));
    updateModeCard('bad', data.bad_count, Math.round((data.bad_count / total) * 100));
    updateModeCard('ugly', data.ugly_count, Math.round((data.ugly_count / total) * 100));
    updateModeCard('neutral', data.neutral_count, Math.round((data.neutral_count / total) * 100));

    // Ugly Pulse trigger
    const uglyCard = document.querySelector('.mode-ugly');
    if (data.ugly_count > 0) {
        uglyCard.classList.add('has-ugly');
    } else {
        uglyCard.classList.remove('has-ugly');
    }

    renderDonutChart();
}

function updateModeCard(mode, count, pct) {
    document.getElementById(`count-${mode}`).textContent = count;
    document.getElementById(`pct-${mode}`).textContent = `${pct}%`;
    document.getElementById(`bar-${mode}`).style.width = `${pct}%`;
}

// Render Donut Chart (Chart.js)
function renderDonutChart() {
    const data = state.dashboardData;
    if (!data) return;

    const ctx = document.getElementById('donutChart').getContext('2d');
    if (state.donutChartInstance) {
        state.donutChartInstance.destroy();
    }

    state.donutChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Good', 'Bad', 'Ugly', 'Neutral'],
            datasets: [{
                data: [data.good_count, data.bad_count, data.ugly_count, data.neutral_count],
                backgroundColor: ['#10B981', '#EF4444', '#7C3AED', '#6B7280'],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94A3B8', font: { family: 'Inter', size: 12 } }
                }
            },
            cutout: '70%',
        }
    });
}

// Render 24h Trend Chart (Chart.js)
function renderTrendChart() {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (state.trendChartInstance) {
        state.trendChartInstance.destroy();
    }

    const labels = state.trendData.map(p => {
        const d = new Date(p.snapshot_time);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    const compounds = state.trendData.map(p => p.avg_compound);

    state.trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Compound Score',
                data: compounds,
                borderColor: '#6366F1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#818CF8',
                pointRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { color: '#64748B' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                y: { min: -1.0, max: 1.0, ticks: { color: '#64748B' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// Render Article Feed
function renderArticleFeed() {
    const list = document.getElementById('article-feed-list');
    const badge = document.getElementById('article-count-badge');
    list.innerHTML = '';

    badge.textContent = `${state.articles.length} Articles`;

    if (state.articles.length === 0) {
        list.innerHTML = '<div class="text-muted" style="padding: 20px; text-align: center;">No articles found matching criteria.</div>';
        return;
    }

    state.articles.forEach(art => {
        const card = document.createElement('div');
        card.className = 'article-card';

        const imgUrl = art.image_url || 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=400&q=80';
        const labelClass = `badge-${art.sentiment_label}`;
        const modeInfo = MODE_MAP[art.sentiment_label] || MODE_MAP.neutral;

        const tagChipsHtml = (art.tags || []).map(t => `<span class="article-tag-chip">🏷️ ${t}</span>`).join('');

        card.innerHTML = `
            <img src="${imgUrl}" alt="article thumb" class="article-thumb" onerror="this.src='https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=400&q=80'">
            <div class="article-main">
                <div class="article-meta">
                    <span class="article-label-badge ${labelClass}">${modeInfo.emoji} ${art.sentiment_label}</span>
                    <span>•</span>
                    <span>${art.source_name || 'News'}</span>
                    <span>•</span>
                    <span>${new Date(art.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                <a href="${art.url}" target="_blank" rel="noopener noreferrer" class="article-title">${art.title}</a>
                <p class="article-desc">${art.description || ''}</p>
                <div class="article-tags-row">
                    ${tagChipsHtml}
                </div>
            </div>
        `;
        list.appendChild(card);
    });
}

// Render Contagion Alert Banner
function renderContagionBanner() {
    const container = document.getElementById('contagion-banner-container');
    container.innerHTML = '';

    if (state.contagionAlerts.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    state.contagionAlerts.forEach(alert => {
        const card = document.createElement('div');
        card.className = 'contagion-card';
        card.innerHTML = `
            <div class="contagion-content">
                <span class="contagion-icon">🚨</span>
                <div class="contagion-text">
                    <strong>Cross-Domain Contagion Warning:</strong> ${alert.message}
                </div>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="this.parentElement.remove()">Dismiss</button>
        `;
        container.appendChild(card);
    });
}

// --- EVENT LISTENERS ---

// Setup Sentiment Tab Filtering
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.sentimentFilter = btn.getAttribute('data-sentiment');
        loadArticles();
    });
});

// Clear Tags Button
document.getElementById('clear-tags-btn').addEventListener('click', () => {
    state.selectedTags = [];
    refreshAllData();
});

// Fetch Now Button
document.getElementById('fetch-now-btn').addEventListener('click', async () => {
    const btn = document.getElementById('fetch-now-btn');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = 'Fetching...';

    await apiPost('/api/fetch-now');
    await refreshAllData();

    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Fetch Now';
});

// Initialize SPA
window.addEventListener('DOMContentLoaded', () => {
    refreshAllData();
    // 60-second auto-refresh
    setInterval(refreshAllData, 60000);
});
