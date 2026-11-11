(function () {
  'use strict';

  const model = window.StarTowerCounter;
  const storageKey = 'stella-sora-star-tower-v1';
  const number = new Intl.NumberFormat('ja-JP');
  let state = model.createState();
  let storageAvailable = true;
  let toastTimer;

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved) state = model.restoreState(JSON.parse(saved));
  } catch (_) {
    // A malformed save or disabled storage must not prevent counting.
  }

  const target = document.getElementById('target');
  const totalOutput = document.getElementById('total');
  const remainingOutput = document.getElementById('remaining');
  const progress = document.getElementById('progress');
  const progressFill = document.getElementById('progress-fill');
  const progressLabel = document.getElementById('progress-label');
  const progressPercent = document.getElementById('progress-percent');
  const storageStatus = document.getElementById('storage-status');
  const cards = new Map();
  const groups = {
    record: document.getElementById('record-counters'),
    reroll: document.getElementById('reroll-counters'),
    note: document.getElementById('note-counters'),
  };
  const measureContext = document.createElement('canvas').getContext('2d');

  const iconFor = id => id === 'trait3' ? 'trait' : id === 'enhancement2' ? 'enhance' : id === 'reroll' ? 'reroll' : 'note';

  for (const counter of model.COUNTERS) {
    const { id, label, cost } = counter;
    const record = cost === 0;
    const card = document.createElement('article');
    card.className = 'counter-card' + (record ? ' record' : '') + (id === 'reroll' ? ' reroll' : '');
    card.dataset.id = id;
    card.setAttribute('aria-label', label);
    card.innerHTML = `
      <div class="card-heading">
        <h3><svg class="icon card-icon" aria-hidden="true"><use href="#icon-${iconFor(id)}"/></svg>${record ? label : id === 'reroll' ? 'リロール' : '音符'}</h3>
        <span class="unit-badge">${record ? '記録用' : '× ' + cost}</span>
      </div>
      <div class="counter-controls">
        <button class="count-button decrement" type="button" aria-label="${label}を1減らす"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12"/></svg></button>
        <input id="count-${id}" class="count-input" type="number" min="0" max="9007199254740991" step="1" inputmode="numeric" autocomplete="off" aria-label="${label}の回数" value="0">
        <button class="count-button increment" type="button" aria-label="${label}を1増やす"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12M10 4v12"/></svg></button>
      </div>
      <p class="card-subtotal">${record ? '合計に含めない' : '小計 0'}</p>`;
    const input = card.querySelector('input');
    const decrease = card.querySelector('.decrement');
    const increase = card.querySelector('.increment');
    const subtotal = card.querySelector('.card-subtotal');
    cards.set(id, { input, decrease, increase, subtotal });

    decrease.addEventListener('click', () => commit(model.adjustCount(state, id, -1)));
    increase.addEventListener('click', () => commit(model.adjustCount(state, id, 1)));
    input.addEventListener('input', () => {
      if (input.value === '') return;
      const next = model.setCount(state, id, input.value);
      if (next === state) {
        input.setAttribute('aria-invalid', 'true');
        return;
      }
      input.removeAttribute('aria-invalid');
      commit(next);
    });
    input.addEventListener('blur', () => {
      if (input.value === '') commit(model.setCount(state, id, 0));
      else if (input.getAttribute('aria-invalid') === 'true') showToast('回数は0以上の整数で入力してください');
      input.removeAttribute('aria-invalid');
      input.value = state.counts[id];
      render();
    });
    input.addEventListener('focus', () => input.select());
    input.addEventListener('keydown', event => { if (event.key === 'Enter') input.blur(); });
    groups[record ? 'record' : id === 'reroll' ? 'reroll' : 'note'].appendChild(card);
  }

  target.addEventListener('input', () => {
    if (target.value === '') return;
    const next = model.setTarget(state, target.value);
    if (next === state) { target.setAttribute('aria-invalid', 'true'); return; }
    target.removeAttribute('aria-invalid');
    commit(next);
  });
  target.addEventListener('focus', () => target.select());
  target.addEventListener('blur', () => {
    if (target.value === '') commit(model.setTarget(state, 0));
    else if (target.getAttribute('aria-invalid') === 'true') showToast('目標値は0以上の整数で入力してください');
    target.removeAttribute('aria-invalid');
    target.value = state.target;
    render();
  });
  target.addEventListener('keydown', event => { if (event.key === 'Enter') target.blur(); });

  document.getElementById('reset').addEventListener('click', () => {
    commit(model.resetCounts(state));
    showToast('すべてのカウンターをリセットしました');
  });

  function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2600);
  }

  function save() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
      storageAvailable = true;
    } catch (_) { storageAvailable = false; }
    if (storageAvailable) storageStatus.innerHTML = '<span class="status-dot"></span>このブラウザーに自動保存';
    else storageStatus.textContent = 'この環境では自動保存できません';
  }

  function commit(next) {
    state = next;
    save();
    render();
  }

  function fitNumber(element, text) {
    element.style.fontSize = '';
    if (!measureContext) return;
    const style = window.getComputedStyle(element);
    measureContext.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const width = measureContext.measureText(text).width;
    const available = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 4;
    if (available > 0 && width > available) element.style.fontSize = Math.max(8, parseFloat(style.fontSize) * available / width) + 'px';
  }

  function render() {
    const sum = model.total(state);
    const rest = model.remaining(state);
    const percent = state.target > 0 ? Math.min(100, sum / state.target * 100) : 0;
    totalOutput.textContent = number.format(sum);
    remainingOutput.textContent = number.format(rest);
    if (document.activeElement !== target) target.value = state.target;
    totalOutput.classList.toggle('long', number.format(sum).length > 8);
    remainingOutput.classList.toggle('long', number.format(rest).length > 8);
    target.classList.toggle('long', String(state.target).length > 7);
    remainingOutput.parentElement.classList.toggle('over', state.target > 0 && rest <= 0);
    progressFill.style.width = percent + '%';
    progress.setAttribute('aria-valuenow', Math.round(percent));
    progress.setAttribute('aria-valuetext', state.target > 0 ? Math.floor(percent) + '%' : '目標未設定');
    progressPercent.textContent = state.target > 0 ? Math.floor(percent) + '%' : '—';
    progressLabel.textContent = state.target === 0 ? '目標値を設定してはじめましょう' : rest > 0 ? '目標まで あと ' + number.format(rest) : rest === 0 ? '目標に到達しました' : '目標を ' + number.format(-rest) + ' 超えています';
    progress.parentElement.classList.toggle('complete', state.target > 0 && rest <= 0);

    for (const { id, cost } of model.COUNTERS) {
      const { input, decrease, subtotal } = cards.get(id);
      const count = state.counts[id];
      if (document.activeElement !== input) input.value = count;
      input.classList.toggle('long', String(count).length > 4);
      input.parentElement.classList.toggle('wide-number', String(count).length > 5);
      fitNumber(input, input.value || '0');
      decrease.disabled = count === 0;
      if (cost > 0) {
        subtotal.textContent = '小計 ' + number.format(count * cost);
        subtotal.classList.toggle('has-value', count > 0);
      }
    }
    fitNumber(target, target.value || '0');
    fitNumber(totalOutput, totalOutput.textContent);
    fitNumber(remainingOutput, remainingOutput.textContent);
  }

  window.addEventListener('resize', render);
  save();
  render();
})();
