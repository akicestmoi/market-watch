const AGENT_CHAT_STORAGE_KEY = 'marketWatchAgentChatMessages';

let agentChatMessages = loadAgentChatMessages();
let agentChatBusy = false;

function loadAgentChatMessages() {
  try {
    const raw = sessionStorage.getItem(AGENT_CHAT_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter(
        (message) =>
          message &&
          (message.role === 'user' ||
            message.role === 'assistant' ||
            message.role === 'proposal')
      )
      .map((message) => ({
        role: message.role,
        content: String(message.content || ''),
        fields: Array.isArray(message.fields) ? message.fields : undefined,
      }))
      .filter((message) => message.content || (message.fields && message.fields.length));
  } catch (err) {
    return [];
  }
}

function persistAgentChatMessages() {
  try {
    sessionStorage.setItem(AGENT_CHAT_STORAGE_KEY, JSON.stringify(agentChatMessages));
  } catch (err) {
    // Ignore quota / private-mode failures.
  }
}

function initializeComparisonPeriod() {
  if (window.ComparisonPeriod) {
    window.ComparisonPeriod.initializeComparisonPeriodSelect({
      formSelector: '.header-date-form',
    });
  }
}

function getReportingDate() {
  const referenceDateInput = document.getElementById('reference_date');
  return referenceDateInput ? referenceDateInput.value : '';
}

function getPreviousDate() {
  const previousDateInput = document.getElementById('previous_date');
  return previousDateInput ? previousDateInput.value : '';
}

function isDayComparisonActive() {
  if (!window.ComparisonPeriod || !window.ComparisonPeriod.isDayOverDayComparison) {
    return true;
  }
  return window.ComparisonPeriod.isDayOverDayComparison(
    getReportingDate(),
    getPreviousDate()
  );
}

function setDailyRecapActionsEnabled(enabled) {
  const generateBtn = document.getElementById('generateRecapBtn');
  const openChatBtn = document.getElementById('openChatBtn');
  if (generateBtn) {
    generateBtn.disabled = !enabled;
    generateBtn.title = enabled
      ? ''
      : 'Available for day comparisons only';
  }
  if (openChatBtn) {
    openChatBtn.disabled = !enabled;
    openChatBtn.title = enabled
      ? ''
      : 'Available for day comparisons only';
  }
}

function renderDailyRecapUnavailableForComparison() {
  const card = document.getElementById('dailyRecapCard');
  const titleEl = document.getElementById('dailyRecapTitle');
  const bodyEl = document.getElementById('dailyRecapBody');
  if (card) {
    card.classList.add('is-unavailable');
  }
  if (titleEl) {
    titleEl.textContent = 'Daily Market Recap';
  }
  if (bodyEl) {
    bodyEl.classList.remove('error');
    bodyEl.classList.add('unavailable');
    bodyEl.style.whiteSpace = 'normal';
    bodyEl.textContent =
      'The written daily recap covers a single session day. ' +
      'It is only available for day comparisons — choose Day under Comparison Date to view or generate it.';
  }
  setRecapExpanded(false);
  setDailyRecapActionsEnabled(false);
}

function getCsrfToken() {
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input && input.value) {
    return input.value;
  }
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function getCellClass(value) {
  if (value > 2.5) {
    return 'table-change-positive';
  } else if (value > 0) {
    return 'table-change-slightly-positive';
  } else if (value < -2.5) {
    return 'table-change-negative';
  } else if (value < 0) {
    return 'table-change-slightly-negative';
  }
  return '';
}

function renderFxMatrix() {
  if (!window.fxMatrix || !window.fxMatrixOrder) {
    return;
  }

  const container = document.getElementById('fxMatrixContainer');
  const header = document.getElementById('fxMatrixHeader');
  const body = document.getElementById('fxMatrixBody');

  if (!container || !header || !body) {
    return;
  }

  const headerRow = document.createElement('tr');
  const emptyHeader = document.createElement('th');
  headerRow.appendChild(emptyHeader);

  window.fxMatrixOrder.forEach(currency => {
    const th = document.createElement('th');
    th.textContent = currency;
    headerRow.appendChild(th);
  });
  header.appendChild(headerRow);

  const matrixMap = {};
  window.fxMatrix.forEach(row => {
    matrixMap[row.currency] = row;
  });

  window.fxMatrixOrder.forEach(baseCurrency => {
    const row = document.createElement('tr');
    const currencyHeader = document.createElement('th');
    currencyHeader.textContent = baseCurrency;
    row.appendChild(currencyHeader);

    window.fxMatrixOrder.forEach(quoteCurrency => {
      const cell = document.createElement('td');
      const value = baseCurrency === quoteCurrency ? 0 : (matrixMap[baseCurrency]?.[quoteCurrency] || 0);
      cell.textContent = value.toFixed(2);
      cell.className = getCellClass(value);
      row.appendChild(cell);
    });

    body.appendChild(row);
  });

  container.style.display = 'block';
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getRecapChangeClass(value, unit) {
  const normalized = String(unit || '').toLowerCase();
  const strong = normalized === 'bps' ? 5 : 2.5;
  if (value > strong) {
    return 'daily-recap-change-positive';
  }
  if (value > 0) {
    return 'daily-recap-change-slightly-positive';
  }
  if (value < -strong) {
    return 'daily-recap-change-negative';
  }
  if (value < 0) {
    return 'daily-recap-change-slightly-negative';
  }
  return '';
}

function colorizeChanges(html) {
  return html.replace(
    /\(([+-]?\d+(?:\.\d+)?)\s*(%|bps|pts)((?:\s+[^)]*)?)\)/gi,
    (match, number, unit, suffix) => {
      const value = Number(number);
      if (Number.isNaN(value)) {
        return match;
      }
      const className = getRecapChangeClass(value, unit);
      if (!className) {
        return match;
      }
      const colored = `<span class="daily-recap-change ${className}">${number}${unit}</span>`;
      return `(${colored}${suffix || ''})`;
    }
  );
}

function formatBulletLine(line) {
  const bullet = line.replace(/^[-*]\s+/, '');
  const bolded = bullet.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  const withLinks = bolded.replace(
    /\[(.+?)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  const subtitleMatch = withLinks.match(/^([^:<]{1,80}):\s*(.*)$/);
  if (subtitleMatch) {
    const subtitle = subtitleMatch[1].replace(/<\/?strong>/g, '');
    return `<li><strong>${subtitle}:</strong> ${subtitleMatch[2]}</li>`;
  }
  return `<li>${withLinks}</li>`;
}

function simpleMarkdownToHtml(markdown) {
  const escaped = escapeHtml(markdown || '');
  const lines = escaped.split('\n');
  const parts = [];
  let inList = false;

  const closeList = () => {
    if (inList) {
      parts.push('</ul>');
      inList = false;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (/^[-*]\s+/.test(trimmed)) {
      if (!inList) {
        parts.push('<ul>');
        inList = true;
      }
      parts.push(formatBulletLine(trimmed));
      return;
    }
    closeList();
    if (!trimmed) {
      return;
    }
    let html = trimmed
      .replace(/^### (.+)$/, '<h4>$1</h4>')
      .replace(/^## (.+)$/, '<h3>$1</h3>')
      .replace(/^# (.+)$/, '<h2>$1</h2>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(
        /\[(.+?)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
      );
    if (!/^<h[2-4]>/.test(html)) {
      html = `<p>${html}</p>`;
    }
    parts.push(html);
  });
  closeList();
  return colorizeChanges(parts.join(''));
}

function buildRecapSection(title, content) {
  if (!content || !String(content).trim()) {
    return '';
  }
  return (
    `<section class="daily-recap-section">` +
    `<h3 class="daily-recap-section-title">${escapeHtml(title)}</h3>` +
    `<div class="daily-recap-section-body">${simpleMarkdownToHtml(content)}</div>` +
    `</section>`
  );
}

function sourceLabelFromUrl(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    const label = host.split('.')[0] || 'Source';
    return label.charAt(0).toUpperCase() + label.slice(1);
  } catch (err) {
    return 'Source';
  }
}

function buildArticleSourcesSection(sourceUrls) {
  const urls = (Array.isArray(sourceUrls) ? sourceUrls : [])
    .map((item) => (typeof item === 'string' ? item : item && item.url))
    .filter(Boolean);
  if (!urls.length) {
    return '';
  }
  const items = urls
    .map((url) => {
      const name = escapeHtml(sourceLabelFromUrl(url));
      const href = escapeHtml(url);
      return (
        `<li><strong>${name}:</strong> ` +
        `<a href="${href}" target="_blank" rel="noopener noreferrer">${href}</a></li>`
      );
    })
    .join('');
  return (
    `<section class="daily-recap-section daily-recap-article-sources">` +
    `<h3 class="daily-recap-section-title">Article URL</h3>` +
    `<div class="daily-recap-section-body"><ul>${items}</ul></div>` +
    `</section>`
  );
}

function setRecapExpanded(expanded) {
  const card = document.getElementById('dailyRecapCard');
  const toggle = document.getElementById('dailyRecapToggle');
  if (!card || !toggle) {
    return;
  }
  card.classList.toggle('is-expanded', expanded);
  toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  const detailSections = card.querySelectorAll('.daily-recap-detail');
  detailSections.forEach((section) => {
    section.hidden = !expanded;
  });
}

function renderDailyRecap(data) {
  const card = document.getElementById('dailyRecapCard');
  const titleEl = document.getElementById('dailyRecapTitle');
  const bodyEl = document.getElementById('dailyRecapBody');
  if (!bodyEl) {
    return;
  }

  if (card) {
    card.classList.remove('is-unavailable');
  }
  bodyEl.classList.remove('error', 'unavailable');
  setDailyRecapActionsEnabled(true);
  if (titleEl) {
    titleEl.textContent = 'Daily Market Recap';
  }

  const headline = data.title
    ? `<p class="daily-recap-headline">${escapeHtml(data.title)}</p>`
    : '';
  const summarySection = buildRecapSection('Summary', data.main_summary || '');
  const articleSourcesSection = buildArticleSourcesSection(data.source_urls || []);
  const detailHtml =
    `<div class="daily-recap-detail" hidden>` +
    buildRecapSection('United States', data.us_summary || '') +
    buildRecapSection('Europe', data.eur_summary || '') +
    buildRecapSection('Japan', data.jp_summary || '') +
    buildRecapSection('Additional', data.additional_summary || '') +
    articleSourcesSection +
    `</div>`;

  bodyEl.innerHTML = headline + summarySection + detailHtml;
  setRecapExpanded(false);
}

function renderDailyRecapError(message) {
  const card = document.getElementById('dailyRecapCard');
  const titleEl = document.getElementById('dailyRecapTitle');
  const bodyEl = document.getElementById('dailyRecapBody');
  if (card) {
    card.classList.remove('is-unavailable');
  }
  if (titleEl) {
    titleEl.textContent = 'Daily Market Recap';
  }
  if (bodyEl) {
    bodyEl.classList.remove('unavailable');
    bodyEl.classList.add('error');
    bodyEl.textContent = message;
  }
  setRecapExpanded(false);
}

async function loadDailyRecap() {
  const bodyEl = document.getElementById('dailyRecapBody');
  if (!bodyEl) {
    return;
  }

  if (!isDayComparisonActive()) {
    renderDailyRecapUnavailableForComparison();
    return;
  }

  const card = document.getElementById('dailyRecapCard');
  if (card) {
    card.classList.remove('is-unavailable');
  }
  bodyEl.classList.remove('error', 'unavailable');
  setDailyRecapActionsEnabled(true);
  bodyEl.textContent = 'Loading daily recap…';

  const reportingDate = getReportingDate();
  const params = new URLSearchParams();
  if (reportingDate) {
    params.set('reporting_date', reportingDate);
  }

  try {
    const response = await fetch(`/analysis/recap?${params.toString()}`, {
      headers: { Accept: 'application/json' },
    });
    const data = await response.json();
    if (response.status === 404) {
      if (document.getElementById('dailyRecapTitle')) {
        document.getElementById('dailyRecapTitle').textContent = 'Daily Market Recap';
      }
      bodyEl.classList.remove('error');
      bodyEl.style.whiteSpace = 'pre-wrap';
      bodyEl.textContent =
        'No daily recap for this date yet.\nUse “Generate new recap” to create one.';
      return;
    }
    if (!response.ok) {
      throw new Error(data.message || data.error || `HTTP ${response.status}`);
    }
    renderDailyRecap(data);
  } catch (err) {
    renderDailyRecapError(`Could not load daily recap: ${err.message}`);
  }
}

function showLoadingModal(message) {
  const modal = document.getElementById('loading-modal-overlay');
  const textEl = document.getElementById('loading-modal-text');
  if (textEl && message) {
    textEl.textContent = message;
  }
  if (modal) {
    modal.classList.add('active');
  }
}

function hideLoadingModal() {
  const modal = document.getElementById('loading-modal-overlay');
  if (modal) {
    modal.classList.remove('active');
  }
}

function openGenerateRecapConfirm() {
  if (!isDayComparisonActive()) {
    renderDailyRecapUnavailableForComparison();
    return;
  }
  const reportingDate = getReportingDate();
  if (!reportingDate) {
    renderDailyRecapError('Select a Target Date before generating a recap.');
    return;
  }
  const messageEl = document.getElementById('generateRecapConfirmMessage');
  if (messageEl) {
    messageEl.textContent =
      `Generate a new daily market recap for ${reportingDate}? ` +
      'This can take a while and will overwrite any existing recap for that date.';
  }
  const modal = document.getElementById('generate-recap-confirm-overlay');
  if (modal) {
    modal.classList.add('active');
  }
}

function closeGenerateRecapConfirm() {
  const modal = document.getElementById('generate-recap-confirm-overlay');
  if (modal) {
    modal.classList.remove('active');
  }
}

async function generateDailyRecap() {
  const generateBtn = document.getElementById('generateRecapBtn');
  const bodyEl = document.getElementById('dailyRecapBody');
  const reportingDate = getReportingDate();
  if (!reportingDate) {
    renderDailyRecapError('Select a Target Date before generating a recap.');
    return;
  }

  closeGenerateRecapConfirm();
  if (generateBtn) {
    generateBtn.disabled = true;
  }
  if (bodyEl) {
    bodyEl.classList.remove('error');
    bodyEl.textContent = 'Generating daily recap (this can take a while)…';
  }
  showLoadingModal('Generating daily recap…');

  try {
    const response = await fetch('/analysis/recap/generate', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        reporting_date: reportingDate,
        force: true,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || data.error || `HTTP ${response.status}`);
    }
    if (data.status === 'skipped') {
      renderDailyRecapError(
        `Pipeline skipped: ${data.reason || 'unknown'}.\n` +
          JSON.stringify(data, null, 2)
      );
      return;
    }
    renderDailyRecap(data);
  } catch (err) {
    renderDailyRecapError(`Could not generate daily recap: ${err.message}`);
  } finally {
    hideLoadingModal();
    if (generateBtn) {
      generateBtn.disabled = false;
    }
  }
}

const PROPOSAL_FIELD_LABELS = {
  title: 'Title',
  main_summary: 'Summary',
  us_summary: 'Summary for US zone',
  eur_summary: 'Summary for EU zone',
  jp_summary: 'Summary for Japan zone',
  additional_summary: 'Additional summary',
};

function buildProposalFieldsFromResponse(data) {
  const candidates = [
    ['title', data.proposed_recap_title],
    ['main_summary', data.proposed_main_summary],
    ['us_summary', data.proposed_us_summary],
    ['eur_summary', data.proposed_eur_summary],
    ['jp_summary', data.proposed_jp_summary],
    ['additional_summary', data.proposed_additional_summary],
  ];
  return candidates
    .filter(([, value]) => typeof value === 'string' && value.trim())
    .map(([key, value]) => ({
      key,
      label: PROPOSAL_FIELD_LABELS[key] || key,
      value: value.trim(),
    }));
}

function formatProposalContent(fields) {
  return fields
    .map((field) => `Proposed ${field.label}:\n${field.value}`)
    .join('\n\n');
}

function appendProposalBubble(container, message) {
  const bubble = document.createElement('div');
  bubble.className = 'agent-chat-bubble proposal';

  const heading = document.createElement('div');
  heading.className = 'agent-chat-proposal-heading';
  heading.textContent = 'Suggested changes';
  bubble.appendChild(heading);

  const fields = Array.isArray(message.fields) && message.fields.length
    ? message.fields
    : null;

  if (fields) {
    fields.forEach((field) => {
      const block = document.createElement('div');
      block.className = 'agent-chat-proposal-field';

      const label = document.createElement('div');
      label.className = 'agent-chat-proposal-label';
      label.textContent = `Proposed ${field.label}`;
      block.appendChild(label);

      const body = document.createElement('div');
      body.className = 'agent-chat-proposal-body';
      body.textContent = field.value;
      block.appendChild(body);

      bubble.appendChild(block);
    });
  } else {
    const body = document.createElement('div');
    body.className = 'agent-chat-proposal-body';
    body.textContent = message.content || '';
    bubble.appendChild(body);
  }

  const note = document.createElement('div');
  note.className = 'agent-chat-proposal-footer';
  note.textContent = 'Not saved yet — approve or order to apply.';
  bubble.appendChild(note);

  container.appendChild(bubble);
}

function renderAgentChatMessages(options = {}) {
  const container = document.getElementById('agentChatMessages');
  if (!container) {
    return;
  }
  container.innerHTML = '';
  agentChatMessages.forEach((message) => {
    if (message.role === 'proposal') {
      appendProposalBubble(container, message);
      return;
    }
    const bubble = document.createElement('div');
    bubble.className = `agent-chat-bubble ${message.role}`;
    bubble.textContent = message.content;
    container.appendChild(bubble);
  });
  if (options.pending) {
    const pending = document.createElement('div');
    pending.className = 'agent-chat-bubble pending';
    pending.id = 'agentChatPending';
    pending.textContent = 'Agent is thinking…';
    container.appendChild(pending);
  }
  persistAgentChatMessages();
  container.scrollTop = container.scrollHeight;
}

function appendAgentChatNote(text) {
  const container = document.getElementById('agentChatMessages');
  if (!container || !text) {
    return;
  }
  const note = document.createElement('div');
  note.className = 'agent-chat-bubble system-note';
  note.textContent = text;
  container.appendChild(note);
  container.scrollTop = container.scrollHeight;
}

function openAgentChat() {
  if (!isDayComparisonActive()) {
    renderDailyRecapUnavailableForComparison();
    return;
  }
  const overlay = document.getElementById('agentChatOverlay');
  if (!overlay) {
    return;
  }
  const input = document.getElementById('agentChatInput');
  renderAgentChatMessages();
  overlay.classList.add('active');
  overlay.setAttribute('aria-hidden', 'false');
  if (input) {
    input.focus();
  }
}

function closeAgentChat() {
  if (agentChatBusy) {
    return;
  }
  const overlay = document.getElementById('agentChatOverlay');
  if (!overlay) {
    return;
  }
  overlay.classList.remove('active');
  overlay.setAttribute('aria-hidden', 'true');
}

function isAgentChatOpen() {
  const overlay = document.getElementById('agentChatOverlay');
  return Boolean(overlay && overlay.classList.contains('active'));
}

async function sendAgentChatMessage(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const input = document.getElementById('agentChatInput');
  const sendBtn = document.getElementById('agentChatSendBtn');
  const overlay = document.getElementById('agentChatOverlay');
  if (!input || agentChatBusy || (sendBtn && sendBtn.disabled)) {
    return;
  }
  const question = input.value.trim();
  if (!question) {
    return;
  }

  const priorMessages = agentChatMessages
    .filter((message) => message.role === 'user' || message.role === 'assistant')
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));

  agentChatBusy = true;
  agentChatMessages.push({ role: 'user', content: question });
  renderAgentChatMessages({ pending: true });
  if (overlay) {
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
  }
  input.value = '';
  if (sendBtn) {
    sendBtn.disabled = true;
  }
  input.disabled = true;

  try {
    const response = await fetch('/analysis/chat', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        question,
        messages: priorMessages,
      }),
    });

    let data = {};
    try {
      data = await response.json();
    } catch (parseErr) {
      throw new Error(`HTTP ${response.status}: invalid JSON response`);
    }

    if (!response.ok) {
      const detail =
        data.message ||
        data.error ||
        (data.error_message ? JSON.stringify(data.error_message) : null) ||
        `HTTP ${response.status}`;
      throw new Error(detail);
    }

    let answer = data.answer;
    if (!answer && Array.isArray(data.messages)) {
      const lastAssistant = [...data.messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.content);
      answer = lastAssistant ? lastAssistant.content : null;
    }
    agentChatMessages.push({
      role: 'assistant',
      content: answer || '(empty reply)',
    });

    const proposalFields = buildProposalFieldsFromResponse(data);
    if (proposalFields.length && !data.recap_updated) {
      agentChatMessages.push({
        role: 'proposal',
        content: formatProposalContent(proposalFields),
        fields: proposalFields,
      });
    }

    renderAgentChatMessages();

    if (data.recap_updated) {
      await loadDailyRecap();
      appendAgentChatNote('Daily recap was updated — reloaded on the page.');
    }

    if (data.cursor_guidelines_prompt) {
      appendAgentChatNote(
        'Suggested Cursor prompt to edit market-analysis.md:\n\n' +
          data.cursor_guidelines_prompt
      );
    }
  } catch (err) {
    agentChatMessages.push({
      role: 'assistant',
      content: `Chat failed: ${err.message}`,
    });
    renderAgentChatMessages();
  } finally {
    agentChatBusy = false;
    if (overlay) {
      overlay.classList.add('active');
      overlay.setAttribute('aria-hidden', 'false');
    }
    if (sendBtn) {
      sendBtn.disabled = false;
    }
    input.disabled = false;
    input.focus();
  }
}

