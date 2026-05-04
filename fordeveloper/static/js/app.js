// ─── Clock ───────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById('clock');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}
updateClock();
setInterval(updateClock, 30000);

// ─── Toast ──────────────────────────────────────────────
let toastEl = null;
function showToast(message) {
    if (!toastEl) {
        toastEl = document.createElement('div');
        toastEl.className = 'toast';
        document.body.appendChild(toastEl);
    }
    toastEl.textContent = message;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2500);
}

// ─── Modal ──────────────────────────────────────────────
function openModal(id) {
    document.getElementById(id).classList.add('open');
}
function closeModal(id) {
    document.getElementById(id).classList.remove('open');
}

// Close modal on backdrop click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('open');
    }
});

// Close modal on Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
    }
});

// ─── API Helpers ────────────────────────────────────────
async function apiPost(url, data) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return res.json();
}

async function apiPut(url, data) {
    const res = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return res.json();
}

async function apiDelete(url) {
    const res = await fetch(url, { method: 'DELETE' });
    return res.json();
}

// ─── Dashboard Quick Actions ────────────────────────────
function openQuickReminder() {
    // Set default datetime to now + 1 hour
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    const dt = now.toISOString().slice(0, 16);
    document.getElementById('qr_remind_at').value = dt;
    openModal('quickReminderModal');
}

async function saveQuickReminder(e) {
    e.preventDefault();
    await apiPost('/api/reminders', {
        note: document.getElementById('qr_note').value,
        remind_at: document.getElementById('qr_remind_at').value,
        category: document.getElementById('qr_category').value,
        recurrence: document.getElementById('qr_recurrence').value,
    });
    closeModal('quickReminderModal');
    showToast('Hatirlatma eklendi');
    setTimeout(() => location.reload(), 500);
}

function openQuickTask() {
    openModal('quickTaskModal');
}

async function saveQuickTask(e) {
    e.preventDefault();
    await apiPost('/api/tasks', {
        title: document.getElementById('qt_title').value,
        tco_number: document.getElementById('qt_tco').value,
        priority: document.getElementById('qt_priority').value,
        category: document.getElementById('qt_category').value,
        jira_url: document.getElementById('qt_jira').value,
    });
    closeModal('quickTaskModal');
    showToast('Task eklendi');
    setTimeout(() => location.reload(), 500);
}

// ─── Task Modal (Tasks page) ────────────────────────────
function openTaskModal() {
    document.getElementById('taskModalTitle').textContent = 'Yeni Task';
    document.getElementById('tm_id').value = '';
    document.getElementById('tm_title').value = '';
    document.getElementById('tm_description').value = '';
    document.getElementById('tm_tco_number').value = '';
    document.getElementById('tm_status').value = 'TODO';
    document.getElementById('tm_priority').value = 'medium';
    document.getElementById('tm_category').value = 'backend';
    document.getElementById('tm_jira_url').value = '';
    document.getElementById('tm_mr_url').value = '';
    document.getElementById('tm_deployment_date').value = '';
    openModal('taskModal');
}

function editTask(id, data) {
    document.getElementById('taskModalTitle').textContent = 'Task Duzenle';
    document.getElementById('tm_id').value = id;
    document.getElementById('tm_title').value = data.title || '';
    document.getElementById('tm_description').value = data.description || '';
    document.getElementById('tm_tco_number').value = data.tco_number || '';
    document.getElementById('tm_status').value = data.status || 'TODO';
    document.getElementById('tm_priority').value = data.priority || 'medium';
    document.getElementById('tm_category').value = data.category || 'backend';
    document.getElementById('tm_jira_url').value = data.jira_url || '';
    document.getElementById('tm_mr_url').value = data.mr_url || '';
    document.getElementById('tm_deployment_date').value = data.deployment_date || '';
    openModal('taskModal');
}

async function saveTask(e) {
    e.preventDefault();
    const id = document.getElementById('tm_id').value;
    const data = {
        title: document.getElementById('tm_title').value,
        description: document.getElementById('tm_description').value,
        tco_number: document.getElementById('tm_tco_number').value,
        status: document.getElementById('tm_status').value,
        priority: document.getElementById('tm_priority').value,
        category: document.getElementById('tm_category').value,
        jira_url: document.getElementById('tm_jira_url').value,
        mr_url: document.getElementById('tm_mr_url').value,
        deployment_date: document.getElementById('tm_deployment_date').value || null,
    };

    if (id) {
        await apiPut('/api/tasks/' + id, data);
        showToast('Task guncellendi');
    } else {
        await apiPost('/api/tasks', data);
        showToast('Task oluşturuldu');
    }
    closeModal('taskModal');
    setTimeout(() => location.reload(), 500);
}

async function deleteTask(id) {
    if (!confirm('Bu task silinsin mi?')) return;
    await apiDelete('/api/tasks/' + id);
    showToast('Task silindi');
    setTimeout(() => location.reload(), 500);
}

