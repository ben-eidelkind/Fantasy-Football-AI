const state = {
  token: localStorage.getItem('ffa_token') || null,
  user: null,
  view: 'onboarding',
  dashboard: null,
  leagues: [],
  currentLeague: null,
};

const appEl = document.getElementById('app');
const toastEl = document.getElementById('toast');

document.querySelectorAll('nav button[data-nav]').forEach((btn) => {
  btn.addEventListener('click', () => {
    navigate(btn.dataset.nav);
  });
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  if (!state.token) return;
  await apiPost('/api/auth/logout', {});
  localStorage.removeItem('ffa_token');
  state.token = null;
  state.user = null;
  state.dashboard = null;
  navigate('onboarding');
  showToast('Signed out');
});

async function initialize() {
  if (state.token) {
    const me = await apiGet('/api/me');
    if (me && me.authenticated) {
      state.user = me.user;
      state.featureFlags = me.feature_flags || {};
      navigate('dashboard');
      await loadDashboard();
      return;
    }
    localStorage.removeItem('ffa_token');
    state.token = null;
  }
  navigate('onboarding');
}

function navigate(view, options = {}) {
  state.view = view;
  if (options.leagueId) {
    state.currentLeague = options.leagueId;
  }
  render();
}

async function apiGet(path) {
  try {
    const res = await fetch(path, {
      headers: state.token
        ? {
            Authorization: `Bearer ${state.token}`,
          }
        : undefined,
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Request failed');
    return null;
  }
}

async function apiPost(path, body) {
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Request failed');
    }
    return data;
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Request failed');
    return null;
  }
}

function render() {
  switch (state.view) {
    case 'onboarding':
      renderTemplate('onboarding-template', renderOnboarding);
      break;
    case 'dashboard':
      renderTemplate('dashboard-template', renderDashboard);
      break;
    case 'trade-lab':
      renderTemplate('trade-lab-template', renderTradeLab);
      break;
    case 'settings':
      renderTemplate('settings-template', renderSettings);
      break;
    case 'whats-new':
      renderTemplate('whats-new-template', renderWhatsNew);
      break;
    case 'league':
      renderTemplate('league-detail-template', renderLeagueDetail);
      break;
    default:
      renderTemplate('onboarding-template', renderOnboarding);
  }
}

function renderTemplate(id, enhancer) {
  const template = document.getElementById(id);
  const fragment = template.content.cloneNode(true);
  appEl.replaceChildren(fragment);
  enhancer?.();
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 3000);
}

function renderOnboarding() {
  const requestBtn = document.getElementById('login-request');
  const verifyBtn = document.getElementById('login-verify');
  const demoBtn = document.getElementById('demo-login');
  const emailInput = document.getElementById('login-email');
  const codeContainer = document.getElementById('login-code-container');
  const hintEl = document.getElementById('login-hint');

  requestBtn.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    if (!email) {
      showToast('Enter your email');
      return;
    }
    const response = await apiPost('/api/auth/request-code', { email });
    if (response) {
      codeContainer.hidden = false;
      hintEl.textContent = `We sent a 6-digit code. Demo hint: ${response.debug.code}`;
      showToast('Code sent');
    }
  });

  verifyBtn.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    const code = document.getElementById('login-code').value.trim();
    if (!email || !code) {
      showToast('Enter the email and code');
      return;
    }
    const response = await apiPost('/api/auth/verify', { email, code });
    if (response) {
      completeSignIn(response.token);
    }
  });

  demoBtn.addEventListener('click', async () => {
    const response = await apiPost('/api/demo/login', {});
    if (response) {
      completeSignIn(response.token, true);
    }
  });

  const connectBtn = document.getElementById('connect-espn');
  const syncBtn = document.getElementById('sync-leagues');
  const connectionPanel = document.getElementById('espn-connection');
  const selectionContainer = document.getElementById('league-selection');

  if (state.user) {
    connectionPanel.hidden = false;
  }

  connectBtn.addEventListener('click', async () => {
    const begin = await apiPost('/api/espn/begin', { provider: 'mock' });
    if (!begin) return;
    showToast('Opening ESPN login');
    const popup = window.open(
      begin.authorization_url,
      'mock-espn',
      'width=420,height=520'
    );
    const handleMessage = async (event) => {
      if (event.data?.type === 'mock-espn-success' && event.data.state === begin.state_id) {
        window.removeEventListener('message', handleMessage);
        if (popup && !popup.closed) popup.close();
        await apiPost('/api/espn/complete', {
          state_id: begin.state_id,
          provider: 'mock',
          tokens: { access_token: 'mock-session' },
        });
        showToast('ESPN connected');
        connectionPanel.hidden = false;
      }
    };
    window.addEventListener('message', handleMessage);
  });

  syncBtn.addEventListener('click', async () => {
    const leagues = await apiPost('/api/espn/sync', { provider: 'mock' });
    if (!leagues) return;
    selectionContainer.replaceChildren();
    const form = document.createElement('form');
    form.className = 'grid';
    leagues.leagues.forEach((league) => {
      const label = document.createElement('label');
      label.innerHTML = `<input type="checkbox" name="league" value="${league.id}" checked /> ${league.name} (${league.season})`;
      form.appendChild(label);
    });
    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.textContent = 'Activate Selected Leagues';
    submit.className = 'primary';
    form.appendChild(submit);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const selected = Array.from(form.querySelectorAll('input[name="league"]:checked')).map((input) => input.value);
      await apiPost('/api/espn/activate', { league_ids: selected });
      showToast('Leagues activated');
      await loadDashboard();
      navigate('dashboard');
    });
    selectionContainer.appendChild(form);
  });
}

