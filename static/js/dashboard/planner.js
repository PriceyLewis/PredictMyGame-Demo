import { debounce, postJSON, toggleButtonLoading, safeNumber } from './helpers.js';

const TERM_OPTIONS = ['Term 1', 'Term 2', 'Term 3', 'Semester 1', 'Semester 2', 'Year-long'];
const CATEGORY_OPTIONS = ['Core', 'Elective', 'Optional'];
const STATUS_OPTIONS = ['Planned', 'Enrolled', 'In Progress', 'Completed'];

function optionMarkup(options, selected) {
  return options
    .map((option) => {
      const isSelected = option === selected ? ' selected' : '';
      return `<option value="${option}"${isSelected}>${option}</option>`;
    })
    .join('');
}

function formatHours(value) {
  if (!Number.isFinite(value)) return '0';
  const normalised = Number(value.toFixed(1));
  return normalised % 1 === 0 ? String(normalised.toFixed(0)) : String(normalised.toFixed(1));
}

function computeWeightedAverage(modules) {
  const graded = modules.filter(
    (item) => item.grade !== null && item.grade !== undefined && (item.credits || 0) > 0,
  );
  const totalCredits = graded.reduce((sum, item) => sum + (item.credits || 0), 0);
  if (!totalCredits) return null;
  const weightedSum = graded.reduce(
    (sum, item) => sum + (item.grade || 0) * (item.credits || 0),
    0,
  );
  return weightedSum / totalCredits;
}