// ─── Reminder Functions (Reminders page) ────────────────
function openReminderModal() {
    document.getElementById('reminderModalTitle').textContent = 'Yeni Hatirlatma';
    document.getElementById('rm_id').value = '';
    document.getElementById('rm_note').value = '';
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    document.getElementById('rm_remind_at').value = now.toISOString().slice(0, 16);
    document.getElementById('rm_category').value = 'genel';
    document.getElementById('rm_recurrence').value = 'once';
    document.getElementById('rm_priority').value = 'medium';
    document.getElementById('rm_related_task_id').value = '';
    openModal('reminderModal');
}

function editReminder(data) {
    document.getElementById('reminderModalTitle').textContent = 'Hatirlatma Duzenle';
    document.getElementById('rm_id').value = data.id;
    document.getElementById('rm_note').value = data.note || '';
    document.getElementById('rm_remind_at').value = (data.remind_at || '').slice(0, 16);
    document.getElementById('rm_category').value = data.category || 'genel';
    document.getElementById('rm_recurrence').value = data.recurrence || 'once';
    document.getElementById('rm_priority').value = data.priority || 'medium';
    document.getElementById('rm_related_task_id').value = data.related_task_id || '';
    openModal('reminderModal');
}

async function saveReminder(e) {
    e.preventDefault();
    const id = document.getElementById('rm_id').value;
    const data = {
        note: document.getElementById('rm_note').value,
        remind_at: document.getElementById('rm_remind_at').value,
        category: document.getElementById('rm_category').value,
        recurrence: document.getElementById('rm_recurrence').value,
        priority: document.getElementById('rm_priority').value,
        related_task_id: document.getElementById('rm_related_task_id').value || null,
    };

    if (id) {
        await apiPut('/api/reminders/' + id, data);
        showToast('Hatirlatma guncellendi');
    } else {
        await apiPost('/api/reminders', data);
        showToast('Hatirlatma eklendi');
    }
    closeModal('reminderModal');
    setTimeout(() => location.reload(), 500);
}

async function updateReminderStatus(id, status) {
    await apiPut('/api/reminders/' + id, { status });
    showToast('Hatirlatma guncellendi');
    setTimeout(() => location.reload(), 500);
}

async function deleteReminder(id) {
    if (!confirm('Bu hatirlatma silinsin mi?')) return;
    await apiDelete('/api/reminders/' + id);
    showToast('Hatirlatma silindi');
    setTimeout(() => location.reload(), 500);
}

// ─── Future Deployments ─────────────────────────────────
let repoCounter = 0;

function addRepoRow(data) {
    const container = document.getElementById('fd_repos_container');
    if (!container) return;
    const idx = repoCounter++;
    const div = document.createElement('div');
    div.className = 'repo-form-block';
    div.id = 'repo-row-' + idx;
    div.innerHTML = `
        <div class="repo-form-header">
            <strong>Repo #${idx + 1}</strong>
            <button type="button" class="btn-icon btn-danger" onclick="removeRepoRow(${idx})">&times;</button>
        </div>
        <div class="form-row">
            <div class="form-group"><label>Repo Adi</label><input type="text" class="form-input repo-name" value="${(data && data.name) || ''}" placeholder="Onboarding/shire"></div>
            <div class="form-group"><label>MR URL</label><input type="url" class="form-input repo-mr" value="${(data && data.mr_url) || ''}" placeholder="https://..."></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label>Branch</label><input type="text" class="form-input repo-branch" value="${(data && data.branch) || ''}" placeholder="TCO-XXXX"></div>
            <div class="form-group"><label>Commit</label><input type="text" class="form-input repo-commit" value="${(data && data.commit) || ''}" placeholder="abc1234"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label>Test Branch Merge</label>
                <select class="form-input repo-test-merge">
                    <option value="Yapilmadi"${(data && data.test_merge === 'Yapilmadi') ? ' selected' : ''}>Yapilmadi</option>
                    <option value="Yapildi"${(data && data.test_merge === 'Yapildi') ? ' selected' : ''}>Yapildi</option>
                    <option value="Bilinmiyor"${(data && data.test_merge === 'Bilinmiyor') ? ' selected' : ''}>Bilinmiyor</option>
                    <option value="Teyit Bekliyor"${(data && data.test_merge === 'Teyit Bekliyor') ? ' selected' : ''}>Teyit Bekliyor</option>
                </select>
            </div>
            <div class="form-group"><label>Test Branch Notu</label><input type="text" class="form-input repo-test-note" value="${(data && data.test_note) || ''}" placeholder="Kisa not..."></div>
        </div>
        <div class="form-group"><label>Detay</label><input type="text" class="form-input repo-detail" value="${(data && data.detail) || ''}" placeholder="Teknik detay..."></div>
    `;
    container.appendChild(div);
}

function removeRepoRow(idx) {
    const row = document.getElementById('repo-row-' + idx);
    if (row) row.remove();
}

function collectRepos() {
    const blocks = document.querySelectorAll('.repo-form-block');
    const repos = [];
    blocks.forEach(block => {
        const name = block.querySelector('.repo-name').value.trim();
        if (!name) return;
        repos.push({
            name: name,
            mr_url: block.querySelector('.repo-mr').value.trim(),
            branch: block.querySelector('.repo-branch').value.trim(),
            commit: block.querySelector('.repo-commit').value.trim(),
            test_merge: block.querySelector('.repo-test-merge').value,
            test_note: block.querySelector('.repo-test-note').value.trim(),
            detail: block.querySelector('.repo-detail').value.trim(),
        });
    });
    return repos;
}

