// Update Summary (2025-02-11): Added data import/export hooks, timeline auto-sync, and navbar indicators.
import {
  requestJSON,
  postJSON,
  startProgress,
  endProgress,
  toggleButtonLoading,
  emit,
  getCSRFToken,
  glowElement,
  formatPercent,
} from './helpers.js';

import { getChart, refreshWeeklyGoalsChart, refreshHabitChart } from './charts.js';

export default function initLive(boot, { assistant, insights, goals } = {}) {

  const urls = boot.urls || {};
  const paletteCommands = Array.isArray(boot.commands) ? boot.commands : [];
  const AI_MOOD_CIRCUMFERENCE = 2 * Math.PI * 45;

  const assistantModule = assistant || { updateLive: () => {} };
  const insightsModule = insights || { updateLive: () => {} };
  const goalsModule = goals || { updateLive: () => {} };

  const weeklyCalendar = document.getElementById('weeklyCalendar');

  const calendarHint = document.getElementById('weeklyCalendarHint');

  const comparisonList = document.getElementById('snapshotComparisonList');
  const forecastFreshness = document.getElementById('forecastRefreshed');
  const aiMoodRing = document.getElementById('aiMoodProgress');
  const aiMoodLabel = document.getElementById('aiMoodLabel');
  const aiMoodText = document.getElementById('aiMoodText');

  const commandInput = document.getElementById('commandPaletteInput');

  const commandRunBtn = document.getElementById('commandPaletteRun');
  const refreshComparisonBtn = document.getElementById('refreshComparisonBtn');
  const syncBtn = document.getElementById('syncNowBtn');
  const timelineRefreshBtn = document.getElementById('timelineRefreshBtn');
  const timelineStream = document.getElementById('timelineStream');
  const timelineEmptyState = document.getElementById('timelineEmptyState');
  const lastSyncLabel = document.getElementById('lastSyncLabel');
  const plannerGrid = document.getElementById('dashboardPlannerGrid');
  const plannerViewToggle = document.getElementById('plannerViewToggle');
  const plannerViewStateKey = 'dashboardPlannerView';
  const plannerViewCompactClass = 'dashboard-view-compact';

  if (plannerGrid && plannerViewToggle) {
    const applyPlannerView = (view) => {
      const compact = view === 'compact';
      plannerGrid.dataset.view = view;
      document.body.classList.toggle(plannerViewCompactClass, compact);
      plannerViewToggle.setAttribute('aria-pressed', compact ? 'true' : 'false');
      const icon = plannerViewToggle.querySelector('i');
      const label = plannerViewToggle.querySelector('span');
      if (icon) {
        icon.classList.toggle('fa-expand-alt', compact);
        icon.classList.toggle('fa-compress-alt', !compact);
      }
      if (label) {
        label.textContent = compact ? 'Show expanded view' : 'Show compact view';
      }
    };

    let initialView = 'expanded';
    try {
      const stored = window.localStorage.getItem(plannerViewStateKey);
      if (stored) {
        initialView = stored === 'compact' ? 'compact' : 'expanded';
      }
    } catch (error) {
      console.warn('PredictMyGrade: planner view preference locked', error);
    }
    applyPlannerView(initialView);
    plannerViewToggle.addEventListener('click', () => {
      const nextView = plannerGrid.dataset.view === 'compact' ? 'expanded' : 'compact';
      applyPlannerView(nextView);
      try {
        window.localStorage.setItem(plannerViewStateKey, nextView);
      } catch (error) {
        console.warn('PredictMyGrade: unable to persist planner view preference', error);
      }
    });
  }

  if (Array.isArray(boot.comparison)) {
    renderComparison(boot.comparison);
  }
  if (Array.isArray(boot.calendar)) {
    renderWeeklyCalendar(boot.calendar);
  }
  if (Array.isArray(boot.timelineEvents)) {
    updateTimelineEvents(boot.timelineEvents);
  }
  setLastSyncLabel();
  updateMoodIndicator(boot.ai?.confidence, boot.band);

  if (urls.liveData) {
    setTimeout(() => refreshLiveData(true), 1500);
    setInterval(() => refreshLiveData(false), 60000);
  }

  if (urls.sync) {
    setTimeout(() => lightweightSync(false), 30000);
    setInterval(() => lightweightSync(false), 60000);
  }



  const exportBtn = document.getElementById('exportDataBtn');
  const importInput = document.getElementById('importDataInput');
  const importWrapper = importInput?.closest('label');
  let _liveUpdateTimer;
  let _dashboardUpdateTimer;
  let deadlineDecorationTimer;

  exportBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    const url = exportBtn?.dataset?.exportUrl || urls.exportData;
    if (!url) {
      if (window.showToast) {
        window.showToast('Data export endpoint is unavailable.', 'error');
      }
      return;
    }
    toggleButtonLoading(exportBtn, true, 'Preparing...');
    try {
      const response = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      const stamp = new Date().toISOString().slice(0, 10);
      link.download = `predictmygrade-data-${stamp}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
      if (window.showToast) {
        window.showToast('Data exported as CSV.', 'success');
      }
    } catch (error) {
      console.warn('PredictMyGrade: data export failed', error);
      if (window.showToast) {
        window.showToast('Unable to export data right now.', 'error');
      }
    } finally {
      toggleButtonLoading(exportBtn, false, 'Export My Data');
    }
  });

  importInput?.addEventListener('change', async () => {
    const file = importInput.files?.[0];
    if (!file) return;
    const url = importInput.dataset?.importUrl || urls.importData;
    if (!url) {
      if (window.showToast) {
        window.showToast('Import endpoint not configured.', 'error');
      }
      importInput.value = '';
      return;
    }
    importWrapper?.classList.add('is-loading');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
        },
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `Import failed (${response.status})`);
      }
      if (window.showToast) {
        const counts = data.created || {};
        window.showToast(
          `Imported ${counts.modules || 0} modules, ${counts.goals || 0} goals, ${counts.timeline || 0} timeline events.`,
          'success',
        );
      }
      refreshLiveData(true);
    } catch (error) {
      console.warn('PredictMyGrade: import failed', error);
      if (window.showToast) {
        window.showToast(error.message || 'Import failed. Try again.', 'error');
      }
    } finally {
      importWrapper?.classList.remove('is-loading');
      importInput.value = '';
    }
  });

  syncBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (syncBtn.dataset.busy === '1') return;
    syncBtn.dataset.busy = '1';
    toggleButtonLoading(syncBtn, true, 'Syncing...');
    await lightweightSync(true);
    toggleButtonLoading(syncBtn, false, 'Live sync');
    syncBtn.dataset.busy = '0';
  });

  timelineRefreshBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (timelineRefreshBtn.dataset.busy === '1') return;
    timelineRefreshBtn.dataset.busy = '1';
    toggleButtonLoading(timelineRefreshBtn, true, 'Refreshing...');
    await lightweightSync(true);
    toggleButtonLoading(timelineRefreshBtn, false);
    timelineRefreshBtn.dataset.busy = '0';
  });



  const snapshotButtons = Array.from(document.querySelectorAll('[data-snapshot-trigger]'));

  const handleSnapshot = async (event) => {
    event.preventDefault();
    const button = event.currentTarget;
    if (!urls.takeSnapshot || !button) return;
    toggleButtonLoading(button, true, 'Saving...');
    startProgress();
    try {
      const data = await postJSON(urls.takeSnapshot, {});
      emit('snapshotTaken', data);
      if (window.showToast) {
        const recordedAt = data?.saved_at || new Date().toLocaleString();
        window.showToast(`Snapshot saved at ${recordedAt}.`, 'success');
      }
      refreshLiveData(true);
    } catch (error) {
      console.warn('PredictMyGrade: snapshot failed', error);
      if (window.showToast) {
        window.showToast('Unable to save snapshot.', 'error');
      }
    } finally {
      toggleButtonLoading(button, false, 'Take Snapshot');
      endProgress();
    }
  };

  snapshotButtons.forEach((btn) => btn?.addEventListener('click', handleSnapshot));



  const digestBtn = document.getElementById('weeklyDigestBtn');

  const digestSummary = document.getElementById('weeklyDigestSummary');

  const digestTips = document.getElementById('weeklyDigestTips');

  digestBtn?.addEventListener('click', async (event) => {

    event.preventDefault();

    if (!urls.weeklyDigest) return;

    toggleButtonLoading(digestBtn, true, 'Generating...');
    digestBtn.disabled = true;

    startProgress();

    try {

      const resp = await fetch(urls.weeklyDigest, {

        headers: { 'X-Requested-With': 'XMLHttpRequest' },

      });

      const data = await resp.json();

      if (!resp.ok || data.ok === false) {

        const message =

          (data && (data.summary || data.answer)) ||

          'Weekly digest is unavailable.';

        if (digestSummary) {

          digestSummary.textContent = message;

        }

        if (digestTips) {

          digestTips.innerHTML = '';

        }

        if (window.showToast) {

          window.showToast(message, 'error');

        }

        return;

      }

      if (digestSummary) {

        digestSummary.textContent = data.summary || 'Digest ready.';

      }

      if (digestTips) {

        digestTips.innerHTML = '';

        (data.tips || []).forEach((tip) => {

          const li = document.createElement('li');

          li.textContent = tip;

          digestTips.appendChild(li);

        });

      }

      if (window.showToast) {

        window.showToast('Weekly digest ready.', 'success');

      }

    } catch (error) {

      console.warn('PredictMyGrade: weekly digest failed', error);

      if (digestSummary) {

        digestSummary.textContent = 'Unable to generate weekly digest right now.';

      }

      if (digestTips) {

        digestTips.innerHTML = '';

      }

      if (window.showToast) {

        window.showToast('Weekly digest unavailable.', 'error');

      }

    } finally {

      toggleButtonLoading(digestBtn, false);
      digestBtn.disabled = false;

      endProgress();

    }

  });



  const motivationEl = document.getElementById('dailyMotivationText');

  if (motivationEl) {

    fetchDailyMotivation(motivationEl);

  }



  const studyEnergyCard = document.getElementById('studyEnergyCard');

  if (studyEnergyCard) {

    fetchStudyEnergy(studyEnergyCard);

  }



  document.querySelectorAll('.mark-complete').forEach((btn) => {

    btn.addEventListener('click', async (event) => {

      event.preventDefault();

      const url = btn.dataset.url;

      if (!url) return;

      toggleButtonLoading(btn, true, 'Marking...');

      let completed = false;

      try {

        const resp = await fetch(url, {

          method: 'POST',

          headers: {

            'X-CSRFToken': getCSRFToken(),

            'X-Requested-With': 'XMLHttpRequest',

          },

        });

        const data = await resp.json().catch(() => ({}));

        if (!resp.ok || data.ok === false) {

          const message = (data && data.error) || 'Could not update deadline.';

          if (window.showToast) {

            window.showToast(message, 'error');

          }

          return;

        }

        const row = btn.closest('tr');

        if (row) {

          row.style.opacity = '0.4';

          row.classList.add('completed');

        }

        btn.dataset.originalText = 'Marked';

        completed = true;

        if (window.showToast) {

          window.showToast('Deadline marked complete.', 'success');

        }

      } catch (error) {

        console.warn('PredictMyGrade: mark deadline complete failed', error);

        if (window.showToast) {

          window.showToast('Could not mark deadline complete.', 'error');

        }

      } finally {

        toggleButtonLoading(btn, false);

        if (completed) {

          btn.disabled = true;

        }

      }

    });

  });

  async function inlineEditDeadline(button) {
    const url = button?.dataset?.url;
    const field = button?.dataset?.field;
    const row = button.closest('tr');
    if (!url || !field || !row) return;
    let promptLabel = 'Enter new value';
    if (field === 'title') promptLabel = 'Enter new title';
    if (field === 'weight') promptLabel = 'Enter weight (0-20)';
    if (field === 'module') promptLabel = 'Enter module name (optional)';
    const currentText =
      field === 'title'
        ? row.querySelector('.deadline-title__text')?.textContent || ''
        : field === 'weight'
          ? row.querySelector('.deadline-weight')?.textContent || ''
          : row.querySelector('.deadline-module')?.textContent || '';
    const value = window.prompt(promptLabel, currentText || '');
    if (value === null) return;
    const payload = new URLSearchParams();
    payload.set('field', field);
    payload.set('value', value);
    toggleButtonLoading(button, true, 'Saving...');
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: payload,
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) {
        const message = (data && data.error) || 'Could not update deadline.';
        if (window.showToast) window.showToast(message, 'error');
        return;
      }
      if (field === 'title') {
        const titleEl = row.querySelector('.deadline-title__text');
        if (titleEl) titleEl.textContent = data.title || value;
      }
      if (field === 'weight') {
        const weightEl = row.querySelector('.deadline-weight');
        if (weightEl) weightEl.textContent = data.weight ?? value;
      }
      if (field === 'module') {
        const moduleEl = row.querySelector('.deadline-module');
        if (moduleEl) moduleEl.textContent = data.module || '-';
      }
      if (window.showToast) window.showToast('Deadline updated.', 'success');
    } catch (error) {
      console.warn('PredictMyGrade: inline deadline update failed', error);
      if (window.showToast) window.showToast('Could not update deadline.', 'error');
    } finally {
      toggleButtonLoading(button, false);
    }
  }

  async function moveDeadlineToPlan(button) {
    const url = button?.dataset?.url;
    if (!url) return;
    toggleButtonLoading(button, true, 'Moving...');
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) {
        const message = (data && data.error) || 'Could not move deadline.';
        if (window.showToast) window.showToast(message, 'error');
        return;
      }
      if (data.plan_item) {
        refreshLiveData(false);
      }
      if (window.showToast) window.showToast('Deadline added to planner.', 'success');
    } catch (error) {
      console.warn('PredictMyGrade: move to planner failed', error);
      if (window.showToast) window.showToast('Unable to move deadline.', 'error');
    } finally {
      toggleButtonLoading(button, false);
    }
  }

  document.querySelectorAll('.inline-edit-deadline').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      await inlineEditDeadline(btn);
    });
  });

  document.querySelectorAll('.deadline-move').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      await moveDeadlineToPlan(btn);
    });
  });

  function decorateDeadlines() {
    const rows = document.querySelectorAll('#dashboardDeadlines tbody tr[data-due]');
    const today = new Date();
    rows.forEach((row) => {
      const dueIso = row.dataset.due;
      if (!dueIso) return;
      const dueDate = new Date(dueIso);
      const countdownWrap = row.querySelector('.deadline-countdown');
      const countdown = row.querySelector('.deadline-countdown__text') || countdownWrap;
      const indicator = row.querySelector('.deadline-indicator');
      const dateLabel = row.querySelector('.deadline-date');
      const timeDiff = dueDate.getTime() - today.getTime();
      const days = Math.round(timeDiff / (1000 * 60 * 60 * 24));
      let label = '';
      row.classList.remove('due-soon', 'overdue');
      if (Number.isNaN(days)) {
        label = '';
      } else if (days < 0) {
        label = `Overdue by ${Math.abs(days)}d`;
        row.classList.add('overdue');
      } else if (days === 0) {
        label = 'Due today';
        row.classList.add('due-soon');
      } else {
        label = `Due in ${days}d`;
        if (days <= 3) {
          row.classList.add('due-soon');
        }
      }
      if (countdown) {
        countdown.textContent = label;
        countdown.classList.toggle('text-danger', row.classList.contains('overdue'));
        countdown.classList.toggle('text-warning', row.classList.contains('due-soon'));
      }
      if (indicator) {
        indicator.textContent = row.classList.contains('overdue')
          ? '!'
          : row.classList.contains('due-soon')
            ? '!'
            : '-';
        indicator.classList.toggle('text-danger', row.classList.contains('overdue'));
        indicator.classList.toggle('text-warning', row.classList.contains('due-soon'));
      }
      if (dateLabel && dueDate.toDateString() !== dateLabel.textContent) {
        // Keep the formatted date if already set; otherwise let backend format stand.
      }
    });
  }

  const DEADLINE_DECORATION_INTERVAL = 60 * 1000;
  function startDeadlineDecorator() {
    decorateDeadlines();
    if (deadlineDecorationTimer) {
      clearInterval(deadlineDecorationTimer);
    }
    deadlineDecorationTimer = setInterval(decorateDeadlines, DEADLINE_DECORATION_INTERVAL);
  }

  async function updateDeadlineDate(button, payload) {
    const url = button?.dataset?.url;
    const row = button?.closest('tr');
    if (!url || !row) return;
    toggleButtonLoading(button, true, 'Saving...');
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) {
        const message = (data && data.error) || 'Could not update deadline.';
        if (window.showToast) {
          window.showToast(message, 'error');
        }
        return;
      }
      if (data.due_date) {
        row.dataset.due = data.due_date;
      }
      const dateCell = row.querySelector('.deadline-date');
      if (dateCell && data.due_display) {
        dateCell.textContent = data.due_display;
      }
      decorateDeadlines();
      if (window.showToast) {
        window.showToast('Deadline updated.', 'success');
      }
    } catch (error) {
      console.warn('PredictMyGrade: deadline update failed', error);
      if (window.showToast) {
        window.showToast('Could not update deadline.', 'error');
      }
    } finally {
      toggleButtonLoading(button, false);
    }
  }

  document.querySelectorAll('.deadline-snooze').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      const days = Number(btn.dataset.days || 2);
      await updateDeadlineDate(btn, { days: days.toString() });
    });
  });

  document.querySelectorAll('.deadline-reschedule').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.preventDefault();
      const row = btn.closest('tr');
      const current = row?.dataset?.due || '';
      const next = window.prompt('Enter a new due date (YYYY-MM-DD)', current.slice(0, 10));
      if (!next) return;
      await updateDeadlineDate(btn, { due_date: next });
    });
  });

  startDeadlineDecorator();



  document.querySelectorAll('.module-inline-edit').forEach((btn) => {

    btn.addEventListener('click', async (event) => {

      event.preventDefault();

      const url = btn.dataset.url;

      if (!url) return;

      const current = btn.dataset.grade || '';

      const input = window.prompt('Enter new grade percentage (0-100)', current);

      if (input === null) return;

      const value = Number.parseFloat(input);

      if (!Number.isFinite(value) || value < 0 || value > 100) {

        if (window.showToast) {

          window.showToast('Please enter a value between 0 and 100.', 'error');

        }

        return;

      }

      toggleButtonLoading(btn, true, 'Saving...');

      try {

        const body = new URLSearchParams();

        body.set('field', 'grade_percent');

        body.set('value', value.toString());

        const resp = await fetch(url, {

          method: 'POST',

          headers: {

            'X-CSRFToken': getCSRFToken(),

            'X-Requested-With': 'XMLHttpRequest',

          },

          body,

        });

        const data = await resp.json().catch(() => ({}));

        if (!resp.ok || data.ok === false) {

          const message = (data && data.error) || 'Unable to update module.';

          if (window.showToast) {

            window.showToast(message, 'error');

          }

          return;

        }

        const li = btn.closest('li');

        if (li) {

          const gradeSpan = li.querySelector('.module-grade');

          if (gradeSpan) {

            gradeSpan.textContent = `${value.toFixed(1)}%`;

          }

          btn.dataset.grade = value.toFixed(1);

        }

        if (window.showToast) {

          window.showToast('Module grade updated.', 'success');

        }

      } catch (error) {

        console.warn('PredictMyGrade: module inline update failed', error);

        if (window.showToast) {

          window.showToast('Unable to update module.', 'error');

        }

      } finally {

        toggleButtonLoading(btn, false);

      }

    });

  });



  const moduleSearch = document.getElementById('moduleSearch');

  const moduleList = document.getElementById('moduleList');

  if (moduleSearch && moduleList) {

    const items = Array.from(moduleList.querySelectorAll('li'));

    moduleSearch.addEventListener('input', () => {

      const query = moduleSearch.value.trim().toLowerCase();

      items.forEach((item) => {

        const matches = !query || item.textContent.toLowerCase().includes(query);

        item.hidden = !matches;

        item.setAttribute('aria-hidden', String(!matches));

      });

    });

  }



  const planBtn = document.getElementById('aiGeneratePlanBtn');

  planBtn?.addEventListener('click', async (event) => {

    event.preventDefault();

    if (!urls.generatePlan) return;

    toggleButtonLoading(planBtn, true, 'Generating...');
    planBtn.disabled = true;

    startProgress();

    try {

      const data = await requestJSON(urls.generatePlan);

      if (window.showToast) {

        window.showToast(data.msg || 'AI study plan generated.', 'success');

      }

      emit('studyPlanUpdated', data);

      if (Array.isArray(data.plan_items) && data.plan_items.length) {

        renderWeeklyCalendar(data.plan_items);

        highlightCalendar();

      }

      if (data.limit_note && window.showToast) {

        window.showToast(data.limit_note, 'info');

      }

    } catch (error) {

      console.warn('PredictMyGrade: AI plan generation failed', error);

      if (window.showToast) {

        window.showToast('Unable to generate plan.', 'error');

      }

    } finally {

      toggleButtonLoading(planBtn, false, 'Generate My Study Plan');
      planBtn.disabled = false;

      endProgress();

    }

  });



  const studyPlanForm = document.getElementById('studyPlanForm');

  if (studyPlanForm && urls.addStudyPlan) {
    studyPlanForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(studyPlanForm);
      const button = studyPlanForm.querySelector('button[type="submit"]');
      toggleButtonLoading(button, true, 'Saving...');
      startProgress();
      try {
        const response = await fetch(urls.addStudyPlan, {
          method: 'POST',
          headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') || '' },
          body: formData,
        });
        let data = {};
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          data = await response.json();
        }
        studyPlanForm.reset();
        if (window.showToast) {
          window.showToast('Study plan item added.', 'success');
        }
        if (data.plan_item) {
          const items = Array.isArray(data.plan_items) ? data.plan_items : [data.plan_item];
          emit('studyPlanUpdated', { plan_items: items });
          renderWeeklyCalendar(items);
          highlightCalendar();
        } else {
          emit('studyPlanUpdated', {});
        }
        if (data.limit_note && window.showToast) {
          window.showToast(data.limit_note, 'info');
        }
      } catch (error) {
        console.warn('PredictMyGrade: add study plan failed', error);
        if (window.showToast) {
          window.showToast('Unable to add study plan item.', 'error');
        }
      } finally {
        toggleButtonLoading(button, false);
        endProgress();
      }
    });
  }


  function renderComparison(items) {

    if (!comparisonList || !Array.isArray(items)) return;

    comparisonList.innerHTML = '';

    if (!items.length) {

      const li = document.createElement('li');

      li.textContent = 'No snapshot comparison yet.';

      comparisonList.appendChild(li);

      return;

    }

    items.forEach((item) => {
      const li = document.createElement('li');
      li.dataset.label = item.label;
      li.innerHTML = `
        <span class="label">${item.label}</span>
        <span class="change" data-change="${item.change}">${Number(item.change).toFixed(1)}%</span>
      `;
      const changeEl = li.querySelector('.change');
      if (changeEl) {
        const numeric = Number(item.change);
        changeEl.classList.toggle('positive', numeric >= 0);
        changeEl.classList.toggle('negative', numeric < 0);
      }
      comparisonList.appendChild(li);
    });

    glowElement(comparisonList, { className: 'pulse-highlight' });

  }

  refreshComparisonBtn?.addEventListener('click', async (event) => {
    event.preventDefault();
    if (!urls.comparison) {
      if (window.showToast) {
        window.showToast('Snapshot comparison endpoint unavailable.', 'error');
      }
      return;
    }
    toggleButtonLoading(refreshComparisonBtn, true, 'Refreshing...');
    startProgress();
    try {
      const payload = await requestJSON(urls.comparison);
      const comparisons = Array.isArray(payload?.comparison)
        ? payload.comparison
        : Array.isArray(payload)
          ? payload
          : [];
      renderComparison(comparisons);
      if (comparisons.length && window.showToast) {
        window.showToast('Snapshot comparison updated.', 'success');
      }
    } catch (error) {
      console.warn('PredictMyGrade: comparison refresh failed', error);
      if (window.showToast) {
        window.showToast('Unable to refresh comparisons.', 'error');
      }
    } finally {
      toggleButtonLoading(refreshComparisonBtn, false, 'Refresh');
      endProgress();
    }
  });



  function renderWeeklyCalendar(items = []) {

    if (!weeklyCalendar) return;

    weeklyCalendar.innerHTML = '';

    if (!items.length) {

      weeklyCalendar.innerHTML = '<p class="muted">No study sessions scheduled yet.</p>';

      if (calendarHint) {

        calendarHint.textContent = 'Add sessions to your planner or ask the assistant to generate a schedule.';

      }

      return;

    }

    const grouped = items.reduce((acc, entry) => {

      const key = entry.date;

      if (!acc[key]) acc[key] = [];

      acc[key].push(entry);

      return acc;

    }, {});



    Object.entries(grouped)

      .sort(([a], [b]) => (a > b ? 1 : -1))

      .forEach(([date, sessions]) => {

        const day = document.createElement('div');

        day.className = 'calendar-day';

        const label = new Date(date).toLocaleDateString(undefined, {

          weekday: 'short',

          month: 'short',

          day: 'numeric',

        });

        day.innerHTML = `<strong>${label}</strong>`;

        const list = document.createElement('ul');

        sessions.forEach((session) => {

          const li = document.createElement('li');

          li.textContent = `${session.title} - ${Number(session.hours).toFixed(1)}h`;

          list.appendChild(li);

        });

        day.appendChild(list);

        weeklyCalendar.appendChild(day);

      });

    if (calendarHint) {

      calendarHint.textContent = 'Synced with AI assistant and planner.';

    }

  }



  function highlightCalendar() {

    if (!weeklyCalendar) return;

    glowElement(weeklyCalendar, { className: 'pulse-highlight', duration: 1400 });

  }

  function touchFreshness(el) {
    if (!el) return;
    const stamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    el.textContent = `Refreshed at ${stamp}`;
  }

  function shouldUpdateChart(chart, cacheKey, payload) {
    if (!chart) return false;
    const serialized = JSON.stringify(payload);
    if (chart[cacheKey] === serialized) {
      return false;
    }
    chart[cacheKey] = serialized;
    return true;
  }

  function safeUpdateDashboard(data, options = {}) {
    clearTimeout(_dashboardUpdateTimer);
    _dashboardUpdateTimer = setTimeout(() => {
      handleLivePayload(data, options);
    }, 200);
  }


  function handleLivePayload(data, { showToast = false } = {}) {
    if (!data || typeof data !== 'object') return;
    updateSummary(data);
    updateTimelineCharts(data);
    if (Array.isArray(data.timeline_events)) {
      updateTimelineEvents(data.timeline_events);
      insightsModule.refreshNow?.();
    }
    setLastSyncLabel(data.generated_at || new Date().toISOString());
    updateMoodIndicator(data.ai_confidence ?? data.confidence, data.band);
    assistantModule.updateLive?.(data);
    insightsModule.updateLive?.(data);
    goalsModule.updateLive?.(data);
    if (Array.isArray(data.comparison)) {
      renderComparison(data.comparison);
    }
    if (Array.isArray(data.calendar)) {
      renderWeeklyCalendar(data.calendar);
      if (data.calendar.length) {
        highlightCalendar();
      }
    }
    refreshWeeklyGoalsChart(urls);
    refreshHabitChart(urls);
    if (showToast && window.showToast) {
      window.showToast('Dashboard synced.', 'success');
    }
  }

  window.addEventListener('storage', (event) => {
    if (event.key !== 'predictmygrade_live_update') return;
    clearTimeout(_liveUpdateTimer);
    _liveUpdateTimer = setTimeout(() => {
      try {
        const data = JSON.parse(event.newValue || '{}');
        safeUpdateDashboard(
          {
            avg: data.avg,
            band: data.band,
            next_target: data.next_target,
            next_label: data.next_label,
            weekly: data.weekly,
            generated_at: new Date().toISOString(),
          },
          { showToast: true },
        );
      } catch (_) {
        // ignore transient storage writes
      }
    }, 200);
  });

  const commandHandlers = {
    snapshot: () => snapshotButtons[0]?.click(),
    plan: () => planBtn?.click(),
    refresh: async () => {
      if (syncBtn) toggleButtonLoading(syncBtn, true, 'Syncing...');
      await refreshLiveData(true);
      if (syncBtn) toggleButtonLoading(syncBtn, false, 'Live sync');
    },
    motivate: () => fetchDailyMotivation(motivationEl),
    export: () => exportBtn?.click(),
    import: () => importInput?.click(),
    sync: async () => {
      if (syncBtn) toggleButtonLoading(syncBtn, true, 'Syncing...');
      await lightweightSync(true);
      if (syncBtn) toggleButtonLoading(syncBtn, false, 'Live sync');
    },
  };

  async function applyCommandPalette(action) {
    const key = (action || '').trim().toLowerCase();
    if (!key) return false;
    const handler = commandHandlers[key];
    if (handler) {
      await handler();
      return true;
    }
    const candidate = paletteCommands.find(
      (cmd) => String(cmd.id || '').toLowerCase() === key,
    );
    if (candidate && window.showToast) {
      window.showToast(`${candidate.label || 'That command'} is not available yet.`, 'info');
    }
    return false;
  }



  document.addEventListener('snapshotTaken', (event) => {
    if (assistantModule.refreshTip) {
      assistantModule.refreshTip(false);
    }
    const detail = event?.detail;
    if (detail && Array.isArray(detail.comparison)) {
      renderComparison(detail.comparison);
    }
  });

  document.addEventListener('studyPlanUpdated', (event) => {
    const items = event?.detail?.plan_items;
    if (Array.isArray(items) && items.length) {
      renderWeeklyCalendar(items);
      highlightCalendar();
    }
  });

  document.addEventListener('assistantPlanCreated', (event) => {
    const items = event?.detail?.plan_items;
    if (Array.isArray(items) && items.length) {
      renderWeeklyCalendar(items);
      highlightCalendar();
    }
  });

  commandRunBtn?.addEventListener('click', async () => {
    const value = commandInput?.value?.trim().toLowerCase();
    if (!value) return;
    const resetRunBtn = () => {
      toggleButtonLoading(commandRunBtn, false, 'Run');
    };
    toggleButtonLoading(commandRunBtn, true, 'Running...');
    const handled = await applyCommandPalette(value);
    if (!handled) {
      const known = paletteCommands.some(
        (cmd) => String(cmd.id || '').toLowerCase() === value,
      );
      if (!known && window.showToast) {
        window.showToast(`Unknown command: ${value}`, 'error');
      }
    }
    if (commandInput) {
      commandInput.value = '';
    }
    setTimeout(resetRunBtn, 400);
  });

  commandInput?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      commandRunBtn?.click();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      commandInput.value = '';
      commandInput.blur();
    }
  });

  async function refreshLiveData(showToast) {
    try {
      const data = await requestJSON(urls.liveData);
      safeUpdateDashboard(data, { showToast });
    } catch (error) {
      console.warn('PredictMyGrade: live data refresh failed', error);
      if (showToast && window.showToast) {
        window.showToast('Live sync failed. Check your connection and try again.', 'error');
      }
    }
  }


  function setLastSyncLabel(timestamp) {
    if (!lastSyncLabel) return;
    const source = timestamp ? new Date(timestamp) : new Date();
    if (Number.isNaN(source.getTime())) {
      lastSyncLabel.textContent = 'Synced moments ago';
      return;
    }
    const fmt = source.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    lastSyncLabel.textContent = `Synced at ${fmt}`;
    const staleDot = document.getElementById('syncStaleDot');
    if (staleDot) {
      const ageMs = Date.now() - source.getTime();
      const stale = ageMs > 2 * 60 * 1000;
      staleDot.hidden = !stale;
      staleDot.setAttribute('aria-hidden', stale ? 'false' : 'true');
    }
  }

  function updateMoodIndicator(confidence, bandLabel) {
    const moodValue = Number(confidence);
    const clamped = Number.isFinite(moodValue) ? Math.max(0, Math.min(100, moodValue)) : 0;
    if (aiMoodRing) {
      const offset = AI_MOOD_CIRCUMFERENCE * (1 - clamped / 100);
      aiMoodRing.style.strokeDashoffset = offset;
      if (clamped >= 80) {
        aiMoodRing.style.stroke = '#22c55e';
      } else if (clamped >= 55) {
        aiMoodRing.style.stroke = '#facc15';
      } else {
        aiMoodRing.style.stroke = '#f97316';
      }
    }
    if (aiMoodLabel) {
      aiMoodLabel.textContent = `${clamped.toFixed(0)}%`;
    }
    if (aiMoodText) {
      const status =
        clamped >= 80 ? 'Calm focus' : clamped >= 55 ? 'Steady effort' : 'Lift energy soon';
      const descriptor = bandLabel ? `${bandLabel} cohort` : 'AI insight';
      aiMoodText.textContent = `${descriptor} · ${status}`;
    }
  }

  function iconForEvent(type) {
    switch (type) {
      case 'module_added':
        return 'fa-square-plus';
      case 'module_removed':
        return 'fa-square-minus';
      case 'goal_completed':
        return 'fa-flag-checkered';
      case 'snapshot_taken':
        return 'fa-camera';
      default:
        return 'fa-circle';
    }
  }

  function updateTimelineEvents(events) {
    if (!timelineStream) return;
    timelineStream.innerHTML = '';
    if (!Array.isArray(events) || !events.length) {
      timelineStream.setAttribute('data-empty', '1');
      if (timelineEmptyState) {
        timelineEmptyState.hidden = false;
      }
      return;
    }
    timelineStream.removeAttribute('data-empty');
    if (timelineEmptyState) {
      timelineEmptyState.hidden = true;
    }
    const fragment = document.createDocumentFragment();
    events.forEach((event) => {
      const article = document.createElement('article');
      article.className = 'timeline-event';
      if (event.id) {
        article.dataset.eventId = event.id;
      }
      if (event.type) {
        article.dataset.eventType = event.type;
      }
      const icon = iconForEvent(event.type);
      article.innerHTML = `
        <div class="timeline-icon"><i class="fa-solid ${icon}"></i></div>
        <div class="timeline-content">
          <p>${event.message || 'Timeline update'}</p>
          <time datetime="${event.created_at || ''}">${event.display_time || ''}</time>
        </div>
      `;
      fragment.appendChild(article);
    });
    timelineStream.appendChild(fragment);
    if (window.AOS && typeof window.AOS.refreshHard === 'function') {
      window.AOS.refreshHard();
    }
  }

  async function lightweightSync(showToast = false) {
    if (!urls.sync) return;
    try {
      const data = await requestJSON(urls.sync);
      safeUpdateDashboard(data, { showToast });
    } catch (error) {
      console.warn('PredictMyGrade: sync failed', error);
      if (showToast && window.showToast) {
        window.showToast('Sync failed. Try again later.', 'error');
      }
    }
  }

  function updateSummary(data) {
    const avgEl = document.getElementById('avgDisplay');
    const bandEl = document.getElementById('bandDisplay');
    const progressEl = document.getElementById('progressBar');
    const safeAvg = Number.isFinite(Number(data.avg)) ? Number(data.avg) : 0;
    if (avgEl) {
      avgEl.textContent = formatPercent(safeAvg);
      avgEl.dataset.value = safeAvg;
      glowElement(avgEl, { className: 'pulse-highlight' });
    }
    if (bandEl && data.band) {
      bandEl.textContent = data.band;
      glowElement(bandEl, { className: 'pulse-highlight' });
    }
    if (progressEl && typeof data.progress === 'number') {
      const clamped = Math.max(0, Math.min(100, data.progress));
      progressEl.style.width = `${clamped}%`;
      progressEl.dataset.progress = data.progress;
      glowElement(progressEl, { className: 'pulse-highlight' });
    }
  }


  function updateTimelineCharts(data) {

    const rawValues = (data.timeline_values || []).map((value) => Number(value));
    if (!rawValues.length) return;
    const hasValidValues = rawValues.some((value) => Number.isFinite(value));
    if (!hasValidValues) return;
    const sanitizedValues = rawValues.map((value) => (Number.isFinite(value) ? value : 0));
    const labelSource = Array.isArray(data.timeline_labels) ? data.timeline_labels : [];
    if (labelSource.length && labelSource.length !== sanitizedValues.length) {
      return;
    }
    const labels =
      labelSource.length === sanitizedValues.length && sanitizedValues.length
        ? labelSource
        : sanitizedValues.map((_, index) => `W${index + 1}`);

    const values = sanitizedValues.slice();
    const timelineLabels = labels.slice();
    const timelinePayload = { labels: timelineLabels, values };

    const timelineChart = getChart('timeline');

    if (timelineChart && shouldUpdateChart(timelineChart, '$timelineCache', timelinePayload)) {
      if (typeof timelineChart.$applyTimelineSource === 'function') {
        timelineChart.$applyTimelineSource(timelinePayload);
      } else {
        timelineChart.data.labels = timelineLabels;
        timelineChart.data.datasets[0].data = values;
        timelineChart.update('none');
      }
    }

    const sparkChart = getChart('spark');
    if (sparkChart && shouldUpdateChart(sparkChart, '$sparkCache', timelinePayload)) {
      sparkChart.data.labels = timelineLabels;
      sparkChart.data.datasets[0].data = values;
      sparkChart.update('none');
    }

    const forecastChart = getChart('forecast');
    const latestValue = values[values.length - 1];
    const aiData = {
      predictedAverage: Number(
        data.ai_predicted_average ?? data.predicted_average ?? latestValue,
      ),
      confidence: Number(data.ai_confidence ?? data.confidence),
      model: data.ai_model || data.model,
    };
    const forecastPayload = {
      labels: timelineLabels,
      values,
      ai: aiData,
    };
      if (forecastChart && shouldUpdateChart(forecastChart, '$forecastCache', forecastPayload)) {
        const summaryEl = document.getElementById('forecastSummary');
        if (typeof forecastChart.$updateForecast === 'function') {
          forecastChart.$updateForecast(timelinePayload, aiData, summaryEl);
        } else {
          forecastChart.data.labels = timelineLabels.concat(['Next']);
          forecastChart.data.datasets[0].data = values.concat([latestValue]);
          forecastChart.update('none');
        }
        touchFreshness(forecastFreshness);
        const confidenceChart = getChart('confidenceTrend');
        const confidenceValues =
          Array.isArray(data.confidence_trend) && data.confidence_trend.length
            ? data.confidence_trend.map((value) => {
                const numeric = Number(value);
                return Number.isFinite(numeric) ? numeric : 0;
              })
            : timelineLabels.map(() => Number(aiData.confidence) || 0);
        const confidencePayload = {
          labels: timelineLabels,
          values: confidenceValues,
        };
        if (
          confidenceChart &&
          shouldUpdateChart(confidenceChart, '$confidenceCache', confidencePayload)
        ) {
          if (typeof confidenceChart.$refreshConfidence === 'function') {
            confidenceChart.$refreshConfidence(timelineLabels, confidenceValues);
          } else {
            confidenceChart.data.labels = timelineLabels;
            confidenceChart.data.datasets[0].data = confidenceValues;
            confidenceChart.update('none');
          }
        }
      }
  }



  async function fetchDailyMotivation(el) {

    const url = el.dataset.url;

    if (!url) return;

    try {

      const data = await requestJSON(url);

      el.textContent = data.quote || 'Keep going - your effort compounds.';
      glowElement(el, { className: 'pulse-highlight' });

    } catch (error) {

      console.warn('PredictMyGrade: daily motivation failed', error);

      el.textContent = 'Motivation is unavailable right now.';

    }

  }



  async function fetchStudyEnergy(card) {

    const url = card.dataset.url;

    if (!url) return;

    try {

      const data = await requestJSON(url);

      const value = Number(data.energy) || 0;

      const clamped = Math.max(0, Math.min(100, value));

      const bar = card.querySelector('#studyEnergyBar');

      const valueEl = card.querySelector('#studyEnergyValue');

      if (bar) {

        bar.style.width = `${clamped}%`;

        bar.textContent = `${clamped.toFixed(0)}%`;

      }

      if (valueEl) {

        valueEl.textContent = `${clamped.toFixed(0)}%`;

        glowElement(valueEl, { className: 'pulse-highlight' });

      }

    } catch (error) {

      console.warn('PredictMyGrade: study energy fetch failed', error);

    }

  }

}




