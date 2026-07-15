const screens = [...document.querySelectorAll('[data-screen]')];
const toast = document.querySelector('[data-toast]');
const sheetOverlay = document.querySelector('[data-sheet-overlay]');
const sheetContent = document.querySelector('[data-sheet-content]');

const state = {
  screen: 'login',
  authMode: 'login',
  role: 'user',
  points: 128,
  checkedIn: false,
  selectedFields: new Set(['date', 'summary', 'score']),
  rewards: [
    { name: '一起看一场电影', cost: 80, description: '挑一部收藏很久的电影，认真看完。' },
    { name: '奶茶一次', cost: 35, description: '今天的口味和甜度都由你决定。' },
    { name: '认真夸夸 10 分钟', cost: 20, description: '不花钱，但要说得非常具体。' }
  ],
  records: [
    { date: '7月15日', title: '忙完后的热乎晚饭', summary: '忙完一天以后，终于坐下来吃到热乎的晚饭。那一刻没有特别盛大，但整个人都慢慢放松了下来。', score: 88, status: '已收藏', comment: '今天已经很努力了，记得早点休息。' },
    { date: '7月14日', title: '傍晚一起散步', summary: '绕着公园慢慢走了一圈，晚风很舒服，也把白天的疲惫吹散了一些。', score: 91, status: '已同步', comment: '下次也想陪你走这条路。' },
    { date: '7月12日', title: '把计划补完了', summary: '中途被打断了好几次，但晚上还是把最重要的部分做完了。', score: 84, status: '待反馈', comment: '被打断以后还能回来，比一次做完更难得。' }
  ]
};

const navIcons = { home: '⌂', chat: '◌', records: '▤', rewards: '◇', adminRecords: '▤', profile: '○' };
const navLabels = { home: '首页', chat: '记录', records: '日常', rewards: '心意', adminRecords: 'TA 的记录', profile: '我的' };

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[char]);
}

function go(screen) {
  state.screen = screen;
  state.role = screen === 'care' ? 'admin' : 'user';
  document.body.classList.toggle('ops-mode', screen === 'ops');
  screens.forEach((item) => item.classList.toggle('active', item.dataset.screen === screen));
  render();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function showToast(message, type = 'success') {
  toast.textContent = message;
  toast.classList.toggle('error', type === 'error');
  toast.classList.add('show');
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 1800);
}

function render() {
  renderHome();
  renderNavigation();
  renderProfile();
  renderRewards();
  renderRecords();
  renderAdminRecords();
}

function renderNavigation() {
  const items = ['chat', 'records', 'home', 'rewards', 'profile'];
  document.querySelectorAll('[data-bottom-nav]').forEach((nav) => {
    nav.innerHTML = items.map((item) => `<button type="button" data-go="${item}" class="${state.screen === item ? 'selected' : ''}" ${state.screen === item ? 'aria-current="page"' : ''}><i>${navIcons[item]}</i><span>${navLabels[item]}</span></button>`).join('');
  });
}

function renderHome() {
  const home = document.querySelector('[data-screen="home"]');
  home.querySelector('[data-home-greeting]').textContent = '晚上好，杪';
  home.querySelector('[data-role-label]').textContent = '我的视角';
  home.querySelector('[data-hero-eyebrow]').textContent = '今天也在认真生活';
  home.querySelector('[data-hero-title]').textContent = '留下今天的心意';
  home.querySelector('[data-hero-copy]').textContent = '把完成过的小事写下来，慢慢看到自己的节奏。';
  home.querySelector('[data-points]').textContent = state.points;
  const action = home.querySelector('[data-checkin]');
  action.innerHTML = `✦ <span data-checkin-label>${state.checkedIn ? '今日份心意已收集' : '今日签到 · 积分 +10'}</span>`;
  const recordsButton = home.querySelector('[data-primary-records]');
  const actionButton = home.querySelector('[data-primary-action]');
  recordsButton.dataset.go = 'records';
  actionButton.dataset.go = 'chat';
  home.querySelector('[data-section-title]').textContent = '想从哪里开始？';
  home.querySelector('[data-records-title]').textContent = '最近记录';
  home.querySelector('[data-records-copy]').textContent = '回看最近的片段';
  home.querySelector('[data-action-title]').textContent = '和 CCC 聊聊';
  home.querySelector('[data-action-copy]').textContent = '把碎片整理成记录';
}