function openFdModal() {
    document.getElementById('fdModalTitle').textContent = 'Yeni Deployment';
    document.getElementById('fd_id').value = '';
    document.getElementById('fd_date').value = new Date().toISOString().slice(0, 10);
    document.getElementById('fd_task').value = '';
    document.getElementById('fd_title').value = '';
    document.getElementById('fd_jira_url').value = '';
    document.getElementById('fd_summary').value = '';
    document.getElementById('fd_contacts').value = '';
    document.getElementById('fd_repos_container').innerHTML = '';
    repoCounter = 0;
    addRepoRow();
    openModal('fdModal');
}

function editFd(id, data) {
    document.getElementById('fdModalTitle').textContent = 'Deployment Duzenle';
    document.getElementById('fd_id').value = id;
    document.getElementById('fd_date').value = data.date || '';
    document.getElementById('fd_task').value = data.task || '';
    document.getElementById('fd_title').value = data.title || '';
    document.getElementById('fd_jira_url').value = data.jira_url || '';
    document.getElementById('fd_summary').value = data.summary || '';
    document.getElementById('fd_contacts').value = (data.contacts || []).join(', ');
    document.getElementById('fd_repos_container').innerHTML = '';
    repoCounter = 0;
    const repos = data.repos || [];
    if (repos.length === 0) {
        addRepoRow();
    } else {
        repos.forEach(r => addRepoRow(r));
    }
    openModal('fdModal');
}

async function saveFd(e) {
    e.preventDefault();
    const id = document.getElementById('fd_id').value;
    const task = document.getElementById('fd_task').value.trim();
    const data = {
        date: document.getElementById('fd_date').value,
        task: task,
        title: document.getElementById('fd_title').value,
        jira_url: document.getElementById('fd_jira_url').value || (task ? 'https://odeal.atlassian.net/browse/' + task : ''),
        summary: document.getElementById('fd_summary').value,
        contacts: document.getElementById('fd_contacts').value,
        repos: collectRepos(),
    };

    if (id) {
        await apiPut('/api/future-deployments/' + id, data);
        showToast('Deployment guncellendi');
    } else {
        await apiPost('/api/future-deployments', data);
        showToast('Deployment eklendi');
    }
    closeModal('fdModal');
    setTimeout(() => location.reload(), 500);
}

async function completeFd(id) {
    await apiPut('/api/future-deployments/' + id, { status: 'tamamlandi' });
    showToast('Deployment tamamlandi olarak isaretlendi');
    setTimeout(() => location.reload(), 500);
}

async function revertFd(id) {
    await apiPut('/api/future-deployments/' + id, { status: 'bekliyor' });
    showToast('Deployment bekliyora geri alindi');
    setTimeout(() => location.reload(), 500);
}

async function deleteFd(id) {
    if (!confirm('Bu deployment kaydi silinsin mi?')) return;
    await apiDelete('/api/future-deployments/' + id);
    showToast('Deployment silindi');
    setTimeout(() => location.reload(), 500);
}

async function copyFdMarkdown(id) {
    try {
        const res = await fetch('/api/future-deployments/' + id + '/markdown');
        const data = await res.json();
        await navigator.clipboard.writeText(data.markdown);
        showToast('Markdown kopyalandi');
    } catch (err) {
        showToast('Kopyalama basarisiz');
    }
}

async function copyLogMarkdown(task, date) {
    try {
        const res = await fetch('/api/deployment-markdown?task=' + encodeURIComponent(task) + '&date=' + encodeURIComponent(date));
        const data = await res.json();
        if (data.markdown) {
            await navigator.clipboard.writeText(data.markdown);
            showToast('Markdown kopyalandi');
        } else {
            showToast('Kayit bulunamadi');
        }
    } catch (err) {
        showToast('Kopyalama basarisiz');
    }
}

// ─── Smart Insights & Notifications ─────────────────────
let notifOpen = false;
let insightsData = [];

function toggleNotifPanel() {
    const panel = document.getElementById('notifPanel');
    notifOpen = !notifOpen;
    panel.classList.toggle('open', notifOpen);
}

function loadInsights() {
    fetch('/api/smart-insights')
        .then(r => r.json())
        .then(items => {
            insightsData = items;
            updateNotifBadge(items);
            renderNotifPanel(items);
            showInsightPopups(items);
        })
        .catch(() => {});
}

