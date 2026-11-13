(() => {
  'use strict';
  const variant = new URLSearchParams(location.search).get('variant') || 'current';
  if (variant !== 'a' && variant !== 'b') return;
  document.body.classList.add('variant-' + variant);
  const main = document.querySelector('main');
  const summary = document.querySelector('.summary');
  const research = document.querySelector('.record-group');
  const spending = document.querySelector('.spending');
  const overview = document.createElement('div');
  overview.className = 'mock-overview';
  main.prepend(overview);
  overview.append(summary, research);
  if (variant === 'b') {
    const workspace = document.createElement('div');
    workspace.className = 'compact-workspace';
    main.insertBefore(workspace, spending);
    workspace.append(research, spending);
  }

  for (const id of ['trait3', 'enhancement2']) {
    const card = document.querySelector(`[data-id="${id}"]`);
    const role = document.createElement('span');
    role.className = 'used-count-label';
    role.textContent = id === 'trait3' ? '取得' : '使用';
    const operation = document.createElement('div');
    operation.className = 'used-count-operation';
    card.querySelector('.counter-controls').before(operation);
    operation.append(role, card.querySelector('.counter-controls'));
    const remaining = document.createElement('p');
    remaining.className = 'research-remaining';
    card.querySelector('.research-remaining').replaceWith(remaining);
    const number = document.createElement('strong');
    number.className = 'remaining-number';
    remaining.append('残り ', number, ' 回');
    const capacity = document.createElement('span');
    capacity.className = 'research-capacity';
    const limit = id === 'trait3' ? 10 : 5;
    capacity.textContent = '/ ' + limit;
    remaining.append(capacity);
    const excess = document.createElement('span');
    excess.className = 'research-excess';
    remaining.append(excess);
    if (variant === 'a') {
      const slots = document.createElement('div');
      slots.className = 'research-slots';
      slots.setAttribute('aria-hidden', 'true');
      for (let i = 0; i < limit; i++) slots.append(document.createElement('span'));
      card.append(slots);
    }
  }

  function updateResearch() {
    for (const id of ['trait3', 'enhancement2']) {
      const card = document.querySelector(`[data-id="${id}"]`);
      const usage = window.StarTowerCounter.researchUsage(window.mockState, id);
      card.querySelector('.remaining-number').textContent = usage.remaining;
      card.querySelector('.research-excess').textContent = usage.excess ? '超過 ' + usage.excess + '回' : '';
      card.classList.toggle('at-limit', usage.remaining === 0);
      card.classList.toggle('exceeded', usage.excess > 0);
      card.querySelectorAll('.research-slots span').forEach((slot, i) => slot.classList.toggle('available', i < usage.remaining));
    }
  }
  window.addEventListener('mock-state-change', updateResearch);
  updateResearch();
})();