function renderProfile() {
  document.querySelector('[data-profile-name]').textContent = '杪';
  document.querySelector('[data-binding-copy]').textContent = '已和 TA 互相绑定';
  document.querySelector('[data-profile-points]').textContent = state.points;
  const reward = state.rewards[0];
  document.querySelector('[data-profile-reward-title]').textContent = reward?.name || '心意正在准备中';
  document.querySelector('[data-profile-reward-copy]').textContent = reward?.description || '照顾者添加奖品后会显示在这里。';
  document.querySelector('[data-profile-reward-status]').textContent = reward
    ? `${reward.cost} 分 · ${state.points >= reward.cost ? '现在可兑换' : `还差 ${reward.cost - state.points} 分`}`
    : '打开商店看看';
}

function rewardHtml(reward, care = false) {
  const ready = state.points >= reward.cost;
  const status = care ? (ready ? 'TA 可兑换' : '积分未满') : (ready ? '可兑换' : `还差 ${reward.cost - state.points} 分`);
  return `<button type="button" class="reward-card" ${care ? '' : `data-redeem="${escapeHtml(reward.name)}"`}><i>◇</i><span><b>${escapeHtml(reward.name)}</b><small>${escapeHtml(reward.description)}</small></span><em>${reward.cost} 分 · ${status}</em></button>`;
}

function renderRewards() {
  const empty = '<article class="empty-card glass-card"><b>心意正在准备中</b><p>照顾者添加奖品后会出现在这里。</p></article>';
  const html = state.rewards.length ? state.rewards.map((reward) => rewardHtml(reward)).join('') : empty;
  document.querySelector('[data-shop-reward-list]').innerHTML = html;
  document.querySelector('[data-care-reward-list]').innerHTML = state.rewards.length ? state.rewards.map((reward) => rewardHtml(reward, true)).join('') : empty;
  document.querySelector('[data-shop-points]').textContent = state.points;
  document.querySelector('[data-care-points]').textContent = state.points;
}

function recordCardHtml(record, index) {
  const fields = [];
  if (state.selectedFields.has('date')) fields.push(record.date);
  if (state.selectedFields.has('summary')) fields.push(record.summary.slice(0, 14) + '…');
  if (state.selectedFields.has('score')) fields.push(`${record.score} 分`);
  if (state.selectedFields.has('status')) fields.push(record.status);
  return `<button type="button" class="record-card" data-record-index="${index}"><div class="record-card__top"><h3>${escapeHtml(record.title)}</h3><time>${escapeHtml(record.date)}</time></div><p>${escapeHtml(record.summary)}</p><div class="record-fields">${fields.map((field) => `<span>${escapeHtml(field)}</span>`).join('')}</div></button>`;
}

function renderRecords() {
  document.querySelector('[data-record-list]').innerHTML = state.records.map(recordCardHtml).join('');
  document.querySelectorAll('[data-field]').forEach((button) => button.classList.toggle('selected', state.selectedFields.has(button.dataset.field)));
}

function renderAdminRecords() {
  document.querySelector('[data-admin-record-list]').innerHTML = state.records.map((record, index) => `
    <article class="admin-record-card glass-card">
      <header><h3>${escapeHtml(record.title)}</h3><span>${record.score} 分</span></header>
      <p>${escapeHtml(record.summary)}</p>
      <form class="comment-form" data-comment-index="${index}">
        <textarea name="comment" aria-label="评论">${escapeHtml(record.comment)}</textarea>
        <input name="score" type="number" min="0" max="100" value="${record.score}" aria-label="打分" />
        <button class="primary">保存评论和打分</button>
      </form>
    </article>`).join('');
}

