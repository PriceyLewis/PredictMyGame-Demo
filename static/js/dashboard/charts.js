import { requestJSON, formatPercent } from './helpers.js';

const charts = {};
const ChartLib = window.Chart || null;
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: {
    duration: 650,
    easing: 'easeOutQuart',
  },
  plugins: {},
};

const tooltipBase = {
  backgroundColor: 'rgba(20, 16, 40, 0.95)',
  titleColor: '#e9e5ff',
  bodyColor: '#cfc8ff',
  borderColor: 'rgba(124, 58, 237, 0.45)',
  borderWidth: 1,
  cornerRadius: 10,
  padding: 12,
  displayColors: false,
  callbacks: {},
};

function mergeOptions(overrides = {}) {
  const merged = { ...chartDefaults, ...overrides };
  merged.plugins = {
    ...(chartDefaults.plugins || {}),
    ...(overrides.plugins || {}),
  };
  return merged;
}

function toggleLegendItem(event, legendItem, chart) {
  const meta = chart.getDatasetMeta(legendItem.datasetIndex);
  if (!meta) return;
  meta.hidden = !meta.hidden;
  chart.update();
}

function readJSONScript(id) {
  const el = document.getElementById(id);
  if (!el) {
    return null;
  }
  try {
    const data = JSON.parse(el.textContent || 'null');
    el.remove();
    return data;
  } catch (error) {
    console.warn(`PredictMyGrade: failed to parse chart data for ${id}`, error);
    el.remove();
    return null;
  }
}

function parseDatasetJSON(value) {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch (error) {
    console.warn('PredictMyGrade: failed to parse dataset JSON', error);
    return null;
  }
}

function createCompareChart(ctx, averages) {
  if (!ChartLib || !ctx) return;
  const data = [
    averages.gcse || 0,
    averages.college || 0,
    averages.university || 0,
  ];
  charts.compare = new ChartLib(ctx, {
    type: 'bar',
    data: {
      labels: ['GCSE', 'College', 'University'],
      datasets: [{
        data,
        backgroundColor: ['#a78bfa', '#7c3aed', '#c084fc'],
        borderRadius: 6,
      }],
    },
    options: mergeOptions({
      plugins: {
        legend: { display: false, onClick: toggleLegendItem },
        tooltip: {
          ...tooltipBase,
          callbacks: {
            title: (items) => `Cohort: ${items[0]?.label ?? ''}`,
            label: (item) => `Average: ${formatPercent(item.raw)}`,
          },
        },
      },
      scales: { y: { beginAtZero: true, max: 100 } },
    }),
  });
}

function createTargetChart(ctx, averages, targetPlan) {
  if (!ChartLib || !ctx || !targetPlan || targetPlan.error) return;
  const dataset = [
    averages.university || 0,
    targetPlan.required_avg_remaining || 0,
    targetPlan.target_avg || 0,
  ];
  charts.target = new ChartLib(ctx, {
    type: 'bar',
    data: {
      labels: ['Current Avg', 'Required Remaining', 'Target Goal'],
      datasets: [{
        data: dataset,
        backgroundColor: [
          'rgba(124,58,237,0.7)',
          'rgba(250,204,21,0.8)',
          'rgba(34,197,94,0.8)',
        ],
        borderRadius: 10,
        barThickness: 30,
      }],
    },
    options: mergeOptions({
      indexAxis: 'y',
      plugins: {
        legend: { display: false, onClick: toggleLegendItem },
        tooltip: {
          ...tooltipBase,
          callbacks: {
            title: (items) => {
              const label = items[0]?.label || '';
              const descMap = {
                'Current Avg': 'Your current average across university modules.',
                'Required Remaining': 'Average needed on remaining work to hit your goal.',
                'Target Goal': 'Target average for your chosen classification.',
              };
              return `${label}${descMap[label] ? ` — ${descMap[label]}` : ''}`;
            },
            label: (item) => `Value: ${formatPercent(item.raw)}`,
          },
        },
      },
      scales: {
        x: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(124,58,237,0.1)' },
          ticks: { color: '#cfc8ff' },
        },
        y: { grid: { display: false }, ticks: { color: '#a78bfa', font: { weight: 'bold' } } },
      },
    }),
  });
  window.targetChartInstance = charts.target;
}