function updateNotifBadge(items) {
    const badge = document.getElementById('notifBadge');
    const critical = items.filter(i => i.type === 'critical' || i.type === 'warning').length;
    if (critical > 0) {
        badge.textContent = critical;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

function renderNotifPanel(items) {
    const body = document.getElementById('notifPanelBody');
    if (!items.length) {
        body.innerHTML = '<p class="empty-state" style="padding:16px">Her sey yolunda!</p>';
        return;
    }
    const typeOrder = { critical: 0, warning: 1, info: 2, success: 3, neutral: 4 };
    items.sort((a, b) => (typeOrder[a.type] || 9) - (typeOrder[b.type] || 9));

    let html = '';
    items.forEach(item => {
        html += `<a href="${item.action || '#'}" class="notif-item notif-${item.type}">
            <span class="notif-dot notif-dot-${item.type}"></span>
            <div class="notif-body">
                <div class="notif-title">${item.title}</div>
                <div class="notif-text">${item.text}</div>
            </div>
            <span class="notif-cat">${item.category}</span>
        </a>`;
    });
    body.innerHTML = html;
}

function showInsightPopups(items) {
    const shown = JSON.parse(sessionStorage.getItem('ys_notif_shown') || '[]');
    const now = Date.now();
    let delay = 800;

    items.forEach(item => {
        if (item.type !== 'critical' && item.type !== 'warning') return;
        if (shown.includes(item.id)) return;

        setTimeout(() => {
            showSmartToast(item);
        }, delay);
        delay += 2000;

        shown.push(item.id);
    });

    sessionStorage.setItem('ys_notif_shown', JSON.stringify(shown));
    // Reset shown list every 30 min
    setTimeout(() => sessionStorage.removeItem('ys_notif_shown'), 30 * 60 * 1000);
}

function showSmartToast(item) {
    const el = document.createElement('div');
    el.className = 'smart-toast smart-toast-' + item.type;
    el.innerHTML = `
        <div class="smart-toast-top">
            <span class="smart-toast-title">${item.title}</span>
            <button class="smart-toast-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
        </div>
        <div class="smart-toast-text">${item.text}</div>
        ${item.action ? `<a href="${item.action}" class="smart-toast-link">Git &rarr;</a>` : ''}
    `;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 400);
    }, 6000);
}

// Close notif panel on outside click
document.addEventListener('click', function(e) {
    const wrap = document.querySelector('.notif-bell-wrap');
    if (wrap && notifOpen && !wrap.contains(e.target)) {
        toggleNotifPanel();
    }
});

// Load on page ready, refresh every 5 min
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadInsights, 1200);
    setInterval(loadInsights, 5 * 60 * 1000);
});

// ─── Click-to-Copy ──────────────────────────────────────
document.addEventListener('click', function(e) {
    const el = e.target.closest('.clickable-copy');
    if (!el) return;
    const text = el.getAttribute('data-copy');
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        showToast('Kopyalandi: ' + (text.length > 50 ? text.slice(0, 50) + '...' : text));
    });
});

// ─── Global Search Shortcut ─────────────────────────────
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.search-input');
        if (searchInput) searchInput.focus();
    }
});