function openSheet(type, value) {
  if (type === 'focus') {
    sheetContent.innerHTML = `<h2>今日热门</h2><p class="sheet-copy">7月15日 08:20 生成 · 来自公开 RSS 的四类信息</p><div class="focus-groups"><section class="focus-group"><h3>AI 与开源</h3><article><b>开源模型工具链持续更新</b><p>从模型能力、部署成本和开发体验三个角度整理今日变化。</p></article><article><b>新的智能体协作框架发布</b><p>关注多步骤任务、确认门和可观察性设计。</p></article></section><section class="focus-group"><h3>中国大事与新闻</h3><article><b>今日重要信息摘要</b><p>保留来源与发布时间，点击正式应用中的条目可查看原文。</p></article></section></div>`;
  } else if (type === 'record') {
    const record = state.records[Number(value)];
    sheetContent.innerHTML = `<article class="record-detail-sheet"><p class="eyebrow">${escapeHtml(record.date)} · ${escapeHtml(record.status)}</p><h3>${escapeHtml(record.title)}</h3><p>${escapeHtml(record.summary)}</p><section class="binding-card glass-card"><b>来自对方的留言</b><p>“${escapeHtml(record.comment)}”</p><strong>${record.score} 分</strong></section></article>`;
  } else if (type === 'addReward') {
    sheetContent.innerHTML = `<h2>添加一份心意</h2><p class="sheet-copy">给绑定用户添加一个可兑换奖品。</p><form class="sheet-form" data-add-reward-form><label class="field"><span>奖品名称</span><input name="name" placeholder="例如：一起看一场电影" /></label><label class="field"><span>所需积分</span><input name="cost" type="number" min="1" value="50" /></label><label class="field"><span>说明</span><textarea name="description" placeholder="写下兑换后的约定"></textarea></label><button class="primary">添加奖品</button></form>`;
  } else if (type === 'redeem') {
    const reward = state.rewards.find((item) => item.name === value);
    sheetContent.innerHTML = `<h2>确认兑换「${escapeHtml(reward.name)}」？</h2><p class="sheet-copy">兑换后会扣除 ${reward.cost} 积分，并在照顾者视角显示兑换提醒。</p><div class="button-row"><button type="button" class="secondary" data-close-sheet>再想想</button><button type="button" class="primary" data-confirm-redeem="${escapeHtml(reward.name)}">确认兑换</button></div>`;
  }
  sheetOverlay.hidden = false;
}

function closeSheet() {
  sheetOverlay.hidden = true;
  sheetContent.innerHTML = '';
}

function switchOpsTab(tab) {
  document.querySelectorAll('[data-ops-tab]').forEach((button) => button.classList.toggle('selected', button.dataset.opsTab === tab));
  document.querySelectorAll('[data-ops-view]').forEach((view) => view.classList.toggle('active', view.dataset.opsView === tab));
  const copy = {
    records: ['记录与异常', '查看记录状态、修正展示并处理飞书同步异常。'],
    daily: ['每日内容配置', '为指定用户配置某一天的首页内容。'],
    trace: ['链路追踪', '用会话、记录或 third session ID 定位完整链路。']
  }[tab];
  document.querySelector('[data-ops-title]').textContent = copy[0];
  document.querySelector('[data-ops-copy]').textContent = copy[1];
}

