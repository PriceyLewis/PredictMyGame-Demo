export function getBootData() {
  if (window.__dashboardBootData) {
    return window.__dashboardBootData;
  }
  const el = document.getElementById("dashboard-boot");
  if (!el) {
    return (window.__dashboardBootData = {});
  }
  try {
    const data = el.textContent ? JSON.parse(el.textContent) : {};
    window.__dashboardBootData = data || {};
  } catch (error) {
    console.warn("PredictMyGrade: failed to parse dashboard boot data", error);
    window.__dashboardBootData = {};
  }
  return window.__dashboardBootData;
}