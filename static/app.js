const form = document.getElementById('taskForm');
const input = document.getElementById('taskInput');
const list = document.getElementById('taskList');
if (input) input.focus();

if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = input.value.trim();
    if (!title) return;
    const res = await fetch('/api/manifest', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ title })
    });
    if (res.ok) location.reload();
  });
}

if (list) {
  list.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('toggle')) return;
    const li = e.target.closest('.task');
    const id = li.dataset.id;
    const res = await fetch(`/api/task/${id}/toggle`, {method:'POST'});
    if (res.ok) location.reload();
  });
}

if (window.weeklyData) {
  const ctx = document.getElementById('weeklyChart');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: window.weeklyData.map(x => x.day),
      datasets: [{
        label: 'Completion %',
        data: window.weeklyData.map(x => x.pct),
        backgroundColor: '#6ea8fe'
      }]
    },
    options: { scales: { y: { beginAtZero: true, max: 100 } } }
  });
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js').catch(() => {});
}
