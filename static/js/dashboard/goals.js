import {
  requestJSON,
  startProgress,
  endProgress,
  toggleButtonLoading,
  getCSRFToken,
} from './helpers.js';

const STATUS_OPTIONS = [
  { value: 'planning', label: 'Planning' },
  { value: 'active', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'paused', label: 'Paused' },
];

const CATEGORY_LABELS = {
  academic: 'Academic',
  assessment: 'Assessment',
  habit: 'Study Habit',
  application: 'Application',
};

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function formatDue(goal) {
  if (goal.due_date == null || goal.due_in_days == null) {
    return { text: 'No due date', className: '' };
  }
  if (goal.overdue) {
    const days = Math.abs(goal.due_in_days);
    return {
      text: `Overdue by ${days} day${days === 1 ? '' : 's'}`,
      className: 'goal-due--overdue',
    };
  }
  if (goal.due_in_days === 0) {
    return { text: 'Due today', className: 'goal-due--soon' };
  }
  if (goal.due_in_days <= 7) {
    return {
      text: `Due in ${goal.due_in_days} day${goal.due_in_days === 1 ? '' : 's'}`,
      className: 'goal-due--soon',
    };
  }
  return {
    text: `Due in ${goal.due_in_days} days`,
    className: '',
  };
}

function statusClass(status) {
  switch (status) {
    case 'active':
      return 'goal-status--active';
    case 'completed':
      return 'goal-status--completed';
    case 'paused':
      return 'goal-status--paused';
    default:
      return 'goal-status--planning';
  }
}

function goalDetailUrl(urls, id) {
  const base = urls.studyGoals || '/dashboard/goals/';
  return `${base}${id}/`;
}