document.addEventListener('click', (event) => {
  const goButton = event.target.closest('[data-go]');
  if (goButton && goButton.dataset.go) {
    go(goButton.dataset.go);
    return;
  }

  const authMode = event.target.closest('[data-auth-mode]');
  if (authMode) {
    state.authMode = authMode.dataset.authMode;
    document.querySelectorAll('[data-auth-mode]').forEach((button) => button.classList.toggle('selected', button === authMode));
    document.querySelectorAll('.register-only').forEach((item) => item.hidden = state.authMode !== 'register');
    document.querySelector('[data-auth-title]').textContent = state.authMode === 'register' ? '一起开始记录' : '欢迎回来';
    document.querySelector('[data-auth-description]').textContent = state.authMode === 'register' ? '创建账号后，可以邀请对方建立双向绑定。' : '登录后继续收藏那些平凡又重要的小事。';
    return;
  }

  if (event.target.closest('[data-refresh-captcha]')) {
    const code = String(Math.floor(1000 + Math.random() * 9000));
    event.target.closest('[data-refresh-captcha]').textContent = `${code} ↻`;
    return;
  }

  const checkin = event.target.closest('[data-checkin]');
  if (checkin) {
    if (state.checkedIn) return showToast('今天已经签到');
    state.checkedIn = true;
    state.points += 10;
    render();
    showToast('+10 积分 · 今天的认真已被记住');
    return;
  }

  const fieldButton = event.target.closest('[data-field]');
  if (fieldButton) {
    const field = fieldButton.dataset.field;
    if (state.selectedFields.has(field) && state.selectedFields.size > 1) state.selectedFields.delete(field);
    else state.selectedFields.add(field);
    renderRecords();
    return;
  }

  const recordButton = event.target.closest('[data-record-index]');
  if (recordButton) return openSheet('record', recordButton.dataset.recordIndex);

  const sheetButton = event.target.closest('[data-open-sheet]');
  if (sheetButton) return openSheet(sheetButton.dataset.openSheet);

  if (event.target.closest('[data-close-sheet]') || event.target === sheetOverlay) return closeSheet();

  const rewardButton = event.target.closest('[data-redeem]');
  if (rewardButton) {
    return openSheet('redeem', rewardButton.dataset.redeem);
  }

  const redeemConfirm = event.target.closest('[data-confirm-redeem]');
  if (redeemConfirm) {
    const index = state.rewards.findIndex((item) => item.name === redeemConfirm.dataset.confirmRedeem);
    const reward = state.rewards[index];
    if (state.points < reward.cost) return showToast('积分不足', 'error');
    state.points -= reward.cost;
    state.rewards.splice(index, 1);
    closeSheet();
    render();
    showToast('兑换成功，心意已经放进礼物盒');
    return;
  }

  if (event.target.closest('[data-edit-draft]')) {
    document.querySelector('[data-draft]').hidden = true;
    document.querySelector('[data-chat-form] textarea').value = '想再补充：那顿饭是我们一起做的。';
    return;
  }

  if (event.target.closest('[data-confirm-draft]')) {
    document.querySelector('[data-draft]').hidden = true;
    showToast('已经好好收藏啦');
    window.setTimeout(() => go('records'), 650);
    return;
  }

  if (event.target.closest('[data-cancel-chat]')) {
    document.querySelector('[data-draft]').hidden = true;
    showToast('本次记录已取消');
    go('home');
    return;
  }

  const messageButton = event.target.closest('[data-toast-message]');
  if (messageButton) return showToast(messageButton.dataset.toastMessage);

  const opsTab = event.target.closest('[data-ops-tab]');
  if (opsTab) return switchOpsTab(opsTab.dataset.opsTab);

  const careTab = event.target.closest('[data-care-tab]');
  if (careTab) {
    document.querySelectorAll('[data-care-tab]').forEach((button) => button.classList.toggle('selected', button === careTab));
    document.querySelectorAll('[data-care-view]').forEach((view) => view.classList.toggle('active', view.dataset.careView === careTab.dataset.careTab));
    return;
  }

  if (event.target.closest('[data-ops-detail]')) {
    document.querySelector('[data-ops-detail-panel]').hidden = false;
    document.querySelector('[data-ops-detail-panel]').scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  if (event.target.closest('[data-ops-trace]')) {
    switchOpsTab('trace');
    showToast('已带入当前 Record ID');
  }
});

document.addEventListener('submit', (event) => {
  const form = event.target;
  if (form.matches('[data-login-form]')) {
    event.preventDefault();
    go('home');
    return;
  }
  if (form.matches('[data-chat-form]')) {
    event.preventDefault();
    const input = form.message;
    if (!input.value.trim()) return;
    document.querySelector('[data-chat-history]').insertAdjacentHTML('beforeend', `<article class="bubble user">${escapeHtml(input.value.trim())}</article><article class="bubble ai">我整理了一版记录草稿，你可以先看看，再决定收藏或继续修改。</article>`);
    input.value = '';
    document.querySelector('[data-draft]').hidden = false;
    return;
  }
  if (form.matches('[data-binding-form]')) {
    event.preventDefault();
    if (!form.target.value.trim()) return showToast('请输入对方账号', 'error');
    form.reset();
    showToast('绑定邀请已发送');
    return;
  }
  if (form.matches('[data-add-reward-form]')) {
    event.preventDefault();
    const name = form.name.value.trim();
    const cost = Number(form.cost.value);
    if (!name || !Number.isFinite(cost) || cost < 1) return showToast('请填写奖品名称和正整数积分', 'error');
    state.rewards.unshift({ name, cost, description: form.description.value.trim() || '刚刚添加的一份心意。' });
    closeSheet();
    render();
    showToast('奖品已添加');
    return;
  }
  if (form.matches('[data-comment-index]')) {
    event.preventDefault();
    const index = Number(form.dataset.commentIndex);
    const score = Number(form.score.value);
    if (!form.comment.value.trim() || score < 0 || score > 100) return showToast('评论不能为空，分数需为 0-100', 'error');
    state.records[index].comment = form.comment.value.trim();
    state.records[index].score = score;
    render();
    showToast('评论和打分已保存');
    return;
  }
  if (form.matches('[data-ops-filter]')) {
    event.preventDefault();
    showToast('记录列表已按条件刷新');
    return;
  }
  if (form.matches('[data-ops-display]')) {
    event.preventDefault();
    showToast('用户端展示已更新');
    return;
  }
  if (form.matches('[data-daily-form]')) {
    event.preventDefault();
    try { JSON.parse(form.querySelector('textarea').value); }
    catch { return showToast('每日内容 JSON 格式不正确', 'error'); }
    showToast('每日内容已保存');
    return;
  }
  if (form.matches('[data-trace-form]')) {
    event.preventDefault();
    showToast('链路追踪已刷新');
  }
});

render();