function initializeDailyRecapControls() {
  const generateBtn = document.getElementById('generateRecapBtn');
  const openChatBtn = document.getElementById('openChatBtn');
  const closeChatBtn = document.getElementById('agentChatClose');
  const sendBtn = document.getElementById('agentChatSendBtn');
  const chatOverlay = document.getElementById('agentChatOverlay');
  const chatInput = document.getElementById('agentChatInput');
  const confirmOk = document.getElementById('generateRecapConfirmOk');
  const confirmCancel = document.getElementById('generateRecapConfirmCancel');
  const confirmClose = document.getElementById('generateRecapConfirmClose');
  const confirmOverlay = document.getElementById('generate-recap-confirm-overlay');

  if (generateBtn) {
    generateBtn.addEventListener('click', openGenerateRecapConfirm);
  }
  if (confirmOk) {
    confirmOk.addEventListener('click', generateDailyRecap);
  }
  if (confirmCancel) {
    confirmCancel.addEventListener('click', closeGenerateRecapConfirm);
  }
  if (confirmClose) {
    confirmClose.addEventListener('click', closeGenerateRecapConfirm);
  }
  if (confirmOverlay) {
    confirmOverlay.addEventListener('click', (event) => {
      if (event.target === confirmOverlay) {
        closeGenerateRecapConfirm();
      }
    });
  }
  if (openChatBtn) {
    openChatBtn.addEventListener('click', openAgentChat);
  }
  const dailyRecapCard = document.getElementById('dailyRecapCard');
  if (dailyRecapCard) {
    dailyRecapCard.addEventListener('click', (event) => {
      if (dailyRecapCard.classList.contains('is-unavailable')) {
        return;
      }
      if (event.target.closest('.daily-recap-actions')) {
        return;
      }
      if (event.target.closest('a[href]')) {
        return;
      }
      const expanded = dailyRecapCard.classList.contains('is-expanded');
      setRecapExpanded(!expanded);
    });
  }
  if (closeChatBtn) {
    closeChatBtn.addEventListener('click', closeAgentChat);
  }
  if (chatOverlay) {
    chatOverlay.addEventListener('click', (event) => {
      if (event.target === chatOverlay && !agentChatBusy) {
        closeAgentChat();
      }
    });
    const chatCard = chatOverlay.querySelector('.agent-chat-card');
    if (chatCard) {
      chatCard.addEventListener('click', (event) => {
        event.stopPropagation();
      });
    }
  }
  if (sendBtn) {
    sendBtn.addEventListener('click', sendAgentChatMessage);
  }
  if (chatInput) {
    chatInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendAgentChatMessage(event);
      }
    });
  }
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') {
      return;
    }
    if (isAgentChatOpen()) {
      closeAgentChat();
      return;
    }
    closeGenerateRecapConfirm();
  });

  loadDailyRecap();
}

initializeComparisonPeriod();
initializeDailyRecapControls();
renderFxMatrix();
