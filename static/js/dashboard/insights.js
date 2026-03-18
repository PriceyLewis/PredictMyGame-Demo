import {
  requestJSON,
  startProgress,
  endProgress,
  toggleButtonLoading,
  postJSON,
} from './helpers.js';
function normaliseFeedback(feedback) {
  if (!feedback || typeof feedback !== 'object') {
    return { helpful: 0, not_helpful: 0, user_rating: 0 };
  }
  return {
    helpful: Number(feedback.helpful || 0),
    not_helpful: Number(feedback.not_helpful || 0),
    user_rating: Number(feedback.user_rating || 0),
  };
}
function formatImpact(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return '';
  if (score >= 0.75) return 'High impact';
  if (score >= 0.5) return 'Medium impact';
  return 'Support insight';
}
function buildChips(insight) {
  const chips = [];
  const impact = formatImpact(insight.impact_score);
  if (impact) chips.push(impact);
  if (insight.tag) chips.push(insight.tag);
  return chips;
}
function renderInsight(listItem, insight) {
  const feedback = normaliseFeedback(insight.feedback);
  const userRating = feedback.user_rating;
  listItem.dataset.insightId = insight.id;
  listItem.dataset.userRating = String(userRating);
  listItem.innerHTML = '';
  const title = document.createElement('div');
  title.className = 'insight-title';
  title.textContent = insight.title || 'AI Insight';
  listItem.appendChild(title);
  if (insight.summary) {
    const summary = document.createElement('p');
    summary.textContent = insight.summary;
    listItem.appendChild(summary);
  }
  const chips = buildChips(insight);
  if (chips.length) {
    const tag = document.createElement('span');
    tag.className = 'insight-tag';
    tag.textContent = chips.join(' | ');
    listItem.appendChild(tag);
  }
  const feedbackWrap = document.createElement('div');
  feedbackWrap.className = 'insight-feedback';
  feedbackWrap.setAttribute('role', 'group');
  feedbackWrap.setAttribute('aria-label', 'Rate this insight');
  const helpfulBtn = document.createElement('button');
  helpfulBtn.type = 'button';
  helpfulBtn.className = 'insight-vote';
  helpfulBtn.dataset.feedback = '1';
  helpfulBtn.dataset.insightId = insight.id;
  helpfulBtn.innerHTML = '<i class="fa-solid fa-thumbs-up"></i> <span class="count"></span>';
  feedbackWrap.appendChild(helpfulBtn);
  const notHelpfulBtn = document.createElement('button');
  notHelpfulBtn.type = 'button';
  notHelpfulBtn.className = 'insight-vote';
  notHelpfulBtn.dataset.feedback = '-1';
  notHelpfulBtn.dataset.insightId = insight.id;
  notHelpfulBtn.innerHTML = '<i class="fa-solid fa-thumbs-down"></i> <span class="count"></span>';
  feedbackWrap.appendChild(notHelpfulBtn);
  listItem.appendChild(feedbackWrap);
  updateFeedbackState(listItem, feedback);
}
function updateFeedbackState(listItem, feedback = {}) {
  if (!listItem) return;
  const totals = normaliseFeedback(feedback);
  const helpful = totals.helpful;
  const notHelpful = totals.not_helpful;
  const userRating = totals.user_rating;
  listItem.dataset.userRating = String(userRating);
  const helpfulBtn = listItem.querySelector('[data-feedback="1"]');
  if (helpfulBtn) {
    helpfulBtn.classList.toggle('active', userRating === 1);
    helpfulBtn.setAttribute('aria-pressed', userRating === 1 ? 'true' : 'false');
    const count = helpfulBtn.querySelector('.count');
    if (count) count.textContent = helpful;
  }
  const notHelpfulBtn = listItem.querySelector('[data-feedback="-1"]');
  if (notHelpfulBtn) {
    notHelpfulBtn.classList.toggle('active', userRating === -1);
    notHelpfulBtn.setAttribute('aria-pressed', userRating === -1 ? 'true' : 'false');
    const count = notHelpfulBtn.querySelector('.count');
    if (count) count.textContent = notHelpful;
  }
}
export default function initInsights(boot) {
  const ai = boot.ai || {};
  const list = document.getElementById('aiInsightsList');
  const refreshBtn = document.getElementById('aiInsightsRefresh');
  const freshness = document.getElementById('insightsRefreshed');
  const urls = boot.urls || {};
  const feedbackUrl = urls.aiInsightFeedback;
  let currentInsights = Array.isArray(ai.insights) ? ai.insights : [];
  if (!list) {
    return { updateLive: () => {}, refreshNow: () => {} };
  }
  const touchFreshness = () => {
    if (!freshness) return;
    const stamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    freshness.textContent = `Refreshed at ${stamp}`;
  };
  function render(insights) {
    const items = Array.isArray(insights) ? insights : [];
    currentInsights = items;
    list.innerHTML = '';
    if (!items.length) {
      const empty = document.createElement('li');
      empty.className = 'muted';
      empty.textContent = 'Insights will appear after the next analysis run.';
      list.appendChild(empty);
      return;
    }
    items.forEach((insight) => {
      const item = document.createElement('li');
      item.className = 'insight-item';
      renderInsight(item, insight);
      list.appendChild(item);
    });
    touchFreshness();
  }
  async function refreshInsights() {
    if (!urls.aiInsights) return;
    toggleButtonLoading(refreshBtn, true, 'Refreshing...');
    startProgress();
    try {
      const data = await requestJSON(urls.aiInsights);
      if (data?.insights) {
        render(data.insights);
      }
    } catch (error) {
      console.warn('PredictMyGrade: failed to refresh AI insights', error);
      if (window.showToast) {
        window.showToast('Unable to refresh insights right now.', 'error');
      }
    } finally {
      toggleButtonLoading(refreshBtn, false, 'Refresh');
      endProgress();
    }
  }
  async function sendFeedback(insightId, rating, listItem) {
    if (!feedbackUrl) return;
    try {
      startProgress();
      const data = await postJSON(feedbackUrl, { insight_id: insightId, rating });
      if (data?.feedback) {
        updateFeedbackState(listItem, data.feedback);
        if (window.showToast) {
          window.showToast('Thanks for the feedback!');
        }
      }
    } catch (error) {
      console.warn('PredictMyGrade: unable to record feedback', error);
      if (window.showToast) {
        window.showToast('Unable to record feedback right now.', 'error');
      }
    } finally {
      endProgress();
    }
  }
  list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-feedback]');
    if (!button) return;
    event.preventDefault();
    const insightId = Number(button.dataset.insightId);
    if (!insightId) return;
    const listItem = button.closest('li');
    if (!listItem) return;
    const currentRating = Number(listItem.dataset.userRating || 0);
    let rating = Number(button.dataset.feedback);
    if (rating === currentRating) {
      rating = 0;
    }
    sendFeedback(insightId, rating, listItem);
  });
  refreshBtn?.addEventListener('click', (event) => {
    event.preventDefault();
    refreshInsights();
  });
  render(currentInsights);
  return {
    updateLive(data) {
      if (!data) return;
      if (Array.isArray(data.ai_insights)) {
        render(data.ai_insights);
      } else if (Array.isArray(data)) {
        render(data);
      }
    },
    refreshNow() {
      refreshInsights();
    },
  };
}
