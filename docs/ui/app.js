const screens = document.querySelectorAll('[data-screen]');
const toast = document.querySelector('[data-toast]');

const state = {
  screen: 'login',
  role: 'user',
  points: 128,
  checkins: 0,
  rewards: [
    { name: '一起看电影', cost: 80, note: '适合周末兑换的小奖励' },
    { name: '奶茶一次', cost: 35, note: '管理员添加的轻量奖励' },
    { name: '认真夸夸 10 分钟', cost: 20, note: '不花钱但很有用' }
  ],
  records: [
    { date: '06-18', content: '上午效率不错，下午有点累，但完成了计划。', score: 91, status: '已同步', comment: '今天整体很稳，下午累的时候还能继续推进很棒。' },
    { date: '06-17', content: '按时吃饭，晚上整理了房间，情绪状态更安定。', score: 88, status: '已同步', comment: '这个节奏很好，明天可以继续保持睡前整理。' },
    { date: '06-16', content: '学习时间被打断，但最后补完了核心任务。', score: 82, status: '待反馈', comment: '被打断之后还能回来，这个比完美执行更重要。' }
  ],
  selectedFields: ['date', 'content', 'score']
};

const fieldNames = {
  date: '日期',
  content: '内容',
  score: '打分',
  status: '状态'
};

const sentences = [
  '签到成功，今天的认真已经被记住。',
  '又多了一点积分，也多了一点确定感。',
  '今天不是一下子变好，是慢慢变稳。',
  '完成一次签到，就给今天留下一个小锚点。'
];

function go(screen) {
  state.screen = screen;
  screens.forEach((item) => item.classList.toggle('active', item.dataset.screen === screen));
  render();
}

function render() {
  renderHomeRole();
  renderProfile();
  renderRewards();
  renderUserRecent();
  renderAdminRecent();
}

function renderHomeRole() {
  const homeRole = document.querySelector('[data-home-role-text]');
  const homePoints = document.querySelector('[data-home-points]');
  const left = document.querySelector('[data-dock-left]');
  const right = document.querySelector('[data-dock-right]');
  if (!homeRole || !homePoints || !left || !right) return;

  homeRole.textContent = state.role === 'user' ? '用户视角' : '管理员视角';
  homePoints.textContent = state.points;

  if (state.role === 'user') {
    left.dataset.go = 'chat';
    left.setAttribute('aria-label', '对话');
    left.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.8A3.8 3.8 0 0 1 7.8 3h8.4A3.8 3.8 0 0 1 20 6.8v5.9a3.8 3.8 0 0 1-3.8 3.8H10l-4.1 3.1c-.7.5-1.7 0-1.7-.9v-12Z"/></svg>';
    right.dataset.go = 'userRecent';
    right.setAttribute('aria-label', '最近');
    right.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10a2 2 0 0 1 2 2v14.1c0 1.1-1.2 1.7-2.1 1.1L12 17l-4.9 3.2A1.35 1.35 0 0 1 5 19.1V5a2 2 0 0 1 2-2Zm2 5h6M9 11h6M9 14h4"/></svg>';
  } else {
    left.dataset.go = 'adminRewards';
    left.setAttribute('aria-label', '积分奖品');
    left.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8L12 3Z"/></svg>';
    right.dataset.go = 'adminRecent';
    right.setAttribute('aria-label', '绑定用户最近');
    right.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10a2 2 0 0 1 2 2v14.1c0 1.1-1.2 1.7-2.1 1.1L12 17l-4.9 3.2A1.35 1.35 0 0 1 5 19.1V5a2 2 0 0 1 2-2Zm2 5h6M9 11h6M9 14h4"/></svg>';
  }
}

function renderProfile() {
  const profileName = document.querySelector('[data-profile-name]');
  const profileRole = document.querySelector('[data-profile-role]');
  const profilePointsLabel = document.querySelector('[data-profile-points-label]');
  const profilePoints = document.querySelector('[data-profile-points]');
  const rewardTitle = document.querySelector('[data-reward-title]');
  const boundLabel = document.querySelector('[data-bound-label]');

  if (!profileName || !profileRole) return;
  const isAdmin = state.role === 'admin';
  profileName.textContent = isAdmin ? 'TA 的管理页' : '杪';
  profileRole.textContent = isAdmin ? '管理员视角 · 点击切换' : '用户视角 · 点击切换';
  profilePointsLabel.textContent = isAdmin ? 'TA 的积分' : '我的积分';
  profilePoints.textContent = state.points;
  rewardTitle.textContent = isAdmin ? 'TA 可兑换的奖品' : '可兑换奖品';
  boundLabel.textContent = isAdmin ? '绑定用户：TA' : '绑定管理员：TA';
}