function completeSignIn(token, demo = false) {
  localStorage.setItem('ffa_token', token);
  state.token = token;
  showToast(demo ? 'Demo mode ready' : 'Signed in');
  navigate('dashboard');
  loadMe().then(loadDashboard);
}

async function loadMe() {
  const me = await apiGet('/api/me');
  if (me && me.authenticated) {
    state.user = me.user;
    state.featureFlags = me.feature_flags;
  }
}

async function loadDashboard() {
  const response = await apiGet('/api/dashboard');
  if (response) {
    state.dashboard = response;
    const leagues = response.leagues || [];
    state.leagues = leagues.map((card) => card.league);
    render();
  }
}

function renderDashboard() {
  const container = document.getElementById('dashboard-cards');
  if (!state.dashboard) {
    container.textContent = 'Loading your leagues...';
    return;
  }
  container.replaceChildren();
  state.dashboard.leagues.forEach((card) => {
    const el = document.createElement('article');
    el.className = 'card';
    el.innerHTML = `
      <header>
        <h2>${card.league.name}</h2>
        <div class="badge">Season ${card.league.season}</div>
      </header>
      <div>
        <strong>Lineup delta:</strong> ${card.lineup ? card.lineup.delta : '—'} pts
      </div>
      <div>
        <strong>Waiver gems:</strong>
        <ul>
          ${(card.waivers || [])
            .map(
              (w) => `<li>${w.player.name} (${w.player.position}) – score ${w.total_score}</li>`
            )
            .join('') || '<li>No suggestions yet</li>'}
        </ul>
      </div>
      <div>
        <strong>Matchup odds:</strong> ${card.matchup ? card.matchup.win_probability * 100 : 0}%
      </div>
      <button class="secondary" data-league="${card.league.id}">Open League</button>
    `;
    el.querySelector('button').addEventListener('click', () => {
      navigate('league', { leagueId: card.league.id });
    });
    container.appendChild(el);
  });
}

async function renderTradeLab() {
  if (!state.leagues.length) {
    appEl.querySelector('#trade-results').textContent = 'Connect or activate a league to see trade ideas.';
    return;
  }
  const leagueId = state.leagues[0].id;
  const trades = await apiGet(`/api/leagues/${leagueId}/trades`);
  const container = appEl.querySelector('#trade-results');
  container.replaceChildren();
  if (!trades || !trades.proposals.length) {
    container.textContent = 'No trade improvements detected.';
    return;
  }
  trades.proposals.forEach((proposal) => {
    const el = document.createElement('article');
    el.className = 'card';
    el.innerHTML = `
      <h3>Balanced ${proposal.offer_players.length}-for-${proposal.request_players.length} swap</h3>
      <p><strong>You give:</strong> ${proposal.offer_players.map((p) => p.name).join(', ')}</p>
      <p><strong>You receive:</strong> ${proposal.request_players.map((p) => p.name).join(', ')}</p>
      <p>Lineup delta: <span class="badge">+${proposal.lineup_delta}</span> | Playoff odds +${(proposal.playoff_odds_delta * 100).toFixed(1)}%</p>
      <p class="hint">${proposal.notes}</p>
    `;
    container.appendChild(el);
  });
}