// ─── Git Pulse & Intelligence ──────────────────────────
function escapeHtml(value) {
    return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function animateElements(elements, baseDelay = 0, step = 55) {
    const list = Array.from(elements || []).filter(Boolean);
    const seen = new Set();
    const unique = list.filter((el) => {
        if (seen.has(el)) return false;
        seen.add(el);
        return true;
    });

    const anim = window.YS_ANIM || {};
    const skip = !anim.page_reveal || anim.pageOff;
    if (skip) {
        unique.forEach((el) => {
            el.dataset.revealReady = '1';
            el.classList.add('page-reveal-target', 'live');
            el.style.setProperty('--reveal-delay', '0ms');
        });
        return;
    }

    unique.forEach((el, index) => {
        if (el.dataset.revealReady === '1') return;
        el.dataset.revealReady = '1';
        el.classList.add('page-reveal-target');
        el.style.setProperty('--reveal-delay', `${baseDelay + (Math.min(index, 18) * step)}ms`);
        requestAnimationFrame(() => el.classList.add('live'));
    });
}

function animateScopedElements(root, selector, baseDelay = 0, step = 55) {
    if (!root) return;
    animateElements(root.querySelectorAll(selector), baseDelay, step);
}

function runPageBootOverlay() {
    const anim = window.YS_ANIM || {};
    if (!anim.page_boot || anim.pageOff) return;
    const host = document.querySelector('.page-content');
    if (!host || host.querySelector('.page-boot-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'page-boot-overlay';

    const grid = document.createElement('div');
    grid.className = 'page-boot-grid';

    const label = document.createElement('div');
    label.className = 'page-boot-label';
    const title = (document.querySelector('.page-title')?.textContent || document.title || 'workspace').trim().toUpperCase();
    label.textContent = `LOADING ${title}`;

    overlay.appendChild(grid);
    overlay.appendChild(label);
    host.appendChild(overlay);

    requestAnimationFrame(() => overlay.classList.add('active'));
    setTimeout(() => overlay.classList.add('done'), 520);
    setTimeout(() => overlay.remove(), 1200);
}

function runPageLoadAnimations() {
    const selectors = [
        '.smart-tips',
        '.status-bar > .status-card',
        '.dashboard-grid > .card',
        '.team-pulse-hero',
        '.team-pulse-summary > *',
        '.search-hero',
        '.search-smart-banner',
        '.search-smart-tokens',
        '.search-suggestions',
        '.search-results > .search-result-card',
        '.trace-layout > .trace-view',
        '.trace-layout > .trace-intelligence-panel',
        '.docs-layout > .docs-sidebar',
        '.docs-layout > .docs-content',
        '.settings-grid > .card',
        '.settings-save',
        '.empty-state-large',
        '.search-tips',
        '.detail-card'
    ];

    animateElements(document.querySelectorAll(selectors.join(', ')), 40, 60);
}

function renderSparkline(values) {
    if (!values || !values.length) return '';
    const max = Math.max(...values, 1);
    return `<div class="pulse-sparkline">` + values.map(v => {
        const pct = Math.max(Math.round((v / max) * 100), 10);
        return `<span class="pulse-sparkline-bar" style="height:${pct}%"></span>`;
    }).join('') + `</div>`;
}

let gitPulseOpen = false;
let gitPulseLoaded = false;

function loadGitPulseWidget(forceRefresh = false) {
    const shell = document.getElementById('gitPulseDrawerBody');
    if (!shell) return;
    const url = forceRefresh ? '/api/git-pulse/sidebar?refresh=1' : '/api/git-pulse/sidebar';
    fetch(url)
        .then(r => r.json())
        .then(data => {
            const people = (data.top_people || []).map(person => `
                <a href="/team-pulse" class="git-pulse-row">
                    <span class="git-pulse-row-title">${escapeHtml(person.name)}</span>
                    <span class="git-pulse-row-meta">${person.mr_count || 0} PR • ${person.merge_count || 0} merge</span>
                </a>
            `).join('');
            const repos = (data.top_repos || []).slice(0, 3).map(repo => `
                <a href="/team-pulse" class="git-pulse-repo-row">
                    <span>${escapeHtml(repo.slug)}</span>
                    <strong>${repo.commit_count_7d || 0}</strong>
                </a>
            `).join('');

            shell.innerHTML = `
                <div class="git-pulse-drawer-stats">
                    <a href="/team-pulse" class="git-pulse-stat"><strong>${data.summary.commits_24h || 0}</strong><span>24s commit</span></a>
                    <a href="/team-pulse" class="git-pulse-stat"><strong>${data.summary.merge_count || 0}</strong><span>PR/Merge</span></a>
                    <a href="/team-pulse" class="git-pulse-stat"><strong>${data.summary.active_repos || 0}</strong><span>aktif repo</span></a>
                </div>
                <div class="git-pulse-section">
                    <div class="git-pulse-section-label">Top people</div>
                    ${people || '<p class="empty-state">Hareket yok.</p>'}
                </div>
                <div class="git-pulse-section">
                    <div class="git-pulse-section-label">Hot repos</div>
                    ${repos || '<p class="empty-state">Repo hareketi yok.</p>'}
                </div>
            `;
            gitPulseLoaded = true;
            animateScopedElements(shell, '.git-pulse-stat, .git-pulse-section, .git-pulse-row, .git-pulse-repo-row', 20, 45);
        })
        .catch(() => {});
}

function setGitPulseOpen(open) {
    const drawer = document.getElementById('gitPulseDrawer');
    const fab = document.getElementById('gitPulseFab');
    if (!drawer || !fab) return;
    gitPulseOpen = open;
    drawer.classList.toggle('open', open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.classList.toggle('active', open);
    if (open && !gitPulseLoaded) loadGitPulseWidget(false);
}

function toggleGitPulseDrawer() {
    setGitPulseOpen(!gitPulseOpen);
}

function initGitPulseWidget() {
    const fab = document.getElementById('gitPulseFab');
    const btn = document.getElementById('gitPulseFabBtn');
    const drawer = document.getElementById('gitPulseDrawer');
    const closeBtn = document.getElementById('gitPulseCloseBtn');
    if (!fab || !btn || !drawer || !closeBtn) return;

    const storageKey = 'ys_git_pulse_pos';
    const defaultX = window.innerWidth - 120;
    const defaultY = Math.max(120, Math.round(window.innerHeight * 0.42));
    const saved = (() => {
        try {
            return JSON.parse(localStorage.getItem(storageKey) || 'null');
        } catch (_err) {
            return null;
        }
    })();

    let posX = (saved && typeof saved.x === 'number') ? saved.x : defaultX;
    let posY = (saved && typeof saved.y === 'number') ? saved.y : defaultY;
    let dragState = null;

    function applyPosition() {
        const rect = fab.getBoundingClientRect();
        const maxX = Math.max(12, window.innerWidth - rect.width - 12);
        const maxY = Math.max(12, window.innerHeight - rect.height - 12);
        posX = Math.min(Math.max(12, posX), maxX);
        posY = Math.min(Math.max(12, posY), maxY);
        fab.style.left = posX + 'px';
        fab.style.top = posY + 'px';
    }

    function persistPosition() {
        localStorage.setItem(storageKey, JSON.stringify({ x: posX, y: posY }));
    }

    btn.addEventListener('pointerdown', (event) => {
        dragState = {
            startX: event.clientX,
            startY: event.clientY,
            originX: posX,
            originY: posY,
            moved: false,
        };
        btn.setPointerCapture(event.pointerId);
        fab.classList.add('dragging');
    });

    btn.addEventListener('pointermove', (event) => {
        if (!dragState) return;
        const deltaX = event.clientX - dragState.startX;
        const deltaY = event.clientY - dragState.startY;
        if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
            dragState.moved = true;
        }
        posX = dragState.originX + deltaX;
        posY = dragState.originY + deltaY;
        applyPosition();
    });

    btn.addEventListener('pointerup', (event) => {
        if (!dragState) return;
        btn.releasePointerCapture(event.pointerId);
        const moved = dragState.moved;
        dragState = null;
        fab.classList.remove('dragging');
        persistPosition();
        if (!moved) {
            toggleGitPulseDrawer();
        }
    });

    btn.addEventListener('pointercancel', () => {
        dragState = null;
        fab.classList.remove('dragging');
    });

    closeBtn.addEventListener('click', () => setGitPulseOpen(false));

    document.addEventListener('click', (event) => {
        if (!gitPulseOpen) return;
        if (fab.contains(event.target) || drawer.contains(event.target)) return;
        setGitPulseOpen(false);
    });

    window.addEventListener('resize', applyPosition);
    applyPosition();
    loadGitPulseWidget(false);
}

function loadDashboardEnhancements() {
    loadTeamRepoPulseCard();
    loadFollowUpRadarCard();
    loadDecisionMemoryCard();
}

function loadTeamRepoPulseCard() {
    const target = document.getElementById('teamRepoPulseCard');
    if (!target) return;
    fetch('/api/team-pulse')
        .then(r => r.json())
        .then(data => {
            const people = (data.contributors || []).slice(0, 5).map(person => `
                <div class="pulse-person-row">
                    <div>
                        <div class="pulse-person-name">${escapeHtml(person.name)}</div>
                        <div class="pulse-person-meta">${person.commit_count} commit • ${person.mr_count} PR • ${person.merge_count} merge</div>
                    </div>
                    <span class="pulse-person-time">${escapeHtml(person.last_activity_label || '-')}</span>
                </div>
            `).join('');

            const repos = (data.repos || []).slice(0, 5).map(repo => `
                <a href="/repo-deployments?repo=${encodeURIComponent(repo.name)}" class="pulse-repo-row">
                    <div>
                        <div class="pulse-repo-name">${escapeHtml(repo.name)}</div>
                        <div class="pulse-repo-meta">${repo.commit_count_7d} commit / 7g • ${repo.mr_count} PR</div>
                    </div>
                    ${renderSparkline(repo.trend)}
                </a>
            `).join('');

            const prs = (data.recent_prs || []).slice(0, 6).map(item => `
                <a href="${item.mr_url || '/team-pulse'}" ${item.mr_url ? 'target="_blank"' : ''} class="pulse-pr-row">
                    <span class="pulse-pr-repo">${escapeHtml(item.repo_slug)}</span>
                    <span class="pulse-pr-title">${escapeHtml(item.title)}</span>
                    <span class="pulse-pr-owner">${escapeHtml(item.owner_name)}</span>
                </a>
            `).join('');

            target.innerHTML = `
                <div class="team-pulse-card-grid">
                    <div class="team-pulse-section">
                        <div class="team-pulse-section-title">Top People</div>
                        ${people || '<p class="empty-state">Kisi verisi yok.</p>'}
                    </div>
                    <div class="team-pulse-section">
                        <div class="team-pulse-section-title">Repo Pulse</div>
                        ${repos || '<p class="empty-state">Repo verisi yok.</p>'}
                    </div>
                    <div class="team-pulse-section">
                        <div class="team-pulse-section-title">Recent PR / Merge</div>
                        ${prs || '<p class="empty-state">Merge izi yok.</p>'}
                    </div>
                </div>
            `;
            animateScopedElements(target, '.team-pulse-section, .pulse-person-row, .pulse-repo-row, .pulse-pr-row', 30, 45);
        })
        .catch(() => {
            target.innerHTML = '<p class="empty-state">Git pulse verisi okunamadi.</p>';
        });
}

function renderRadarRows(items) {
    if (!items || !items.length) return '<p class="empty-state">Her sey dengeli gorunuyor.</p>';
    return items.map(item => `
        <a href="${item.href || '#'}" class="radar-row radar-${item.severity}">
            <div class="radar-title">${escapeHtml(item.title)}</div>
            <div class="radar-text">${escapeHtml(item.text)}</div>
        </a>
    `).join('');
}

function loadFollowUpRadarCard() {
    const target = document.getElementById('followUpRadarCard');
    if (!target) return;
    fetch('/api/follow-up-radar')
        .then(r => r.json())
        .then(items => {
            target.innerHTML = renderRadarRows(items);
            animateScopedElements(target, '.radar-row', 20, 50);
        })
        .catch(() => {
            target.innerHTML = '<p class="empty-state">Follow-up radar okunamadi.</p>';
        });
}

function renderDecisionMemoryRows(items) {
    if (!items || !items.length) return '<p class="empty-state">Karar hafizasi kaydi bulunamadi.</p>';
    return items.map(item => `
        <a href="/docs?path=${encodeURIComponent(item.source_path)}" class="decision-row">
            <div class="decision-row-top">
                <span class="decision-row-date">${escapeHtml(item.date)}</span>
                <span class="decision-row-source">${escapeHtml(item.source_name)}</span>
            </div>
            <div class="decision-row-text">${escapeHtml(item.text)}</div>
        </a>
    `).join('');
}

function loadDecisionMemoryCard() {
    const target = document.getElementById('decisionMemoryCard');
    if (!target) return;
    fetch('/api/decision-memory')
        .then(r => r.json())
        .then(items => {
            target.innerHTML = renderDecisionMemoryRows(items);
            animateScopedElements(target, '.decision-row', 20, 50);
        })
        .catch(() => {
            target.innerHTML = '<p class="empty-state">Decision memory okunamadi.</p>';
        });
}

function renderTcoIntelligenceHtml(data, compact = false) {
    const docs = (data.docs || []).map(doc => `
        <span class="tco-doc-pill ${doc.count > 0 ? 'active' : ''}">
            ${doc.type.replaceAll('_', ' ')} <strong>${doc.count}</strong>
        </span>
    `).join('');

    const repos = (data.git.top_repos || []).slice(0, compact ? 3 : 5).map(repo => `
        <div class="tco-mini-row">
            <span>${escapeHtml(repo.slug || repo.name)}</span>
            <strong>${repo.score || repo.commit_count_30d || 0}</strong>
        </div>
    `).join('');

    const contributors = (data.git.top_contributors || []).slice(0, compact ? 3 : 5).map(person => `
        <div class="tco-mini-row">
            <span>${escapeHtml(person.name)}</span>
            <strong>${person.score || person.mr_count || person.commit_count || 0}</strong>
        </div>
    `).join('');

    const followups = renderRadarRows(data.followups || []);
    const decisions = renderDecisionMemoryRows(data.decisions || []);

    return `
        <div class="tco-intel-shell" data-tco-intel-shell>
            <div class="tco-health tco-health-${(data.health.label || '').toLowerCase().replaceAll(' ', '-')}">
                <div>
                    <div class="tco-health-label">Health</div>
                    <div class="tco-health-value">${escapeHtml(data.health.label)} <span>${data.health.score}/100</span></div>
                </div>
                <div class="tco-health-actions">
                    <a href="/search?q=${encodeURIComponent(data.tco)}" class="btn btn-ghost btn-sm">Trace Ac</a>
                    <button type="button" class="btn btn-ghost btn-sm tco-intel-toggle" onclick="toggleTcoIntelligence(this)" aria-expanded="true">Daralt</button>
                </div>
            </div>
            <div class="tco-intel-details">
                <div class="tco-doc-pills">${docs}</div>
                <div class="tco-intel-grid ${compact ? 'compact' : ''}">
                    <div class="tco-intel-section">
                        <div class="team-pulse-section-title">Git Pulse</div>
                        <div class="tco-mini-stats">
                            <div class="tco-mini-stat"><strong>${data.git.commit_count_7d}</strong><span>7g commit</span></div>
                            <div class="tco-mini-stat"><strong>${data.git.commit_count_30d}</strong><span>30g commit</span></div>
                            <div class="tco-mini-stat"><strong>${data.git.merge_count}</strong><span>PR/merge</span></div>
                        </div>
                        ${repos || '<p class="empty-state">Repo izi yok.</p>'}
                    </div>
                    <div class="tco-intel-section">
                        <div class="team-pulse-section-title">Contributors</div>
                        ${contributors || '<p class="empty-state">Katkici izi yok.</p>'}
                    </div>
                </div>
                <div class="tco-intel-section">
                    <div class="team-pulse-section-title">Follow-up Radar</div>
                    ${followups}
                </div>
                <div class="tco-intel-section">
                    <div class="team-pulse-section-title">Decision Memory</div>
                    ${decisions}
                </div>
            </div>
        </div>
    `;
}

function toggleTcoIntelligence(button) {
    const shell = button.closest('[data-tco-intel-shell]');
    if (!shell) return;
    const collapsed = shell.classList.toggle('collapsed');
    button.textContent = collapsed ? 'Genislet' : 'Daralt';
    button.setAttribute('aria-expanded', String(!collapsed));
}

function runDashboardTcoIntelligence() {
    const input = document.getElementById('dashTcoInput');
    const target = document.getElementById('dashTcoIntelligenceResult');
    if (!input || !target) return;
    const raw = (input.value || '').trim().toUpperCase();
    if (!raw) {
        showToast('Bir TCO gir');
        return;
    }
    const tco = raw.startsWith('TCO-') ? raw : `TCO-${raw}`;
    target.innerHTML = '<p class="empty-state">Analiz yapiliyor...</p>';
    fetch('/api/tco-intelligence?tco=' + encodeURIComponent(tco))
        .then(r => r.json())
        .then(data => {
            target.innerHTML = renderTcoIntelligenceHtml(data, true);
            animateScopedElements(target, '.tco-intel-shell, .tco-doc-pill, .tco-intel-section, .radar-row, .decision-row', 20, 45);
        })
        .catch(() => {
            target.innerHTML = '<p class="empty-state">TCO intelligence okunamadi.</p>';
        });
}

function loadTcoIntelligencePanel() {
    const panel = document.getElementById('tcoIntelligencePanel');
    if (!panel) return;
    const tco = panel.getAttribute('data-tco');
    if (!tco) return;
    fetch('/api/tco-intelligence?tco=' + encodeURIComponent(tco))
        .then(r => r.json())
        .then(data => {
            panel.innerHTML = renderTcoIntelligenceHtml(data, false);
            animateScopedElements(panel, '.tco-intel-shell, .tco-doc-pill, .tco-intel-section, .radar-row, .decision-row', 20, 45);
        })
        .catch(() => {
            panel.innerHTML = '<p class="empty-state">TCO intelligence okunamadi.</p>';
        });
}

function renderTeamPulseSummary(summary) {
    return `
        <div class="status-card">
            <div class="status-info"><span class="status-label">24 Saat Commit</span><span class="status-value">${summary.commits_24h || 0}</span></div>
        </div>
        <div class="status-card">
            <div class="status-info"><span class="status-label">7 Gun Commit</span><span class="status-value">${summary.commits_7d || 0}</span></div>
        </div>
        <div class="status-card">
            <div class="status-info"><span class="status-label">PR / Merge</span><span class="status-value">${summary.merge_count || 0}</span></div>
        </div>
        <div class="status-card">
            <div class="status-info"><span class="status-label">Aktif Repo</span><span class="status-value">${summary.active_repos || 0}</span></div>
        </div>
    `;
}

function loadTeamPulsePage(forceRefresh = false) {
    const summaryEl = document.getElementById('teamPulseSummary');
    if (!summaryEl) return;
    const url = forceRefresh ? '/api/team-pulse?refresh=1' : '/api/team-pulse';
    fetch(url)
        .then(r => r.json())
        .then(data => {
            summaryEl.innerHTML = renderTeamPulseSummary(data.summary || {});

            const contributors = (data.contributors || []).map(person => `
                <div class="pulse-person-row">
                    <div>
                        <div class="pulse-person-name">${escapeHtml(person.name)}</div>
                        <div class="pulse-person-meta">${person.commit_count} commit • ${person.mr_count} PR • ${person.merge_count} merge • ${person.repo_count} repo</div>
                    </div>
                    <span class="pulse-person-time">${escapeHtml(person.last_activity_label)}</span>
                </div>
            `).join('');
            document.getElementById('teamPulseContributors').innerHTML = contributors || '<p class="empty-state">Katkici verisi yok.</p>';

            const repos = (data.repos || []).map(repo => `
                <div class="team-repo-card">
                    <div class="team-repo-top">
                        <strong>${escapeHtml(repo.name)}</strong>
                        <span>${repo.commit_count_7d} commit / 7g</span>
                    </div>
                    <div class="team-repo-meta">${repo.mr_count} PR • ${repo.merge_count} merge • ${repo.contributors} kisi</div>
                    ${renderSparkline(repo.trend)}
                </div>
            `).join('');
            document.getElementById('teamPulseRepos').innerHTML = repos || '<p class="empty-state">Repo verisi yok.</p>';

            const prs = (data.recent_prs || []).map(item => `
                <a href="${item.mr_url || '#'}" ${item.mr_url ? 'target="_blank"' : ''} class="pulse-pr-row">
                    <span class="pulse-pr-repo">${escapeHtml(item.repo_slug)}</span>
                    <span class="pulse-pr-title">${escapeHtml(item.title)}</span>
                    <span class="pulse-pr-owner">${escapeHtml(item.owner_name)}</span>
                </a>
            `).join('');
            document.getElementById('teamPulsePRs').innerHTML = prs || '<p class="empty-state">PR / merge verisi yok.</p>';

            const commits = (data.recent_commits || []).map(item => `
                <div class="commit-stream-row">
                    <span class="commit-stream-repo">${escapeHtml(item.repo_slug)}</span>
                    <span class="commit-stream-msg">${escapeHtml(item.subject)}</span>
                    <span class="commit-stream-author">${escapeHtml(item.author_name)}</span>
                    <span class="commit-stream-time">${escapeHtml(item.authored_at_label)}</span>
                </div>
            `).join('');
            document.getElementById('teamPulseCommits').innerHTML = commits || '<p class="empty-state">Commit verisi yok.</p>';

            animateElements(summaryEl.children, 20, 50);
            animateScopedElements(document.getElementById('teamPulseContributors'), '.pulse-person-row', 40, 36);
            animateScopedElements(document.getElementById('teamPulseRepos'), '.team-repo-card', 70, 45);
            animateScopedElements(document.getElementById('teamPulsePRs'), '.pulse-pr-row', 90, 36);
            animateScopedElements(document.getElementById('teamPulseCommits'), '.commit-stream-row', 110, 26);

            if (forceRefresh) {
                loadGitPulseWidget(true);
                showToast('Team Pulse yenilendi');
            }
        })
        .catch(() => {
            summaryEl.innerHTML = '<div class="status-card"><div class="status-info"><span class="status-label">Hata</span><span class="status-value">!</span></div></div>';
        });
}

document.addEventListener('DOMContentLoaded', () => {
    initGitPulseWidget();
    loadTcoIntelligencePanel();
    const splashDelay = document.getElementById('splash') ? 7150 : 80;
    window.setTimeout(() => {
        runPageBootOverlay();
        runPageLoadAnimations();
    }, splashDelay);
});