function renderRewards() {
  const rewardList = document.querySelector('[data-reward-list]');
  const adminRewardList = document.querySelector('[data-admin-reward-list]');
  const adminUserPoints = document.querySelector('[data-admin-user-points]');
  if (adminUserPoints) adminUserPoints.textContent = `${state.points} 分`;
  const html = state.rewards.map((reward) => `
    <article class="reward-item">
      <h3>${escapeHtml(reward.name)}</h3>
      <span class="reward-cost">${reward.cost} 分</span>
      <p>${escapeHtml(reward.note || '管理员添加的可兑换奖品')}</p>
    </article>
  `).join('');
  if (rewardList) rewardList.innerHTML = html;
  if (adminRewardList) adminRewardList.innerHTML = html;
}

function renderUserRecent() {
  const list = document.querySelector('[data-user-recent-list]');
  if (!list) return;
  list.innerHTML = state.records.map((record) => {
    const fields = state.selectedFields.map((key) => `
      <div class="record-field">
        <span>${fieldNames[key]}</span>
        <b>${escapeHtml(String(record[key]))}</b>
      </div>
    `).join('');
    return `
      <article class="record-item">
        <div class="record-fields">${fields}</div>
        <p class="bound-comment"><b>管理员评论：</b>${escapeHtml(record.comment)}</p>
      </article>
    `;
  }).join('');
}

function renderAdminRecent() {
  const list = document.querySelector('[data-admin-record-list]');
  if (!list) return;
  list.innerHTML = state.records.map((record, index) => `
    <article class="admin-record-row">
      <div class="admin-fields">
        <div><span>时间</span><b>${escapeHtml(record.date)}</b></div>
        <div><span>内容</span><b>${escapeHtml(record.content)}</b></div>
        <div><span>打分</span><b>${escapeHtml(String(record.score))}</b></div>
      </div>
      <form class="admin-inline-edit" data-admin-comment-form="${index}">
        <input name="comment" value="${escapeAttr(record.comment)}" aria-label="评论" />
        <input name="score" value="${escapeAttr(String(record.score))}" aria-label="打分" />
        <button type="submit" class="inline-action">保存</button>
      </form>
    </article>
  `).join('');
}

function showToast(message, type = 'success') {
  toast.textContent = message;
  toast.classList.toggle('error', type === 'error');
  toast.classList.add('show');
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 1700);
}

function escapeHtml(value) {
  return value.replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/'/g, '&#039;');
}

document.addEventListener('click', (event) => {
  const goButton = event.target.closest('[data-go]');
  if (goButton) {
    go(goButton.dataset.go);
    return;
  }

  if (event.target.closest('[data-switch-role]')) {
    state.role = state.role === 'user' ? 'admin' : 'user';
    render();
    showToast(state.role === 'admin' ? '已切换为管理员视角' : '已切换为用户视角');
    return;
  }

  if (event.target.closest('[data-checkin]')) {
    state.checkins += 1;
    state.points += 5;
    document.querySelector('[data-home-points]').textContent = state.points;
    document.querySelector('[data-checkin-label]').textContent = state.checkins > 0 ? '已签到' : '签到';
    document.querySelector('[data-checkin-sentence]').textContent = sentences[state.checkins % sentences.length];
    showToast('+5 积分');
    render();
    return;
  }

  if (event.target.closest('[data-refresh-captcha]')) {
    const next = Math.floor(1000 + Math.random() * 9000);
    event.target.textContent = next;
  }
});

document.addEventListener('change', (event) => {
  const select = event.target.closest('[data-field-select]');
  if (!select) return;
  state.selectedFields[Number(select.dataset.fieldSelect)] = select.value;
  renderUserRecent();
});

document.addEventListener('submit', (event) => {
  const chatForm = event.target.closest('[data-chat-form]');
  if (chatForm) {
    event.preventDefault();
    const input = chatForm.querySelector('input');
    if (!input.value.trim()) return;
    const history = document.querySelector('.chat-history');
    history.insertAdjacentHTML('beforeend', `<article class="message me">${escapeHtml(input.value.trim())}</article>`);
    input.value = '';
    history.scrollTop = history.scrollHeight;
    return;
  }

  const rewardForm = event.target.closest('[data-reward-form]');
  if (rewardForm) {
    event.preventDefault();
    const reward = rewardForm.reward.value.trim();
    const cost = Number(rewardForm.cost.value.trim());
    if (!reward || !cost || cost < 1) {
      showToast('添加失败：请补全奖品和积分', 'error');
      return;
    }
    state.rewards.unshift({ name: reward, cost, note: '刚刚由管理员添加' });
    rewardForm.reset();
    renderRewards();
    showToast('奖品添加成功');
    return;
  }

  const commentForm = event.target.closest('[data-admin-comment-form]');
  if (commentForm) {
    event.preventDefault();
    const index = Number(commentForm.dataset.adminCommentForm);
    const comment = commentForm.comment.value.trim();
    const score = Number(commentForm.score.value.trim());
    if (!comment || !Number.isFinite(score) || score < 0 || score > 100) {
      showToast('保存失败：评论不能为空，分数需为 0-100', 'error');
      return;
    }
    state.records[index].comment = comment;
    state.records[index].score = score;
    renderAdminRecent();
    renderUserRecent();
    showToast('评论和打分已保存');
  }
});

render();
