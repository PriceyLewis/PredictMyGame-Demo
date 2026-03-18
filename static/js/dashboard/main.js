// Update Summary (2025-02-11): Hooked upgrade buttons into routing and initialised enhanced live sync.
import { getBootData } from './context.js';
import initCharts from './charts.js';
import initPlanner from './planner.js';
import initAssistant from './assistant.js';
import initInsights from './insights.js';
import initGoals from './goals.js';
import initLive from './live.js';

window.addEventListener('error', (event) => {
  console.error('Global JS error:', event.message, event.error);
  window.showToast?.('Something went wrong. Please refresh.', 'error');
});
window.addEventListener('unhandledrejection', (event) => {
  console.error('Global JS promise rejection:', event.reason);
  window.showToast?.('Something went wrong. Please refresh.', 'error');
});

function ready(fn) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fn);
  } else {
    fn();
  }
}

function applyPremiumLocks(boot) {
  if (boot.isPremium) return;
  const cards = document.querySelectorAll('[data-premium-lock]');
  cards.forEach((card) => {
    if (card.dataset.premiumApplied) return;
    if (card.classList.contains('premium-locked')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'premium-locked-wrapper';
    const overlay = document.createElement('div');
    overlay.className = 'premium-overlay';
    overlay.innerHTML = '<p>Premium feature</p><a class="btn" href="/upgrade/">Upgrade to Premium</a>';
    const parent = card.parentNode;
    if (!parent) return;
    parent.insertBefore(wrapper, card);
    wrapper.appendChild(card);
    card.classList.add('premium-locked');
    card.dataset.premiumApplied = 'true';
    wrapper.appendChild(overlay);
  });
}


ready(() => {
  const boot = getBootData();
  const initAOS = () => {
    if (window.AOS && typeof window.AOS.init === 'function') {
      window.AOS.init({ duration: 700 });
      document.body.classList.add('aos-ready');
    }
  };
  const aosTargets = document.querySelectorAll('[data-aos]');
  if (aosTargets.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          initAOS();
          obs.disconnect();
        }
      },
      { rootMargin: '0px 0px 120px 0px', threshold: 0.1 },
    );
    aosTargets.forEach((el) => observer.observe(el));
  } else {
    initAOS();
  }
  const navBar = document.querySelector('.nav-bar');
  const navToggle = document.getElementById('dashboardNavToggle');
  const closeNavBar = () => {
    if (!navBar) return;
    navBar.classList.remove('is-open');
    navToggle?.setAttribute('aria-expanded', 'false');
  };
  const toggleNavBar = () => {
    if (!navBar || !navToggle) return;
    const isOpen = navBar.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  };
  if (navBar && navToggle) {
    navToggle.addEventListener('click', (event) => {
      event.preventDefault();
      toggleNavBar();
    });
    document.addEventListener('click', (event) => {
      if (!navBar.classList.contains('is-open')) return;
      if (navBar.contains(event.target) || navToggle.contains(event.target)) {
        if (navBar.contains(event.target) && event.target.matches('a')) {
          closeNavBar();
        }
        return;
      }
      closeNavBar();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 1024) {
        closeNavBar();
      }
    });
  }

  const compactToggle = document.getElementById('compactModeToggle');
  const pageShell = document.querySelector('.page');
  const compactLabel = compactToggle ? compactToggle.querySelector('span') : null;
  const COMPACT_MODE_KEY = 'dashboardCompactMode';
  const setCompact = (state) => {
    if (!pageShell || !compactToggle) return;
    const next = state ? '1' : '0';
    pageShell.dataset.compact = next;
    compactToggle.setAttribute('aria-pressed', state ? 'true' : 'false');
    if (compactLabel) {
      compactLabel.textContent = state ? 'Compact on' : 'Compact mode';
    }
    try {
      window.localStorage.setItem(COMPACT_MODE_KEY, next);
    } catch (error) {
      console.warn('PredictMyGrade: unable to persist compact mode', error);
    }
  };
  if (compactToggle) {
    let initialCompact = false;
    try {
      initialCompact = window.localStorage.getItem(COMPACT_MODE_KEY) === '1';
    } catch (error) {
      console.warn('PredictMyGrade: compact mode preference locked', error);
    }
    setCompact(initialCompact);
    compactToggle.addEventListener('click', () => {
      const next = pageShell?.dataset.compact !== '1';
      setCompact(next);
    });
  }

  let assistantInstance = null;
  const ensureAssistant = () => {
    if (!assistantInstance) {
      assistantInstance = initAssistant(boot);
    }
    return assistantInstance;
  };
  const assistantProxy = {
    updateLive: (data) => ensureAssistant()?.updateLive?.(data),
    refreshTip: (force) => ensureAssistant()?.refreshTip?.(force),
  };
  const insights = initInsights(boot);
  const goals = initGoals(boot);
  let chartsInitialized = false;
  const startCharts = () => {
    if (chartsInitialized) return;
    chartsInitialized = true;
    initCharts(boot);
  };
  const chartTargets = document.querySelectorAll(
    '.chart-shell canvas, #forecastChart, #confidenceTrend, #performanceChart',
  );
  if (chartTargets.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          startCharts();
          obs.disconnect();
        }
      },
      { rootMargin: '0px 0px 200px 0px', threshold: 0.1 },
    );
    chartTargets.forEach((canvas) => observer.observe(canvas));
  } else {
    startCharts();
  }
  initPlanner(boot);
  initLive(boot, { assistant: assistantProxy, insights, goals });
  const aiSection = document.getElementById('ai');
  const openAssistantBtn = document.getElementById('openAssistantBtn');
  if (openAssistantBtn) {
    openAssistantBtn.addEventListener('click', () => {
      ensureAssistant();
    });
  }
  if (aiSection && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          ensureAssistant();
          obs.disconnect();
        }
      },
      { rootMargin: '0px 0px 200px 0px', threshold: 0.1 },
    );
    observer.observe(aiSection);
  }
  document.querySelectorAll('[data-upgrade-url]').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      const target = btn.dataset.upgradeUrl || '/upgrade/';
      window.location.href = target;
    });
  });
  const calendarCopyBtn = document.getElementById('plannerCopyLink');
  const calendarGoogleBtn = document.getElementById('plannerGoogleSync');
  const calendarDownloadLink = document.getElementById('plannerIcsDownload');
  const resolveCalendarUrl = (element) => {
    const raw =
      element?.dataset?.calendarUrl || calendarDownloadLink?.dataset?.calendarUrl || '';
    if (!raw) return '';
    if (/^(https?|webcal):/i.test(raw)) {
      return raw;
    }
    try {
      const origin = window.location?.origin || '';
      if (origin) {
        return new URL(raw, origin).toString();
      }
    } catch (error) {
      console.warn('PredictMyGrade: unable to normalise calendar URL', error);
    }
    return raw;
  };

  if (calendarCopyBtn) {
    calendarCopyBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      const url = resolveCalendarUrl(calendarCopyBtn);
      if (!url) return;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(url);
        } else {
          const tempInput = document.createElement('input');
          tempInput.value = url;
          document.body.appendChild(tempInput);
          tempInput.select();
          document.execCommand('copy');
          document.body.removeChild(tempInput);
        }
        if (window.showToast) {
          window.showToast('Calendar link copied to clipboard.', 'success');
        }
      } catch (error) {
        console.warn('PredictMyGrade: calendar link copy failed', error);
        if (window.showToast) {
          window.showToast('Unable to copy link. Copy it manually instead.', 'error');
        }
      }
    });
  }

  if (calendarGoogleBtn) {
    calendarGoogleBtn.addEventListener('click', (event) => {
      event.preventDefault();
      const href = calendarGoogleBtn.getAttribute('href') || resolveCalendarUrl(calendarGoogleBtn);
      if (!href) return;
      window.open(href, '_blank', 'noopener');
    });
  }

  const COLLAPSE_KEY_PREFIX = 'dashboardCollapse:';
  document.querySelectorAll('.collapsible-toggle').forEach((toggle) => {
    const targetId = toggle.dataset.collapseTarget;
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;
    const showLabel = toggle.dataset.collapseShowLabel || 'Show section';
    const hideLabel = toggle.dataset.collapseHideLabel || 'Hide section';
    const storageKey = `${COLLAPSE_KEY_PREFIX}${targetId}`;
    const applyState = (open, persist = true) => {
      target.hidden = !open;
      toggle.textContent = open ? hideLabel : showLabel;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (persist) {
        try {
          window.localStorage.setItem(storageKey, open ? 'open' : 'closed');
        } catch (error) {
          console.warn('PredictMyGrade: unable to persist collapse state', error);
        }
      }
    };
    let initialOpen = !target.hasAttribute('hidden');
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored === 'open') initialOpen = true;
      if (stored === 'closed') initialOpen = false;
    } catch (error) {
      console.warn('PredictMyGrade: collapse preference locked', error);
    }
    applyState(initialOpen, false);
    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      applyState(target.hidden, true);
    });
  });
  applyPremiumLocks(boot);
});