function createTimelineChart(ctx, timeline) {
  if (!ChartLib || !ctx || !timeline || !timeline.values || !timeline.values.length) return;
  const chart = new ChartLib(ctx, {
    type: 'line',
    data: {
      labels: timeline.labels,
      datasets: [{
        label: 'Average %',
        data: timeline.values,
        borderColor: '#a78bfa',
        backgroundColor: 'rgba(124,58,237,0.2)',
        borderWidth: 2,
        fill: true,
        tension: 0.35,
      }],
    },
    options: mergeOptions({
      plugins: {
        legend: { display: false, onClick: toggleLegendItem },
        tooltip: {
          ...tooltipBase,
          callbacks: {
            title: (items) => `Snapshot ${items[0]?.label ?? ''}`,
            label: (item) => `Average: ${formatPercent(item.raw)}`,
          },
        },
      },
      scales: { y: { beginAtZero: true, max: 100 } },
    }),
  });
  chart.$activeRange = null;
  charts.timeline = chart;
  updateTimelineDelta(timeline.values);
}

function createForecastChart(ctx, timeline, ai, summaryEl) {
  if (!ChartLib || !ctx || !timeline || !timeline.values || !timeline.values.length) return;

  const chart = new ChartLib(ctx, {
    type: 'line',
    data: {
      labels: timeline.labels.concat(['Next']),
      datasets: [{
        label: 'Predicted Avg %',
        data: timeline.values.concat([timeline.values[timeline.values.length - 1] || 0]),
        borderColor: '#22c55e',
        borderDash: [5, 4],
        borderWidth: 2,
        fill: false,
        tension: 0.35,
        pointBackgroundColor: timeline.values.concat([0]).map((_, idx, arr) => (idx === arr.length - 1 ? '#22c55e' : '#a78bfa')),
      }],
    },
    options: mergeOptions({
      plugins: {
        legend: { display: false, onClick: toggleLegendItem },
        tooltip: {
          ...tooltipBase,
          callbacks: {
            title: (items) => `Week ${items[0]?.label ?? ''}`,
            label: (item) => {
              const isPredicted = item.dataIndex === item.dataset.data.length - 1;
              const label = isPredicted ? 'Predicted' : 'Actual';
              return `${label}: ${formatPercent(item.raw)}`;
            },
          },
        },
      },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: 'rgba(124,58,237,0.1)' } },
        x: { grid: { display: false }, ticks: { color: '#a78bfa' } },
      },
    }),
  });

  chart.$updateForecast = (sourceTimeline, sourceAi = ai, targetSummary = summaryEl) => {
    if (!sourceTimeline?.values?.length) {
      return;
    }
    const values = [...sourceTimeline.values];
    const latest = values[values.length - 1];
    const previous = Number(values[values.length - 2]);
    const trend = Number.isNaN(previous) ? 0 : latest - previous;
    const predictedValue = sourceAi?.predictedAverage ?? latest + trend * 0.8;
    const predicted = Math.max(0, Math.min(100, Number(predictedValue)));
    const labels = (sourceTimeline.labels?.length === values.length
      ? sourceTimeline.labels
      : values.map((_, index) => `W${index + 1}`)).concat(['Next']);

    chart.data.labels = labels;
    chart.data.datasets[0].data = values.concat([predicted]);
    chart.data.datasets[0].pointBackgroundColor = chart.data.datasets[0].data.map((_, idx, arr) => (
      idx === arr.length - 1 ? '#22c55e' : '#a78bfa'
    ));
    chart.update('none');

    updateForecastSummary(targetSummary, {
      predicted,
      latest,
      diff: predicted - latest,
      confidence: sourceAi?.confidence,
      model: sourceAi?.model || sourceAi?.mode || sourceAi?.modelLabel,
    });
  };

  charts.forecast = chart;
  chart.$updateForecast(timeline, ai, summaryEl);
}

function createConfidenceTrendChart(ctx, labels = [], values = []) {
  if (!ChartLib || !ctx) return;
  const normalizedLabels =
    Array.isArray(labels) && labels.length
      ? labels
      : ['Confidence'];
  const fallbackValue =
    Array.isArray(values) && values.length ? Number(values[0]) : 75;
  const sanitizedValues =
    Array.isArray(values) && values.length
      ? values.map((value) => {
          const numeric = Number(value);
          return Number.isFinite(numeric) ? numeric : 0;
        })
      : normalizedLabels.map(() => fallbackValue);
  const chart = new ChartLib(ctx, {
    type: 'line',
    data: {
      labels: normalizedLabels,
      datasets: [
        {
          label: 'AI confidence',
          data: sanitizedValues,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.25)',
          borderWidth: 2,
          fill: true,
          tension: 0.35,
          pointRadius: 0,
        },
      ],
    },
    options: mergeOptions({
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipBase,
          callbacks: {
            title: () => 'AI confidence',
            label: (item) => formatPercent(item.raw),
          },
        },
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: '#cfc8ff' },
          grid: { color: 'rgba(124,58,237,0.15)' },
        },
        x: {
          grid: { color: 'rgba(124,58,237,0.05)' },
          ticks: { color: '#a78bfa' },
        },
      },
    }),
  });
  chart.$refreshConfidence = (nextLabels, nextValues) => {
    if (!Array.isArray(nextLabels) || !nextLabels.length) return;
    const sanitized =
      Array.isArray(nextValues) && nextValues.length
        ? nextValues.map((value) => {
            const numeric = Number(value);
            return Number.isFinite(numeric) ? numeric : 0;
          })
        : nextLabels.map(() => fallbackValue);
    chart.data.labels = nextLabels;
    chart.data.datasets[0].data = sanitized;
    chart.update('none');
  };
  charts.confidenceTrend = chart;
}

