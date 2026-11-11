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
    90: document.getElementById('note-counters-90'),
    400: document.getElementById('note-counters-400'),
  };
  const noteFamilies = [
    { base: 90, ids: ['note90', 'note72', 'note45'] },
    { base: 400, ids: ['note400', 'note320', 'note200'] },
  ];
  const presentation = new Map(noteFamilies.flatMap(({ base, ids }) => ids.map(id => [id, base])));
  const counterById = new Map(model.COUNTERS.map(counter => [counter.id, counter]));
  const displayCounters = [
    ...model.COUNTERS.filter(counter => !presentation.has(counter.id)),
    ...noteFamilies.flatMap(({ ids }) => ids.map(id => counterById.get(id))),
  ];
  const measureContext = document.createElement('canvas').getContext('2d');

  const iconFor = id => id === 'trait3' ? 'trait' : id === 'enhancement2' ? 'enhance' : id === 'reroll' ? 'reroll' : 'note';

  for (const counter of displayCounters) {
    const { id, label, cost } = counter;
    const record = cost === 0;
    const countLabel = record ? label + (id === 'trait3' ? 'の取得回数' : 'の使用回数') : id === 'reroll' ? '素質の再抽選回数' : label + 'の購入回数';
    const base = presentation.get(id);
    const discount = base ? Math.round((1 - cost / base) * 100) : 0;
    const card = document.createElement('article');
    card.className = 'counter-card ' + (record ? 'record' : id === 'reroll' ? 'reroll' : 'note-card');
    card.dataset.id = id;
    card.setAttribute('aria-label', label);
    const heading = record
      ? `<h3><svg class="icon card-icon" aria-hidden="true"><use href="#icon-${iconFor(id)}"/></svg>${label}</h3>`
      : base
        ? `<h4 class="note-price">${cost}<span>コイン</span></h4><span class="discount-badge discount-${discount}">${discount === 50 ? '半額' : discount ? discount + '%引き' : '通常'}</span>`
        : `<h3 class="reroll-price">${cost}<span>コイン / 回</span></h3>`;
    card.innerHTML = `
      <div class="card-heading">
        ${heading}
      </div>
      <div class="counter-controls">
        <button class="count-button decrement" type="button" aria-label="${countLabel}を1減らす"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12"/></svg></button>
        <input id="count-${id}" class="count-input" type="number" min="0" max="9007199254740991" step="1" inputmode="numeric" autocomplete="off" aria-label="${countLabel}"${record ? ' aria-describedby="research-condition"' : ''} value="0">
        <button class="count-button increment" type="button" aria-label="${countLabel}を1増やす"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12M10 4v12"/></svg></button>
      </div>
      <p class="card-subtotal${record ? ' research-remaining' : ''}">${record ? '' : '支出 0コイン'}</p>`;
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
    groups[record ? 'record' : id === 'reroll' ? 'reroll' : base].appendChild(card);
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
    else if (target.getAttribute('aria-invalid') === 'true') showToast('目標コインは0以上の整数で入力してください');
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
    progressLabel.textContent = state.target === 0 ? '目標コインを設定してはじめましょう' : rest > 0 ? '目標まで あと ' + number.format(rest) + 'コイン' : rest === 0 ? '目標コインに到達しました' : '目標を ' + number.format(-rest) + 'コイン超えています';
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
        subtotal.textContent = '支出 ' + number.format(count * cost) + 'コイン';
        subtotal.classList.toggle('has-value', count > 0);
      } else {
        const usage = model.researchUsage(state, id);
        subtotal.textContent = '残り' + number.format(usage.remaining) + '回 / 上限' + usage.limit + '回' + (usage.excess ? '（' + number.format(usage.excess) + '回超過）' : '');
        subtotal.classList.toggle('exceeded', usage.excess > 0);
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