export default function initGoals(boot) {
  const urls = boot.urls || {};
  const form = document.getElementById('goalForm');
  const submitBtn = form ? form.querySelector('[data-goal-submit]') : null;
  const refreshBtn = document.getElementById('goalsRefresh');
  const listEl = document.getElementById('goalList');
  const emptyEl = document.getElementById('goalListEmpty');
  const summaryEl = document.getElementById('goalsSummary');
  const setGoalControlsBusy = (disabled) => {
    const controls = listEl?.querySelectorAll('[data-goal-status], [data-goal-complete], [data-goal-delete]');
    controls?.forEach((node) => {
      node.disabled = disabled;
    });
    if (submitBtn) {
      submitBtn.disabled = disabled;
      toggleButtonLoading(submitBtn, disabled, disabled ? 'Saving...' : 'Add goal');
    }
    if (refreshBtn) {
      refreshBtn.disabled = disabled;
    }
  };
  if (!listEl || !form) {
    return { updateLive: () => {} };
  }

  let goals = Array.isArray(boot.goals?.items) ? boot.goals.items.slice() : [];
  let summary = boot.goals?.summary || {};

  renderSummary(summary);
  renderGoals(goals);

  async function createGoal(event) {
    event.preventDefault();
    const titleInput = document.getElementById('goalText');
    const dueInput = document.getElementById('goalDue');
    const categoryInput = document.getElementById('goalCategory');
    const moduleInput = document.getElementById('goalModule');
    const targetInput = document.getElementById('goalTarget');
    if (!titleInput?.value.trim()) {
      if (window.showToast) window.showToast('Add a goal title first.', 'error');
      return;
    }
    const payload = {
      title: titleInput.value.trim(),
      due_date: dueInput?.value || null,
      category: categoryInput?.value || 'academic',
      module_name: moduleInput?.value || '',
      target_percent: targetInput?.value || null,
    };
    toggleButtonLoading(submitBtn, true, 'Adding...');
    setGoalControlsBusy(true);
    startProgress();
    try {
      const resp = await fetch(urls.studyGoals || '/dashboard/goals/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data?.error || 'Failed to add goal.');
      }
      if (data.goal) {
        goals.unshift(data.goal);
      }
      if (data.summary) {
        summary = data.summary;
        renderSummary(summary);
      }
      renderGoals(goals);
      form.reset();
      if (window.showToast) window.showToast('Goal added.', 'success');
    } catch (error) {
      console.warn('PredictMyGrade: failed to create goal', error);
      if (window.showToast) window.showToast(error.message || 'Could not create goal.', 'error');
    } finally {
      toggleButtonLoading(submitBtn, false);
      setGoalControlsBusy(false);
      endProgress();
    }
  }

  async function refreshGoals() {
    if (!urls.studyGoals) return;
    toggleButtonLoading(refreshBtn, true, 'Refreshing...');
    startProgress();
    try {
      const data = await requestJSON(urls.studyGoals);
      goals = Array.isArray(data.items) ? data.items : [];
      summary = data.summary || summary;
      renderSummary(summary);
      renderGoals(goals);
    } catch (error) {
      console.warn('PredictMyGrade: failed to refresh goals', error);
      if (window.showToast) window.showToast('Unable to refresh goals right now.', 'error');
    } finally {
      toggleButtonLoading(refreshBtn, false, 'Refresh');
      endProgress();
    }
  }

  async function updateGoal(id, payload, { silent = false } = {}) {
    try {
      if (!silent) {
        startProgress();
        setGoalControlsBusy(true);
      }
      const resp = await fetch(goalDetailUrl(urls, id), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data?.error || 'Goal update failed');
      }
      if (data.deleted) {
        goals = goals.filter((item) => item.id !== id);
      } else if (data.goal) {
        goals = goals.map((item) => (item.id === id ? data.goal : item));
      }
      if (data.summary) {
        summary = data.summary;
        renderSummary(summary);
      }
      renderGoals(goals);
      if (!silent && window.showToast) window.showToast('Goal updated.', 'success');
    } catch (error) {
      console.warn('PredictMyGrade: goal update failed', error);
      if (!silent && window.showToast) window.showToast(error.message || 'Goal update failed.', 'error');
    } finally {
      if (!silent) {
        endProgress();
        setGoalControlsBusy(false);
      }
    }
  }

  function renderSummary(data) {
    if (!summaryEl) return;
    const summaryValues = summaryEl.querySelectorAll('[data-goal-summary]');
    summaryValues.forEach((node) => {
      const key = node.dataset.goalSummary;
      if (key && data[key] !== undefined) {
        const value = typeof data[key] === 'number' ? data[key] : 0;
        node.textContent = key === 'average_progress' ? `${Math.round(value)}%` : value;
      }
    });
  }

  function renderGoals(items) {
    listEl.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      if (emptyEl) emptyEl.style.display = '';
      return;
    }
    if (emptyEl) emptyEl.style.display = 'none';
    items.forEach((goal) => {
      const li = createGoalItem(goal);
      listEl.appendChild(li);
    });
  }

  function createGoalItem(goal) {
    const li = document.createElement('li');
    li.className = 'goal-item';
    li.dataset.goalId = goal.id;
    const due = formatDue(goal);
    const categoryLabel = CATEGORY_LABELS[goal.category] || 'General';
    const statusBadge = statusClass(goal.status);
    const statusOptions = STATUS_OPTIONS.map(
      ({ value, label }) => `<option value="${value}"${value === goal.status ? ' selected' : ''}>${label}</option>`,
    ).join('');
    li.innerHTML = `
      <div class="goal-item__header">
        <div class="goal-item__title">
          ${escapeHtml(goal.title)}
          ${goal.module_name ? `<span class="goal-tag">${escapeHtml(goal.module_name)}</span>` : ''}
        </div>
        <div class="goal-actions">
          <span class="goal-status-badge ${statusBadge}">${escapeHtml(goal.status_label || goal.status)}</span>
          <select class="input-field goal-status-select" data-goal-status>${statusOptions}</select>
          <button class="btn secondary small" data-goal-complete ${goal.status === 'completed' ? 'disabled' : ''}>Mark Complete</button>
          <button class="btn secondary small" data-goal-delete>Delete</button>
        </div>
      </div>
      <div class="goal-item__meta">
        <span class="goal-tag">${categoryLabel}</span>
        <span class="goal-due ${due.className}">${due.text}</span>
        ${goal.target_percent != null ? `<span>Target ${Number(goal.target_percent).toFixed(1)}%</span>` : ''}
      </div>
      <div class="goal-progress">
        <input type="range" min="0" max="100" value="${goal.progress}" data-goal-progress ${goal.status === 'completed' ? 'disabled' : ''}>
        <span class="goal-progress__value">${goal.progress}%</span>
      </div>
      ${goal.description ? `<p class="goal-item__description">${escapeHtml(goal.description)}</p>` : ''}
    `;

    const statusSelect = li.querySelector('[data-goal-status]');
    const progressInput = li.querySelector('[data-goal-progress]');
    const progressValue = li.querySelector('.goal-progress__value');
    const completeBtn = li.querySelector('[data-goal-complete]');
    const deleteBtn = li.querySelector('[data-goal-delete]');

    statusSelect?.addEventListener('change', () => {
      updateGoal(goal.id, { status: statusSelect.value });
    });

    if (progressInput && progressValue) {
      progressInput.addEventListener('input', () => {
        progressValue.textContent = `${progressInput.value}%`;
      });
      progressInput.addEventListener('change', () => {
        updateGoal(goal.id, { progress: Number(progressInput.value) }, { silent: true });
      });
    }

    completeBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      updateGoal(goal.id, { status: 'completed' });
    });

    deleteBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      if (window.confirm && !window.confirm('Delete this goal?')) return;
      updateGoal(goal.id, { action: 'delete' });
    });

    return li;
  }

  if (submitBtn) {
    submitBtn.addEventListener('click', createGoal);
  }
  form.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      createGoal(event);
    }
  });
  refreshBtn?.addEventListener('click', refreshGoals);

  return {
    updateLive(data) {
      if (!data) return;
      if (data.goal_summary) {
        summary = data.goal_summary;
        renderSummary(summary);
      }
    },
  };
}
