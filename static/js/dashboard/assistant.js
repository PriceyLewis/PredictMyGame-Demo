// Update Summary (2025-02-11): Wired assistant to new JSON endpoint, added multi-trigger support,
// premium gating toasts, and live loading indicators.
import {
  requestJSON,
  startProgress,
  endProgress,
  toggleButtonLoading,
  getCSRFToken,
  emit,
} from './helpers.js';

const TIP_STORAGE_KEY = 'predictmygrade-assistant-tip';
const ROLE_LABELS = {
  user: 'You',
  assistant: 'PredictMyGrade',
  system: 'System',
};
const DEFAULT_MENTOR_TIP = 'Keep reviewing your weaker modules; consistency is key!';
const FALLBACK_MENTOR_TIP = 'Keep pushing - your consistency is what drives improvement!';

export default function initAssistant(boot) {
  const panel = document.getElementById('aiAssistantPanel');
  if (!panel) {
    return { updateLive: () => {}, refreshTip: () => {} };
  }
  const isModalPanel = panel.dataset.modal !== 'false';

  const primaryOpenBtn = document.getElementById('openAssistantBtn');
  const openTriggers = new Set();
  if (primaryOpenBtn) {
    openTriggers.add(primaryOpenBtn);
  }
  document.querySelectorAll('[data-assistant-trigger]').forEach((btn) => {
    if (btn) openTriggers.add(btn);
  });
  let lastAssistantTrigger = null;
  const closeBtn = document.getElementById('closeAssistant');
  const messageBox = document.getElementById('assistantMessage');
  const aiTutorNode = document.getElementById('aiTutor');
  const chatLog = document.getElementById('assistantChatLog');
  const input = document.getElementById('assistantInput');
  const sendBtn = document.getElementById('assistantSend');
  const refreshButtons = Array.from(document.querySelectorAll('[data-mentor-refresh]'));
  const voiceBtn = document.getElementById('voiceMentorBtn');
  const speakBtn = document.getElementById('assistantSpeak');
  const personaSelect = document.getElementById('assistantPersona');
  const personaDescription = document.getElementById('assistantPersonaDescription');
  const previewBanner = document.getElementById('assistantPreviewBanner');
  const resetBtn = document.getElementById('assistantReset');
  const form = document.getElementById('assistantForm');
  const focusableSelectors =
    'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const urls = boot.urls || {};
  const assistantEndpoint = urls.assistantChat || urls.forecastChat || '';
  const bootAI = boot.ai || {};
  const freePreview = Boolean(bootAI.freePreview);
  const allowPersonas = bootAI.allowPersonas !== false;
  const previewLimit = Number(bootAI.previewLimit || 0);
  const upgradeHint = bootAI.upgradeHint || '';

  let personas = Array.isArray(bootAI.personas) ? bootAI.personas : [];
  let currentPersona = bootAI.persona || 'mentor';
  let chatHistory = [];
  let focusTrapActive = false;
  const focusTrapHandler = (event) => {
    if (!focusTrapActive || !panel?.classList.contains('open')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeAssistantPanel();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(panel.querySelectorAll(focusableSelectors)).filter(
      (node) => node.offsetParent !== null && node.tabIndex !== -1,
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (!panel.contains(active)) {
      event.preventDefault();
      first.focus();
      return;
    }
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const isOpen = panel.classList.contains('open');
  focusTrapActive = isOpen && isModalPanel;
  panel.setAttribute('tabindex', '-1');
  panel.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
  if (isModalPanel) {
    panel.setAttribute('aria-modal', isOpen ? 'true' : 'false');
  } else {
    panel.removeAttribute('aria-modal');
  }
  document.addEventListener('keydown', focusTrapHandler, true);

  if (previewBanner) {
    if (freePreview) {
      previewBanner.hidden = false;
      previewBanner.textContent =
        upgradeHint ||
        (previewLimit
          ? `Enjoy ${previewLimit} mentor replies per day on the free plan. Upgrade to unlock unlimited chat and persona switching.`
          : 'Enjoy mentor previews on the free plan. Upgrade to unlock unlimited chat and persona switching.');
    } else {
      previewBanner.hidden = true;
    }
  }

  if (!allowPersonas && personaSelect) {
    personaSelect.disabled = true;
    personaSelect.setAttribute('aria-disabled', 'true');
    personaSelect.classList.add('is-disabled');
  }

  if (chatLog) {
    chatLog.setAttribute('role', 'log');
    chatLog.setAttribute('aria-live', 'polite');
    chatLog.setAttribute('aria-label', 'AI mentor conversation');
  }
  if (messageBox) {
    messageBox.setAttribute('aria-live', 'polite');
  }

  function updatePersonaDescription(personaId) {
    currentPersona = personaId || currentPersona;
    if (!personaDescription) return;
    const meta = personas.find((item) => item.id === currentPersona);
    personaDescription.textContent = meta?.description || '';
  }

  function setPersonaOptions(options, selectedId) {
    if (!Array.isArray(options)) return;
    personas = options;
    if (!personaSelect) {
      if (selectedId) {
        currentPersona = selectedId;
      }
      updatePersonaDescription(currentPersona);
      return;
    }
    personaSelect.innerHTML = '';
    options.forEach((option) => {
      const node = document.createElement('option');
      node.value = option.id;
      node.textContent = option.label;
      personaSelect.appendChild(node);
    });
    const hasSelected = options.some((opt) => opt.id === selectedId);
    const fallback = options.length ? options[0].id : currentPersona;
    const target = hasSelected ? selectedId : fallback;
    if (target) {
      personaSelect.value = target;
      currentPersona = target;
    }
    updatePersonaDescription(currentPersona);
    if (!allowPersonas) {
      personaSelect.disabled = true;
      personaSelect.setAttribute('aria-disabled', 'true');
    }
  }

  function syncHistory(rawHistory) {
    if (!Array.isArray(rawHistory)) return;
    chatHistory = rawHistory.map((entry) => ({
      role: entry.role || 'assistant',
      text: entry.content || '',
      ts: entry.timestamp || Date.now(),
    }));
    if (!chatLog) return;
    chatLog.innerHTML = '';
    chatHistory.forEach((entry) => {
      appendChatMessage(entry.role, entry.text, { persist: false });
    });
  }

  function loadSavedTip() {
    try {
      return localStorage.getItem(TIP_STORAGE_KEY) || '';
    } catch (error) {
      console.warn('PredictMyGrade: failed to load assistant tip', error);
      return '';
    }
  }

  function persistTip(text) {
    try {
      localStorage.setItem(TIP_STORAGE_KEY, text);
    } catch (error) {
      console.warn('PredictMyGrade: failed to persist assistant tip', error);
    }
  }

  function updateMessage(text) {
    if (!text) return;
    if (messageBox) {
      messageBox.textContent = text;
    }
    if (aiTutorNode) {
      aiTutorNode.textContent = text;
    }
    persistTip(text);
  }

  function appendChatMessage(role, text, { persist = true } = {}) {
    if (!chatLog || !text) return;
    const wrap = document.createElement('div');
    wrap.className = 'assistant-chat-line';
    const label = document.createElement('strong');
    label.textContent = `${ROLE_LABELS[role] || role}: `;
    wrap.appendChild(label);
    wrap.append(document.createTextNode(text));
    chatLog.appendChild(wrap);
    chatLog.scrollTop = chatLog.scrollHeight;
    if (persist) {
      chatHistory.push({ role, text, ts: Date.now() });
    }
  }

function handleStateResponse(data) {
  if (!data || typeof data !== 'object') return;
  if (previewBanner) {
    if (typeof data.free_preview === 'boolean') {
      previewBanner.hidden = !data.free_preview;
    }
    if (typeof data.upgrade_hint === 'string' && data.upgrade_hint) {
      previewBanner.textContent = data.upgrade_hint;
    }
  }
  if (Array.isArray(data.personas)) {
    setPersonaOptions(data.personas, data.persona || currentPersona);
  } else if (typeof data.persona === 'string') {
    currentPersona = data.persona;
    if (personaSelect) {
        personaSelect.value = currentPersona;
      }
      updatePersonaDescription(currentPersona);
    }
    if (Array.isArray(data.history)) {
      syncHistory(data.history);
    }
    if (typeof data.tip === 'string') {
      updateMessage(data.tip);
    }
  if (boot.ai) {
    if (typeof data.persona === 'string') {
      boot.ai.persona = data.persona;
    }
    if (Array.isArray(data.history)) {
      boot.ai.history = data.history;
    }
    if (typeof data.upgrade_hint === 'string') {
      boot.ai.upgradeHint = data.upgrade_hint;
    }
    if (typeof data.free_preview === 'boolean') {
      boot.ai.freePreview = data.free_preview;
    }
  }
}

  async function loadAssistantState({ showLoader = false } = {}) {
    if (!urls.forecastState) return;
    if (showLoader) startProgress();
    try {
      const resp = await fetch(urls.forecastState);
      const data = await resp.json().catch(() => ({}));
      if (resp.ok) {
        handleStateResponse(data);
      }
    } catch (error) {
      console.warn('PredictMyGrade: failed to load assistant state', error);
    } finally {
      if (showLoader) endProgress();
    }
  }

  async function postAssistantState(params, { successMessage } = {}) {
    if (!urls.forecastState) return { ok: false, data: null };
    try {
      const resp = await fetch(urls.forecastState, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params,
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok) {
        handleStateResponse(data);
        if (successMessage && window.showToast) {
          window.showToast(successMessage, 'success');
        }
      } else if (window.showToast) {
        const msg = data?.error || 'AI mentor update failed.';
        window.showToast(msg, 'error');
      }
      return { ok: resp.ok, data };
    } catch (error) {
      console.warn('PredictMyGrade: assistant state update failed', error);
      if (window.showToast) {
        window.showToast('AI mentor update failed.', 'error');
      }
      return { ok: false, data: null };
    }
  }

  async function fetchMentorTip(showToast = false, sourceButton) {
    if (!urls.mentorTip) return;
    const targets = sourceButton ? [sourceButton] : refreshButtons;
    targets.forEach((btn) => toggleButtonLoading(btn, true, 'Refreshing...'));
    startProgress();
    try {
      const data = await requestJSON(urls.mentorTip);
      const tip = data.ai_tip?.trim() || DEFAULT_MENTOR_TIP;
      updateMessage(tip);
      if (data.plan_item) {
        emit('assistantPlanCreated', { plan_items: [data.plan_item] });
      }
      if (data.limit_note && window.showToast) {
        window.showToast(data.limit_note, 'info');
      }
      if (showToast && window.showToast) {
        window.showToast('Mentor tip updated', 'success');
      }
    } catch (error) {
      console.warn('PredictMyGrade: failed to refresh mentor tip', error);
      updateMessage(FALLBACK_MENTOR_TIP);
      if (window.showToast) {
        window.showToast('Unable to refresh mentor tip.', 'error');
      }
    } finally {
      targets.forEach((btn) => toggleButtonLoading(btn, false, 'Refresh Tip'));
      endProgress();
    }
  }

  async function sendMessage() {
    if (!assistantEndpoint || !input || !sendBtn) return;
    const text = input.value.trim();
    if (!text) return;

    const persona = personaSelect?.value || currentPersona;
    appendChatMessage('user', text);
    input.value = '';

    toggleButtonLoading(sendBtn, true, 'Sending...');
    input.disabled = true;
    sendBtn.disabled = true;
    panel?.classList.add('busy');
    startProgress();
    try {
      const payload = { message: text };
      if (persona) {
        payload.persona = persona;
      }
      const resp = await fetch(assistantEndpoint, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) {
        if (data.requires_upgrade && window.showToast) {
          window.showToast(
            data.upgrade_hint || upgradeHint || 'Upgrade to Premium to unlock the AI assistant.',
            'info',
          );
        }
        const message =
          (data && (data.error || data.answer)) ||
          'AI mentor chat is currently unavailable.';
        appendChatMessage('assistant', message);
        return;
      }
      handleStateResponse(data);
      if (data.requires_upgrade && window.showToast) {
        const hint = data.upgrade_hint || upgradeHint;
        if (hint) {
          window.showToast(hint, 'info');
        }
      }
      if (!Array.isArray(data.history) && typeof data.answer === 'string') {
        appendChatMessage('assistant', data.answer || 'Let me think about that...');
      }
      if (data.limit_note && window.showToast) {
        window.showToast(data.limit_note, 'info');
      }
    } catch (error) {
      console.warn('PredictMyGrade: assistant chat failed', error);
      appendChatMessage('assistant', 'Sorry, I could not process that.');
    } finally {
      toggleButtonLoading(sendBtn, false, 'Send');
      input.disabled = false;
      sendBtn.disabled = false;
      panel?.classList.remove('busy');
      endProgress();
    }
  }

  const initialTip = loadSavedTip() || bootAI.tip;
  if (messageBox && initialTip) {
    updateMessage(initialTip);
  }

  if (Array.isArray(bootAI.history) && bootAI.history.length) {
    syncHistory(bootAI.history);
  }
  setPersonaOptions(personas, currentPersona);
  if (allowPersonas) {
    loadAssistantState();
  }

  function openAssistantPanel(trigger) {
    if (!panel) return;
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    panel.setAttribute('aria-modal', 'true');
    focusTrapActive = isModalPanel;
    if (trigger?.setAttribute) {
      trigger.setAttribute('aria-expanded', 'true');
    }
    if (primaryOpenBtn && trigger === primaryOpenBtn) {
      primaryOpenBtn.style.display = 'none';
    }
    lastAssistantTrigger = trigger || primaryOpenBtn || null;
    window.requestAnimationFrame(() => {
      if (input) {
        input.focus();
      } else {
        panel.focus();
      }
    });
  }

  function closeAssistantPanel() {
    if (!panel) return;
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    panel.setAttribute('aria-modal', 'false');
    focusTrapActive = false;
    if (primaryOpenBtn) {
      primaryOpenBtn.setAttribute('aria-expanded', 'false');
      if (primaryOpenBtn.style.display === 'none') {
        primaryOpenBtn.style.display = '';
      }
    }
    if (lastAssistantTrigger && lastAssistantTrigger !== primaryOpenBtn) {
      lastAssistantTrigger.focus?.();
    } else if (primaryOpenBtn) {
      primaryOpenBtn.focus();
    }
    lastAssistantTrigger = null;
  }

  openTriggers.forEach((btn) => {
    btn?.addEventListener('click', (event) => {
      event?.preventDefault?.();
      openAssistantPanel(btn);
    });
  });

  closeBtn?.addEventListener('click', (event) => {
    event?.preventDefault?.();
    closeAssistantPanel();
  });

  personaSelect?.addEventListener('change', async (event) => {
    if (!allowPersonas) {
      event.preventDefault();
      return;
    }
    const value = event.target.value;
    const params = new URLSearchParams();
    params.set('persona', value);
    params.set('reset', '1');
    personaSelect.disabled = true;
    startProgress();
    try {
      const label =
        personas.find((item) => item.id === value)?.label || 'New persona';
      await postAssistantState(params, { successMessage: `${label} persona activated` });
    } finally {
      personaSelect.disabled = false;
      endProgress();
    }
  });

  resetBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (!urls.forecastState) return;
    const params = new URLSearchParams();
    params.set('persona', personaSelect?.value || currentPersona);
    params.set('reset', '1');
    toggleButtonLoading(resetBtn, true, 'Resetting...');
    startProgress();
    try {
      await postAssistantState(params, { successMessage: 'Conversation reset' });
    } finally {
      toggleButtonLoading(resetBtn, false, 'Reset Chat');
      endProgress();
    }
  });

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage();
  });

  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  refreshButtons.forEach((btn) =>
    btn?.addEventListener('click', (event) => {
      event.preventDefault();
      toggleButtonLoading(btn, true, 'Refreshing...');
      fetchMentorTip(true, btn);
    }),
  );

  voiceBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (!urls.voiceMentor) return;
    toggleButtonLoading(voiceBtn, true, 'Playing...');
    try {
      const data = await requestJSON(urls.voiceMentor);
      updateMessage(data.msg || 'Keep studying hard!');
      if (data.limit_note && window.showToast) {
        window.showToast(data.limit_note, 'info');
      }
      if ('speechSynthesis' in window && data.msg) {
        const utterance = new SpeechSynthesisUtterance(data.msg);
        utterance.lang = 'en-GB';
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      }
    } catch (error) {
      console.warn('PredictMyGrade: voice mentor failed', error);
      if (window.showToast) {
        window.showToast('Voice mentor unavailable.', 'error');
      }
    } finally {
      toggleButtonLoading(voiceBtn, false, 'Hear AI Mentor');
    }
  });

  speakBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    if (!('speechSynthesis' in window) || !messageBox?.textContent) return;
    const utterance = new SpeechSynthesisUtterance(messageBox.textContent);
    utterance.lang = 'en-GB';
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });

  document.addEventListener('snapshotTaken', () => fetchMentorTip());

  return {
    updateLive(data) {
      if (!data) return;
      const lines = [];
      if (typeof data.avg === 'number') {
        lines.push(`Current average: ${data.avg}%`);
      }
      if (typeof data.progress === 'number') {
        lines.push(`Progress to next target: ${data.progress}%`);
      }
      if (lines.length && messageBox && !panel.classList.contains('open')) {
        updateMessage(lines.join(' - '));
      }
    },
    refreshTip: fetchMentorTip,
  };
}
