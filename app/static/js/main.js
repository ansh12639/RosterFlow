// RosterFlow client-side helpers (progressive enhancement – every action is a normal form POST).
(function () {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;

  // 1. CSRF: add the token to every POST form.
  document.querySelectorAll('form').forEach((form) => {
    if ((form.method || '').toLowerCase() === 'post' && token && !form.querySelector('input[name="csrf_token"]')) {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = 'csrf_token'; input.value = token;
      form.appendChild(input);
    }
  });

  // 2. Roster grid: click a cell to edit that employee-day.
  const dialog = document.getElementById('cell-dialog');
  if (dialog) {
    document.querySelectorAll('td.cell.editable').forEach((cell) => {
      cell.addEventListener('click', () => {
        const form = dialog.querySelector('form');
        form.employee_id.value = cell.dataset.emp;
        form.date.value = cell.dataset.date;
        form.status.value = cell.dataset.status === 'UNASSIGNED' ? 'WORKING' : cell.dataset.status;
        form.note.value = '';
        const d = new Date(cell.dataset.date + 'T00:00:00');
        dialog.querySelector('[data-title]').textContent = `${cell.dataset.name} · ${d.toDateString()}`;
        dialog.querySelector('[data-current]').textContent =
          `Currently: ${cell.dataset.status.replace('_', ' ').toLowerCase()}${cell.dataset.note ? ' – ' + cell.dataset.note : ''}`;
        dialog.showModal();
      });
    });
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  }

  // 3. "Explain this" – AI (or rule-based) explanation of a conflict.
  document.querySelectorAll('[data-explain]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const box = btn.closest('.conflict').querySelector('.ai-box');
      box.hidden = false; box.textContent = 'Thinking…'; btn.disabled = true;
      try {
        const res = await fetch(btn.dataset.explain, { method: 'POST', headers: { 'X-CSRFToken': token } });
        const data = await res.json();
        box.textContent = data.explanation + (data.source === 'claude' ? '\n— explained by Claude' : '\n— rule-based explanation (no AI key configured)');
      } catch (e) {
        box.textContent = 'Could not load an explanation right now.';
      } finally { btn.disabled = false; }
    });
  });

  // 4. Working-rule form: show per-day inputs only for the custom schedule.
  document.querySelectorAll('[data-preset-toggle]').forEach((select) => {
    const form = select.closest('form');
    const sync = () => {
      const custom = select.value === 'CUSTOM';
      form.querySelectorAll('[data-custom-only]').forEach((el) => (el.hidden = !custom));
      form.querySelectorAll('[data-preset-only]').forEach((el) => (el.hidden = custom));
    };
    select.addEventListener('change', sync); sync();
  });
})();