function createRadarChart(ctx, radar) {
  if (!ChartLib || !ctx || !radar || !radar.values || !radar.values.length) return;
  charts.radar = new ChartLib(ctx, {
    type: 'radar',
    data: {
      labels: radar.labels,
      datasets: [{
        label: 'Subject Averages',
        data: radar.values,
        borderColor: '#a78bfa',
        backgroundColor: 'rgba(124,58,237,0.2)',
        borderWidth: 2,
        fill: true,
      }],
    },
    options: mergeOptions({
      plugins: { legend: { display: false, onClick: toggleLegendItem } },
    }),
  });
}

function createSparkline(ctx, timeline) {
  if (!ChartLib || !ctx || !timeline || !timeline.values || !timeline.values.length) return;
  charts.spark = new ChartLib(ctx, {
    type: 'line',
    data: {
      labels: timeline.labels,
      datasets: [{
        data: timeline.values,
        borderColor: '#7c3aed',
        backgroundColor: 'rgba(124,58,237,0.15)',
        tension: 0.35,
        fill: true,
        borderWidth: 2,
        pointRadius: 0,
      }],
    },
    options: mergeOptions({
      plugins: { legend: { display: false, onClick: toggleLegendItem } },
      scales: { x: { display: false }, y: { display: false } },
    }),
  });
}

function createWeeklyActivityChart(canvas, data) {
  if (!ChartLib || !canvas || !data?.labels?.length) return;
  charts.weeklyActivity = new ChartLib(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{
        label: 'Activity',
        data: data.values || [],
        backgroundColor: 'rgba(124,58,237,0.35)',
        borderColor: '#7c3aed',
        borderWidth: 2,
        borderRadius: 6,
      }],
    },
    options: mergeOptions({
      plugins: { legend: { display: false, onClick: toggleLegendItem } },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0 },
        },
      },
    }),
  });
}

function updateTimelineDelta(values) {
  const deltaEl = document.getElementById('timelineDelta');
  if (!deltaEl) return;
  const icon = deltaEl.querySelector('i') || deltaEl.insertBefore(document.createElement('i'), deltaEl.firstChild);
  const textNode = deltaEl.querySelector('span') || deltaEl.appendChild(document.createElement('span'));
  const classes = ['positive', 'negative', 'neutral'];
  classes.forEach((cls) => deltaEl.classList.remove(cls));

  if (!values || values.length < 2) {
    deltaEl.classList.add('neutral');
    icon.className = 'fa-solid fa-minus';
    textNode.textContent = 'Trend data will appear after more snapshots.';
    return;
  }

  const latest = Number(values[values.length - 1]) || 0;
  const previous = Number(values[values.length - 2]) || 0;
  const diff = latest - previous;
  const formattedDiff = `${diff > 0 ? '+' : diff < 0 ? '' : ''}${diff.toFixed(1)} pts vs last snapshot`;

  if (diff > 0.1) {
    deltaEl.classList.add('positive');
    icon.className = 'fa-solid fa-arrow-trend-up';
    textNode.textContent = `${formattedDiff} — now ${latest.toFixed(1)}%.`;
  } else if (diff < -0.1) {
    deltaEl.classList.add('negative');
    icon.className = 'fa-solid fa-arrow-trend-down';
    textNode.textContent = `${formattedDiff} — now ${latest.toFixed(1)}%.`;
  } else {
    deltaEl.classList.add('neutral');
    icon.className = 'fa-solid fa-arrows-left-right';
    textNode.textContent = `Steady at ${latest.toFixed(1)}% compared to the previous snapshot.`;
  }
}