async function renderSettings() {
  await loadMe();
  const flagsContainer = document.getElementById('feature-flags');
  flagsContainer.replaceChildren();
  Object.entries(state.featureFlags || {}).forEach(([flag, enabled]) => {
    const label = document.createElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = enabled;
    input.addEventListener('change', async () => {
      await apiPost('/api/feature-flags', { flag, enabled: input.checked });
      showToast(`${flag} ${input.checked ? 'enabled' : 'disabled'}`);
    });
    label.append(input, document.createTextNode(` ${flag}`));
    flagsContainer.appendChild(label);
  });
  document.getElementById('reconnect-espn').addEventListener('click', () => {
    navigate('onboarding');
    setTimeout(() => document.getElementById('connect-espn').focus(), 100);
  });
  const notifications = await apiGet('/api/notifications');
  const list = document.getElementById('notification-list');
  list.replaceChildren();
  (notifications?.notifications || []).forEach((item) => {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<h3>${item.type}</h3><p>${item.message}</p>`;
    list.appendChild(div);
  });
}

async function renderWhatsNew() {
  const container = document.getElementById('whats-new-content');
  const res = await fetch('/whats-new.json').catch(() => null);
  if (!res || !res.ok) {
    container.textContent = 'Changelog not available yet.';
    return;
  }
  const entries = await res.json();
  container.replaceChildren();
  entries.forEach((entry) => {
    const section = document.createElement('section');
    section.className = 'panel';
    section.innerHTML = `<h2>${entry.title}</h2><p>${entry.body}</p><small>${entry.date}</small>`;
    container.appendChild(section);
  });
}

async function renderLeagueDetail() {
  const leagueId = state.currentLeague || (state.leagues[0] && state.leagues[0].id);
  if (!leagueId) {
    appEl.querySelector('#league-content').textContent = 'Select a league from the dashboard first.';
    return;
  }
  const league = state.leagues.find((l) => l.id === leagueId) || { name: 'League' };
  document.getElementById('league-title').textContent = league.name;
  const tabBar = document.querySelector('.tab-bar');
  tabBar.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBar.querySelectorAll('button').forEach((b) => b.setAttribute('aria-selected', 'false'));
      btn.setAttribute('aria-selected', 'true');
      loadLeagueTab(leagueId, btn.dataset.tab);
    });
  });
  tabBar.querySelector('button').click();
}

async function loadLeagueTab(leagueId, tab) {
  const container = document.getElementById('league-content');
  container.textContent = 'Loading…';
  if (tab === 'overview') {
    const matchup = await apiGet(`/api/leagues/${leagueId}/matchup`);
    const heatmap = await apiGet(`/api/leagues/${leagueId}/matchup?opponent=${encodeURIComponent('team-002')}`);
    container.innerHTML = `
      <div class="card">Win probability: ${(matchup?.win_probability * 100 || 0).toFixed(1)}%<br/>Median: ${matchup?.median_score || 0}</div>
      <div class="card">Scenario planner ready – run what-if trades to adjust playoff odds.</div>
    `;
    return;
  }
  if (tab === 'roster') {
    const roster = await apiGet(`/api/leagues/${leagueId}/roster`);
    if (!roster?.lineup) {
      container.textContent = 'No roster found';
      return;
    }
    const list = document.createElement('ul');
    roster.lineup.lineup.forEach((slot) => {
      const item = document.createElement('li');
      item.textContent = `${slot.slot}: ${slot.name} – ${slot.projected_points} pts (${slot.recommendation})`;
      list.appendChild(item);
    });
    const summary = document.createElement('p');
    summary.textContent = `Projected total ${roster.lineup.total_projection} (Δ ${roster.lineup.delta}). ${roster.lineup.rationale}`;
    container.replaceChildren(summary, list);
    return;
  }
  if (tab === 'waivers') {
    const waivers = await apiGet(`/api/leagues/${leagueId}/waivers`);
    const list = document.createElement('ol');
    (waivers?.candidates || []).forEach((candidate) => {
      const item = document.createElement('li');
      item.innerHTML = `<strong>${candidate.player.name}</strong> ${candidate.player.position} — score ${candidate.total_score}<br/><span class="hint">${candidate.explanation}</span>`;
      list.appendChild(item);
    });
    container.replaceChildren(list);
    return;
  }
  if (tab === 'trades') {
    const trades = await apiGet(`/api/leagues/${leagueId}/trades`);
    const list = document.createElement('div');
    (trades?.proposals || []).forEach((proposal) => {
      const card = document.createElement('article');
      card.className = 'card';
      card.innerHTML = `
        <h3>Trade idea</h3>
        <p>You give: ${proposal.offer_players.map((p) => p.name).join(', ')}</p>
        <p>You receive: ${proposal.request_players.map((p) => p.name).join(', ')}</p>
        <p>Lineup delta +${proposal.lineup_delta} | Playoff odds +${(proposal.playoff_odds_delta * 100).toFixed(1)}%</p>
        <p class="hint">${proposal.notes}</p>
      `;
      list.appendChild(card);
    });
    container.replaceChildren(list);
    return;
  }
  if (tab === 'schedule') {
    const schedule = await apiGet(`/api/dashboard`); // reuse for heatmap
    container.innerHTML = '<p>Playoff heatmap driven by nightly simulations.</p>';
    return;
  }
}

initialize();
