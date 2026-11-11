(function (root) {
  'use strict';

  const COUNTERS = Object.freeze([
    { id: 'trait3', label: '素質3', cost: 0 },
    { id: 'enhancement2', label: '強化2', cost: 0 },
    { id: 'reroll', label: 'リロール(40)', cost: 40 },
    { id: 'note45', label: '音符(45)', cost: 45 },
    { id: 'note72', label: '音符(72)', cost: 72 },
    { id: 'note90', label: '音符(90)', cost: 90 },
    { id: 'note200', label: '音符(200)', cost: 200 },
    { id: 'note320', label: '音符(320)', cost: 320 },
    { id: 'note400', label: '音符(400)', cost: 400 },
  ].map(Object.freeze));

  function integer(value) {
    if (typeof value === 'string') {
      if (!/^\d+$/.test(value)) return null;
      value = Number(value);
    }
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }

  function createState() {
    return { target: 0, counts: Object.fromEntries(COUNTERS.map(({ id }) => [id, 0])) };
  }

  function total(state) {
    return COUNTERS.reduce((sum, { id, cost }) => sum + state.counts[id] * cost, 0);
  }

  function remaining(state) {
    return state.target - total(state);
  }

  function setCount(state, id, value) {
    const count = integer(value);
    if (count === null || !COUNTERS.some(counter => counter.id === id)) return state;
    const next = { ...state, counts: { ...state.counts, [id]: count } };
    return Number.isSafeInteger(total(next)) ? next : state;
  }

  function adjustCount(state, id, delta) {
    if (!Number.isSafeInteger(delta) || !Object.hasOwn(state.counts, id)) return state;
    return setCount(state, id, Math.max(0, state.counts[id] + delta));
  }

  function setTarget(state, value) {
    const target = integer(value);
    return target === null ? state : { ...state, target };
  }

  function resetCounts(state) {
    return { ...createState(), target: state.target };
  }

  function restoreState(value) {
    let state = createState();
    if (!value || typeof value !== 'object') return state;
    state = setTarget(state, value.target);
    if (!value.counts || typeof value.counts !== 'object') return state;
    for (const { id } of COUNTERS) state = setCount(state, id, value.counts[id]);
    return state;
  }

  const api = Object.freeze({ COUNTERS, createState, setCount, adjustCount, setTarget, resetCounts, total, remaining, restoreState });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.StarTowerCounter = api;
})(globalThis);