function initTimelineControls(timeline) {
  const chart = charts.timeline;
  if (!chart || !timeline?.labels?.length) return;

  const buttons = Array.from(document.querySelectorAll('[data-timeline-range]'));
  if (!buttons.length) return;

  const ranges = {
    '4': 4,
    '12': 12,
    '24': 24,
    all: Infinity,
  };

  let currentTimeline = timeline;

  function sliceTimeline(rangeKey) {
    const limit = ranges[rangeKey] ?? Infinity;
    const total = currentTimeline.values.length;
    const start = limit === Infinity ? 0 : Math.max(0, total - limit);
    return {
      labels: currentTimeline.labels.slice(start),
      values: currentTimeline.values.slice(start),
    };
  }

  function setActiveButton(rangeKey) {
    buttons.forEach((btn) => {
      const isActive = btn.dataset.timelineRange === rangeKey;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', String(isActive));
    });
  }

  function applyRange(rangeKey, updateButtons = true) {
    const slice = sliceTimeline(rangeKey);
    chart.data.labels = slice.labels;
    chart.data.datasets[0].data = slice.values;
    chart.update('none');
    updateTimelineDelta(slice.values);
    chart.$activeRange = rangeKey;
    if (updateButtons) {
      setActiveButton(rangeKey);
    }
  }

  chart.$applyTimelineSource = (nextTimeline) => {
    if (!nextTimeline?.labels?.length) {
      return;
    }
    currentTimeline = nextTimeline;
    const range = chart.$activeRange || buttons[0]?.dataset.timelineRange || 'all';
    applyRange(range, false);
  };

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      applyRange(btn.dataset.timelineRange, true);
    });
  });

  const initial = buttons.find((btn) => btn.classList.contains('active'))?.dataset.timelineRange
    || buttons[0]?.dataset.timelineRange
    || 'all';
  applyRange(initial, true);
}

function updateForecastSummary(el, { predicted, latest, diff, confidence, model }) {
  if (!el) return;
  if (!Number.isFinite(predicted) || !Number.isFinite(latest)) {
    el.textContent = 'Forecast insight will appear once enough historical data is available.';
    return;
  }

  const trendWord = diff > 0.1 ? 'above' : diff < -0.1 ? 'below' : 'in line with';
  const diffText = diff > 0.1 || diff < -0.1 ? ` (${diff > 0 ? '+' : ''}${diff.toFixed(1)} pts vs last)` : '';
  const confidenceText = Number.isFinite(confidence) ? ` Confidence: ${Math.round(confidence)}%.` : '';
  const modelText = model ? ` Model: ${model}.` : '';

  el.textContent = `Forecast: ${predicted.toFixed(1)}% - ${trendWord} the latest ${latest.toFixed(1)}%${diffText}.${confidenceText}${modelText}`;
}

let weeklyGoalsChart = null;
let weeklyGoalsUrls = null;

async function refreshWeeklyGoalsChart(urls) {
  if (!ChartLib) return;
  const targetUrls = urls || weeklyGoalsUrls;
  if (!targetUrls?.weeklyGoals) return;
  weeklyGoalsUrls = targetUrls;
  const canvas = document.getElementById('weeklyGoalsChart');
  if (!canvas) return;
  let data;
  try {
    data = await requestJSON(targetUrls.weeklyGoals);
  } catch (error) {
    console.warn('PredictMyGrade: weekly goals chart failed', error);
    return;
  }
  const labels = Array.isArray(data.labels) ? data.labels : [];
  if (!labels.length) return;
  const values = Array.isArray(data.values) ? data.values : [];
  const totals = Array.isArray(data.totals) ? data.totals : [];
  const completed = Array.isArray(data.completed) ? data.completed : [];
  if (weeklyGoalsChart) {
    weeklyGoalsChart.data.labels = labels;
    weeklyGoalsChart.data.datasets[0].data = values;
    weeklyGoalsChart.update('none');
    return;
  }
  weeklyGoalsChart = new ChartLib(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Goals Completed (%)',
        data: values,
        backgroundColor: 'rgba(124,58,237,0.4)',
        borderColor: '#7c3aed',
        borderWidth: 2,
        borderRadius: 6,
      }],
    },
    options: mergeOptions({
      plugins: {
        legend: { display: false, onClick: toggleLegendItem },
        tooltip: {
          callbacks: {
            label: (context) => {
              const index = context.dataIndex;
              const percent = context.parsed.y ?? context.parsed ?? 0;
              const total = totals[index] ?? 0;
              const done = completed[index] ?? 0;
              const percentText = `${percent}%`;
              if (!total) return percentText;
              return `${percentText} (${done}/${total} goals)`;
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: {
            callback: (value) => `${value}%`,
          },
        },
      },
    }),
  });
}

let habitChartInstance = null;
let habitUrls = null;