export default function initPlanner(boot) {
  const form = document.getElementById('targetPlannerForm');
  const modulesTableBody = document.querySelector('#futureModulesTable tbody');
  const modulesTableWrapper = document.querySelector('#futureModulesTable')?.closest('.table-scroll');
  const addModuleBtn = document.getElementById('addFutureModuleBtn');
  const creditsTotalEl = document.getElementById('futureCreditsTotal');
  const expectedAvgEl = document.getElementById('futureExpectedAverage');
  const summaryEl = document.getElementById('plannerSummary');
  const totalDisplay = document.getElementById('totalCreditsDisplay');
  const remainingDisplay = document.getElementById('remainingCreditsDisplay');
  const progressBar = document.getElementById('plannerProgressBar');
  const workloadTotalEl = document.getElementById('plannerWorkloadTotal');
  const termSummaryList = document.getElementById('plannerTermSummary');
  const statusSummaryList = document.getElementById('plannerStatusSummary');
  const plannerAlerts = document.getElementById('plannerAlerts');
  const plannerChangeSummary = document.getElementById('plannerChangeSummary');
  const plannerUndo = document.getElementById('plannerUndo');
  const totalInput = form ? form.querySelector('#totalCreditsInput') : null;
  const targetSelect = form ? form.querySelector('#targetClassSelect') : null;
  const submitBtn = form ? form.querySelector('[data-planner-recalc]') : null;
  const plannerStatus = document.getElementById('plannerSaveStatus');
  const WORKLOAD_WARN_THRESHOLD = 40;
  const MAX_MODULE_CREDITS = 60;
  const MAX_WORKLOAD = 200;
  const MAX_TOTAL_CREDITS = 360;
  let lastPlanSnapshot = null;
  let lastRemoved = null;

  const deadlinesTableBody = document.querySelector('#plannedDeadlinesTable tbody');
  const deadlinesTableWrapper = document.querySelector('#plannedDeadlinesTable')?.closest('.table-scroll');
  const addDeadlineBtn = document.getElementById('addFutureDeadlineBtn');
  const deadlinesStatus = document.getElementById('futureDeadlinesStatus');
  let deadlineStatusTimer;

  if (!form || !modulesTableBody) {
    return;
  }
  if (plannerAlerts) {
    plannerAlerts.setAttribute('aria-live', 'assertive');
  }

  function collectRowData(row) {
    const inputs = row.querySelectorAll('input, select');
    return {
      name: inputs[0]?.value?.trim() || '',
      credits: safeNumber(inputs[1]?.value, 0),
      grade: inputs[2]?.value === '' ? null : safeNumber(inputs[2]?.value, null),
      term: inputs[3]?.value || TERM_OPTIONS[0],
      category: inputs[4]?.value || CATEGORY_OPTIONS[0],
      status: inputs[5]?.value || STATUS_OPTIONS[0],
      workload: inputs[6]?.value === '' ? null : safeNumber(inputs[6]?.value, 0),
    };
  }

  function collectDeadlineRow(row) {
    const inputs = row.querySelectorAll('input');
    return {
      title: inputs[0]?.value?.trim() || '',
      due_date: inputs[1]?.value || '',
      weight: inputs[2]?.value === '' ? null : safeNumber(inputs[2]?.value, null),
      module: inputs[3]?.value?.trim() || '',
    };
  }

  function queueUndo(type, data) {
    if (!plannerUndo) return;
    lastRemoved = { type, data };
    plannerUndo.innerHTML = '';
    const btn = document.createElement('button');
    btn.className = 'btn tertiary small';
    btn.type = 'button';
    btn.textContent = 'Undo last delete';
    btn.addEventListener('click', () => {
      if (!lastRemoved) return;
      if (lastRemoved.type === 'module') addModuleRow(lastRemoved.data);
      if (lastRemoved.type === 'deadline') addDeadlineRow(lastRemoved.data);
      recalcTargetPlan();
      lastRemoved = null;
      plannerUndo.textContent = '';
    });
    plannerUndo.appendChild(btn);
    setTimeout(() => {
      if (lastRemoved) {
        lastRemoved = null;
        plannerUndo.textContent = '';
      }
    }, 6000);
  }

  const urls = boot.urls || {};

  const scheduleRecalc = debounce(() => recalcTargetPlan(), 400);
  const scheduleModuleSync = debounce(() => syncModules(), 600);
  const scheduleDeadlineSync = debounce(() => syncDeadlines(), 600);

  (boot.plannedModules || []).forEach(addModuleRow);
  (boot.deadlines || []).forEach(addDeadlineRow);
  recalcModuleSummary();
  recalcTargetPlan();

  addModuleBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    addModuleRow();
    recalcModuleSummary();
    scheduleModuleSync();
  });

  addDeadlineBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    addDeadlineRow();
    scheduleDeadlineSync();
  });

  modulesTableBody.addEventListener('input', () => {
    recalcModuleSummary();
    scheduleModuleSync();
  });

  modulesTableBody.addEventListener('click', (event) => {
    if (event.target.matches('[data-remove-row]')) {
      event.preventDefault();
      const row = event.target.closest('tr');
      if (row) {
        const data = collectRowData(row);
        row.remove();
        queueUndo('module', data);
        recalcModuleSummary();
        scheduleModuleSync();
      }
    }
  });

  deadlinesTableBody?.addEventListener('input', () => {
    scheduleDeadlineSync();
  });

  deadlinesTableBody?.addEventListener('click', (event) => {
    if (event.target.matches('[data-remove-deadline]')) {
      event.preventDefault();
      const row = event.target.closest('tr');
      if (row) {
        const data = collectDeadlineRow(row);
        row.remove();
        queueUndo('deadline', data);
        scheduleDeadlineSync();
      }
    }
  });

  totalInput?.addEventListener('input', () => {
    recalcTargetPlan();
    scheduleRecalc();
  });

  targetSelect?.addEventListener('change', () => {
    recalcTargetPlan();
  });

  if (submitBtn) {
    submitBtn.addEventListener('click', (event) => {
      event.preventDefault();
      recalcTargetPlan();
    });
  }
  if (form) {
    form.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        recalcTargetPlan();
      }
    });
  }
  document.addEventListener('keydown', (event) => {
    const active = document.activeElement;
    if (event.key === 'Enter' && !event.shiftKey) {
      if (modulesTableBody.contains(active)) {
        event.preventDefault();
        addModuleRow();
        recalcModuleSummary();
        scheduleModuleSync();
      } else if (deadlinesTableBody && deadlinesTableBody.contains(active)) {
        event.preventDefault();
        addDeadlineRow();
        scheduleDeadlineSync();
      }
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      recalcTargetPlan();
    }
  });

  function recalcTargetPlan() {
    recalcModuleSummary();
    const modules = collectModuleData();
    const totalCredits = modules.reduce((sum, item) => sum + (item.credits || 0), 0);
    const average = computeWeightedAverage(modules);
    const workloadTotal = modules.reduce((sum, item) => sum + (item.workload || 0), 0);
    const fallbackGoal = Number(remainingDisplay?.dataset?.total || 120);
    const goalCredits = Math.max(60, Math.min(MAX_TOTAL_CREDITS, safeNumber(totalInput?.value, fallbackGoal)));
    const completed = Number(remainingDisplay?.dataset?.completed || 0);
    const remaining = Math.max(0, goalCredits - completed);
    const progress = goalCredits > 0 ? Math.min(100, (completed / goalCredits) * 100) : 0;

    if (creditsTotalEl) creditsTotalEl.textContent = totalCredits.toString();
    if (expectedAvgEl) expectedAvgEl.textContent = average === null ? '--' : `${average.toFixed(1)}%`;
    if (remainingDisplay) {
      remainingDisplay.dataset.total = goalCredits;
      remainingDisplay.textContent = remaining.toString();
    }
    if (progressBar) {
      progressBar.style.width = `${progress.toFixed(1)}%`;
      progressBar.setAttribute('aria-valuenow', progress.toFixed(1));
    }
    updateGoalDisplay();

    const snapshot = {
      totalCredits,
      goalCredits,
      completedCredits: completed,
      remainingCredits: remaining,
      expectedAverage: average,
      workloadTotal,
      progress,
    };
    renderPlannerAlerts(snapshot);
    renderPlannerChangeSummary(snapshot);
    lastPlanSnapshot = snapshot;
  }

  function addDeadlineRow(data = {}) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input type="text" placeholder="Deadline title" aria-label="Deadline title" class="planner-input" /></td>
      <td><input type="date" aria-label="Due date" class="planner-input planner-input--narrow" /></td>
      <td><input type="number" min="0" max="20" step="0.1" aria-label="Weight" class="planner-input planner-input--narrow" /></td>
      <td><input type="text" placeholder="Module name (optional)" aria-label="Module name" class="planner-input" /></td>
      <td class="text-right">
        <button type="button" class="btn secondary small" data-remove-deadline>Remove</button>
      </td>
    `;
    deadlinesTableBody?.appendChild(row);
    const titleInput = row.querySelector('input[type="text"]');
    const dateInput = row.querySelector('input[type="date"]');
    const weightInput = row.querySelector('input[type="number"]');
    const moduleInput = row.querySelectorAll('input[type="text"]')[1];
    if (titleInput) titleInput.value = data.title || '';
    if (dateInput) dateInput.value = data.due_date || '';
    if (weightInput) weightInput.value = data.weight ?? '';
    if (moduleInput) moduleInput.value = data.module || '';
  }

  function collectDeadlineData() {
    const rows = deadlinesTableBody ? Array.from(deadlinesTableBody.querySelectorAll('tr')) : [];
    return rows.map((row) => {
      const inputs = row.querySelectorAll('input');
      return {
        title: inputs[0]?.value?.trim() || '',
        due_date: inputs[1]?.value || '',
        weight: inputs[2]?.value === '' ? null : safeNumber(inputs[2]?.value, null),
        module: inputs[3]?.value?.trim() || '',
      };
    });
  }

  function setDeadlineStatus(text, tone = 'muted') {
    if (!deadlinesStatus) return;
    deadlinesStatus.textContent = text;
    deadlinesStatus.classList.remove('text-danger', 'text-success');
    if (tone === 'error') {
      deadlinesStatus.classList.add('text-danger');
    } else if (tone === 'success') {
      deadlinesStatus.classList.add('text-success');
    }
    clearTimeout(deadlineStatusTimer);
    if (text) {
      deadlineStatusTimer = setTimeout(() => {
        deadlinesStatus.textContent = '';
        deadlinesStatus.classList.remove('text-danger', 'text-success');
      }, 2000);
    }
  }

  async function syncDeadlines() {
    const url =
      urls.savePlannedDeadlines || urls.saveFutureDeadlines || urls.saveDeadlines || null;
    if (!url) return;
    const deadlines = collectDeadlineData();
    const spinnerTarget = addDeadlineBtn;
    if (spinnerTarget) toggleButtonLoading(spinnerTarget, true, 'Saving...');
    setDeadlineStatus('Saving...');
    deadlinesTableWrapper?.classList.add('is-saving');
    try {
      await postJSON(url, deadlines);
      setDeadlineStatus('Saved', 'success');
    } catch (error) {
      console.warn('PredictMyGrade: deadline sync failed', error);
      setDeadlineStatus('Save failed', 'error');
      if (window.showToast) {
        window.showToast('Unable to save deadlines right now.', 'error');
      }
    } finally {
      deadlinesTableWrapper?.classList.remove('is-saving');
      if (spinnerTarget) toggleButtonLoading(spinnerTarget, false, 'Add deadline');
    }
  }

  function updateGoalDisplay() {
    const fallback = Number.isFinite(boot.totalCredits) ? boot.totalCredits : 120;
    const goal = totalInput
      ? Math.max(60, Math.min(MAX_TOTAL_CREDITS, safeNumber(totalInput.value, fallback)))
      : fallback;
    const goalEl = document.getElementById('futureCreditsGoal');
    if (goalEl) {
      goalEl.textContent = goal.toString();
    }
  }

  function addModuleRow(data = {}) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input type="text" placeholder="Module name" aria-label="Module name" class="planner-input" /></td>
      <td><input type="number" min="0" max="${MAX_MODULE_CREDITS}" aria-label="Credits" class="planner-input planner-input--narrow" /></td>
      <td><input type="number" min="0" max="100" aria-label="Target percentage" class="planner-input planner-input--narrow" /></td>
      <td>
        <select data-field="term" class="planner-input planner-select" aria-label="Term">
          ${optionMarkup(TERM_OPTIONS, data.term)}
        </select>
      </td>
      <td>
        <select data-field="category" class="planner-input planner-select" aria-label="Category">
          ${optionMarkup(CATEGORY_OPTIONS, data.category)}
        </select>
      </td>
      <td>
        <select data-field="status" class="planner-input planner-select" aria-label="Status">
          ${optionMarkup(STATUS_OPTIONS, data.status)}
        </select>
      </td>
      <td><input data-field="workload" type="number" min="0" max="${MAX_WORKLOAD}" step="0.5" aria-label="Workload hours" class="planner-input planner-input--narrow" /></td>
      <td class="text-right">
        <button type="button" class="btn secondary small" data-remove-row>Remove</button>
      </td>
    `;
    modulesTableBody.appendChild(row);
    const nameInput = row.querySelector('input[type="text"]');
    const creditsInput = row.querySelector('input[type="number"]');
    if (nameInput) {
      nameInput.value = data.name || '';
    }
    if (creditsInput) {
      creditsInput.value = data.credits ?? '';
    }
    const gradeInput = row.querySelector('input[type="number"][max="100"]');
    if (gradeInput) {
      gradeInput.value = data.grade ?? '';
    }
    const workloadInput = row.querySelector('[data-field="workload"]');
    if (workloadInput) {
      workloadInput.value = data.workload ?? '';
    }
  }

  function collectModuleData() {
    return Array.from(modulesTableBody.querySelectorAll('tr')).map((row) => {
      const inputs = row.querySelectorAll('input, select');
      const rawCredits = safeNumber(inputs[1]?.value, 0);
      const credits = Math.max(0, Math.min(MAX_MODULE_CREDITS, rawCredits));
      const rawGrade = inputs[2]?.value === '' ? null : safeNumber(inputs[2]?.value, null);
      const grade = rawGrade === null ? null : Math.max(0, Math.min(100, rawGrade));
      const rawWorkload = inputs[6]?.value === '' ? null : safeNumber(inputs[6]?.value, 0);
      const workload =
        rawWorkload === null ? null : Math.max(0, Math.min(MAX_WORKLOAD, rawWorkload));
      return {
        name: inputs[0]?.value?.trim() || 'Module',
        credits,
        grade,
        term: inputs[3]?.value || TERM_OPTIONS[0],
        category: inputs[4]?.value || CATEGORY_OPTIONS[0],
        status: inputs[5]?.value || STATUS_OPTIONS[0],
        workload,
      };
    });
  }

  function recalcModuleSummary() {
    const modules = collectModuleData();
    const totalCredits = modules.reduce((sum, item) => sum + (item.credits || 0), 0);
    const average = computeWeightedAverage(modules);
    const workloadTotal = modules.reduce((sum, item) => sum + (item.workload || 0), 0);
    const termTotals = modules.reduce((acc, item) => {
      const key = item.term || TERM_OPTIONS[0];
      if (!acc[key]) {
        acc[key] = { credits: 0, modules: 0, workload: 0 };
      }
      acc[key].credits += item.credits || 0;
      acc[key].modules += 1;
      acc[key].workload += item.workload || 0;
      return acc;
    }, {});
    const statusTotals = modules.reduce((acc, item) => {
      const key = item.status || STATUS_OPTIONS[0];
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    if (creditsTotalEl) {
      creditsTotalEl.textContent = totalCredits.toString();
    }
    if (expectedAvgEl) {
      expectedAvgEl.textContent = average === null ? '--' : `${average.toFixed(1)}%`;
    }
    if (workloadTotalEl) {
      workloadTotalEl.textContent = formatHours(workloadTotal);
    }
    if (termSummaryList) {
      termSummaryList.innerHTML = '';
      const entries = Object.entries(termTotals);
      if (!entries.length) {
        const li = document.createElement('li');
        li.className = 'muted';
        li.textContent = 'Add modules to see per-term planning stats.';
        termSummaryList.appendChild(li);
      } else {
        entries.forEach(([term, data]) => {
          const li = document.createElement('li');
          const workloadValue = data.workload.toFixed(1);
          li.innerHTML = `<strong>${term}</strong> &mdash; ${data.credits} credits, ${data.modules} modules, ${workloadValue.endsWith('.0') ? workloadValue.slice(0, -2) : workloadValue} hrs`;
          termSummaryList.appendChild(li);
        });
      }
    }
    if (statusSummaryList) {
      statusSummaryList.innerHTML = '';
      const entries = Object.entries(statusTotals);
      if (!entries.length) {
        const li = document.createElement('li');
        li.className = 'muted';
        li.textContent = 'Statuses will appear once modules are added.';
        statusSummaryList.appendChild(li);
      } else {
        entries.forEach(([status, count]) => {
          const li = document.createElement('li');
          li.innerHTML = `<strong>${status}</strong><span>${count}</span>`;
          statusSummaryList.appendChild(li);
        });
      }
    }
  }

  function renderPlannerAlerts(snapshot) {
    if (!plannerAlerts) return;
    const messages = [];
    if (snapshot.totalCredits < snapshot.goalCredits) {
      messages.push(
        `Planned credits (${snapshot.totalCredits}) are below your goal (${snapshot.goalCredits}). Add modules or raise targets.`,
      );
    }
    if (snapshot.workloadTotal > WORKLOAD_WARN_THRESHOLD) {
      messages.push(`Workload is high at ${formatHours(snapshot.workloadTotal)} hrs. Spread sessions out.`);
    }
    if (snapshot.expectedAverage === null) {
      messages.push('Add target percentages to estimate your expected average.');
    }
    if (!messages.length) {
      plannerAlerts.textContent = 'Planner is on track.';
      plannerAlerts.classList.remove('text-danger');
      return;
    }
    plannerAlerts.innerHTML = messages.map((msg) => `<div>${msg}</div>`).join('');
    plannerAlerts.classList.add('text-danger');
  }

  function renderPlannerChangeSummary(snapshot) {
    if (!plannerChangeSummary) return;
    if (!lastPlanSnapshot) {
      plannerChangeSummary.textContent = 'Plan recalculated with latest inputs.';
      return;
    }
    const deltas = [];
    const creditDelta = snapshot.totalCredits - lastPlanSnapshot.totalCredits;
    if (creditDelta !== 0) {
      deltas.push(`Credits ${creditDelta > 0 ? 'up' : 'down'} ${Math.abs(creditDelta)}`);
    }
    const workloadDelta = snapshot.workloadTotal - lastPlanSnapshot.workloadTotal;
    if (Math.abs(workloadDelta) >= 0.1) {
      deltas.push(`Workload ${workloadDelta > 0 ? 'up' : 'down'} ${formatHours(Math.abs(workloadDelta))} hrs`);
    }
    const averageDelta =
      snapshot.expectedAverage !== null && lastPlanSnapshot.expectedAverage !== null
        ? snapshot.expectedAverage - lastPlanSnapshot.expectedAverage
        : 0;
    if (averageDelta !== 0) {
      deltas.push(`Expected average ${averageDelta > 0 ? 'up' : 'down'} ${Math.abs(averageDelta).toFixed(1)}%`);
    }
    plannerChangeSummary.textContent = deltas.length
      ? `Changes: ${deltas.join('; ')}.`
      : 'No changes since the last recalculation.';
  }

  function setPlannerStatus(text, tone = 'muted') {
    if (!plannerStatus) return;
    plannerStatus.textContent = text;
    plannerStatus.classList.remove('text-danger', 'text-success');
    if (tone === 'success') plannerStatus.classList.add('text-success');
    if (tone === 'error') plannerStatus.classList.add('text-danger');
  }

  async function syncModules() {
    if (!urls.saveFutureModules) return;
    const modules = collectModuleData();
    modulesTableWrapper?.classList.add('is-saving');
    setPlannerStatus('Saving...');
    try {
      const data = await postJSON(urls.saveFutureModules, modules);
      if (data?.term_summary && termSummaryList) {
        termSummaryList.innerHTML = '';
        if (Array.isArray(data.term_summary) && data.term_summary.length) {
          data.term_summary.forEach((item) => {
            const li = document.createElement('li');
            const workloadValue = Number(item.workload ?? 0).toFixed(1);
            li.innerHTML = `<strong>${item.term}</strong> &mdash; ${item.credits} credits, ${item.modules} modules, ${workloadValue.endsWith('.0') ? workloadValue.slice(0, -2) : workloadValue} hrs`;
            termSummaryList.appendChild(li);
          });
        }
      }
      setPlannerStatus('Saved', 'success');
      if (window.showToast) {
        window.showToast('Modules saved.', 'success');
      }
    } catch (error) {
      console.warn('PredictMyGrade: module sync failed', error);
      if (window.showToast) {
        window.showToast('Unable to save modules right now.', 'error');
      }
      setPlannerStatus('Save failed', 'error');
    } finally {
      modulesTableWrapper?.classList.remove('is-saving');
      setPlannerStatus('');
    }
  }
}