async function refreshHabitChart(urls) {
  if (!ChartLib) return;
  const targetUrls = urls || habitUrls;
  if (!targetUrls?.studyHabits) return;
  habitUrls = targetUrls;
  const canvas = document.getElementById('habitChart');
  if (!canvas) return;
  let data;
  try {
    data = await requestJSON(targetUrls.studyHabits);
  } catch (error) {
    console.warn('PredictMyGrade: habit chart failed', error);
    return;
  }
  const labels = Array.isArray(data.labels) ? data.labels : [];
  if (!labels.length) return;
  const hours = Array.isArray(data.hours) ? data.hours : [];
  if (habitChartInstance) {
    habitChartInstance.data.labels = labels;
    habitChartInstance.data.datasets[0].data = hours;
    habitChartInstance.update('none');
    return;
  }
  habitChartInstance = new ChartLib(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Study Hours',
        data: hours,
        borderColor: '#7c3aed',
        backgroundColor: 'rgba(124,58,237,0.2)',
        tension: 0.35,
        fill: true,
      }],
    },
    options: mergeOptions({
      plugins: { legend: { display: false, onClick: toggleLegendItem } },
      scales: { y: { beginAtZero: true } },
    }),
  });
}

export default function initCharts(boot) {
  if (!ChartLib) {
    console.warn('PredictMyGrade: Chart.js not available');
    return;
  }

  const averages = boot.averages || {};
  const targetPlan = boot.targetPlan || null;
  const timeline = boot.timeline || { labels: [], values: [] };
  const radar = boot.radar || { labels: [], values: [] };
  const weeklyActivity = readJSONScript('weekly-activity-data');
  const radarFromScript = readJSONScript('subject-radar-data');

  const compareCanvas = document.getElementById('compareChart');
  if (compareCanvas) {
    createCompareChart(compareCanvas.getContext('2d'), averages);
  }

  const targetCanvas = document.getElementById('targetChart');
  if (targetCanvas) {
    createTargetChart(targetCanvas.getContext('2d'), averages, targetPlan);
  }

  const timelineCanvas = document.getElementById('performanceChart');
  if (timelineCanvas) {
    createTimelineChart(timelineCanvas.getContext('2d'), timeline);
    initTimelineControls(timeline);
  }

  const forecastCanvas = document.getElementById('forecastChart');
  if (forecastCanvas) {
    const history = parseDatasetJSON(forecastCanvas.dataset.history) || timeline.values || [];
    const labels = history.length === timeline.labels.length && history.length
      ? timeline.labels
      : history.map((_, index) => `W${index + 1}`);
    const timelineForForecast = { labels, values: history.map((value) => Number(value)) };
    const summaryEl = document.getElementById('forecastSummary');
    const aiData = Object.assign({}, boot.ai, {
      predictedAverage: Number.isFinite(Number(forecastCanvas.dataset.prediction))
        ? Number(forecastCanvas.dataset.prediction)
        : boot.ai?.predictedAverage,
      confidence: Number.isFinite(Number(forecastCanvas.dataset.confidence))
        ? Number(forecastCanvas.dataset.confidence)
        : boot.ai?.confidence,
      model: forecastCanvas.dataset.model || boot.ai?.model || boot.ai?.mode || boot.ai?.modelLabel,
    });
    createForecastChart(forecastCanvas.getContext('2d'), timelineForForecast, aiData, summaryEl);
  }

  const confidenceCanvas = document.getElementById('confidenceTrend');
  if (confidenceCanvas) {
    const confidenceData = Array.isArray(boot.ai?.confidenceTrend)
      ? boot.ai.confidenceTrend
      : [];
    createConfidenceTrendChart(
      confidenceCanvas.getContext('2d'),
      timeline.labels,
      confidenceData,
    );
  }

  const radarCanvas = document.getElementById('subjectRadar');
  if (radarCanvas) {
    const radarData = radarFromScript || radar;
    createRadarChart(radarCanvas.getContext('2d'), radarData);
  }

  const sparkCanvas = document.getElementById('miniTrend');
  if (sparkCanvas) {
    createSparkline(sparkCanvas.getContext('2d'), timeline);
  }

  refreshWeeklyGoalsChart(boot.urls);
  refreshHabitChart(boot.urls);

  const weeklyCanvas = document.getElementById('weeklyChart');
  if (weeklyCanvas && weeklyActivity) {
    weeklyActivity.values = (weeklyActivity.values || []).map((value) => Number(value));
    createWeeklyActivityChart(weeklyCanvas, weeklyActivity);
  }
}

export function getChart(name) {
  return charts[name];
}

export { refreshWeeklyGoalsChart, refreshHabitChart };


