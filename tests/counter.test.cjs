const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createState, setCount, adjustCount, setTarget, resetCounts, total, remaining, restoreState, researchUsage } = require('../dist/counter.js');

test('all seven weighted counters contribute their specified cost; record counters do not', () => {
  let state = createState();
  const fixture = { trait3: 9, enhancement2: 8, reroll: 2, note45: 1, note72: 2, note90: 3, note200: 4, note320: 5, note400: 6 };
  for (const [id, count] of Object.entries(fixture)) state = setCount(state, id, count);
  assert.equal(total(state), 5339);
});

test('changing one counter preserves the others and decrement stops at zero', () => {
  let state = setCount(createState(), 'trait3', 3);
  state = adjustCount(state, 'reroll', 1);
  assert.equal(state.counts.trait3, 3);
  assert.equal(state.counts.reroll, 1);
  assert.equal(state.counts.note45, 0);
  state = adjustCount(state, 'reroll', -1);
  state = adjustCount(state, 'reroll', -1);
  assert.equal(state.counts.reroll, 0);
});

test('one reset zeros every counter while keeping the target', () => {
  let state = setTarget(createState(), 2000);
  for (const id of Object.keys(state.counts)) state = setCount(state, id, 7);
  state = resetCounts(state);
  assert.equal(state.target, 2000);
  assert.deepEqual(Object.values(state.counts), [0, 0, 0, 0, 0, 0, 0, 0, 0]);
  assert.equal(total(state), 0);
  assert.equal(remaining(state), 2000);
});

test('remaining is target minus total including an exact goal and overshoot', () => {
  let state = setCount(setTarget(createState(), 100), 'note45', 2);
  assert.equal(remaining(state), 10);
  state = setTarget(state, 90);
  assert.equal(remaining(state), 0);
  state = setTarget(state, 80);
  assert.equal(remaining(state), -10);
});

test('invalid inputs cannot corrupt counts, target, or the weighted total', () => {
  const state = setCount(setTarget(createState(), 1000), 'note400', 2);
  for (const bad of [-1, 1.5, '', '3e2', 'NaN', Infinity, Number.MAX_SAFE_INTEGER + 1, null]) {
    assert.deepEqual(setCount(state, 'note400', bad), state);
    assert.deepEqual(setTarget(state, bad), state);
  }
  assert.deepEqual(setCount(state, 'note400', Number.MAX_SAFE_INTEGER), state);
  assert.deepEqual(setCount(state, '__proto__', 1), state);
  assert.equal(setCount(state, 'note45', '12').counts.note45, 12);
  assert.equal(setTarget(state, '0').target, 0);
});

test('restoring saved data keeps valid fields and safely defaults malformed data', () => {
  const saved = setCount(setTarget(createState(), 1234), 'note72', 5);
  assert.deepEqual(restoreState(JSON.parse(JSON.stringify(saved))), saved);
  assert.deepEqual(restoreState(null), createState());
  assert.deepEqual(restoreState({ target: -10, counts: { note72: -5 } }), createState());
  const partial = restoreState({ target: 500, counts: { note72: 2, note45: 'oops' } });
  assert.equal(total(partial), 144);
  assert.equal(remaining(partial), 356);
  assert.equal(total(restoreState({ counts: { note400: Number.MAX_SAFE_INTEGER } })), 0);
});

test('research counters start with ten Lv3 acquisitions and five double upgrades remaining', () => {
  assert.deepEqual(researchUsage?.(createState(), 'trait3'), { used: 0, limit: 10, remaining: 10, excess: 0 });
  assert.deepEqual(researchUsage?.(createState(), 'enhancement2'), { used: 0, limit: 5, remaining: 5, excess: 0 });
});

test('research usage deducts actual selections and reset restores all uses', () => {
  let state = setCount(setCount(createState(), 'trait3', 4), 'enhancement2', 5);
  assert.deepEqual(researchUsage?.(state, 'trait3'), { used: 4, limit: 10, remaining: 6, excess: 0 });
  assert.deepEqual(researchUsage?.(state, 'enhancement2'), { used: 5, limit: 5, remaining: 0, excess: 0 });
  state = resetCounts(state);
  assert.deepEqual(researchUsage?.(state, 'trait3'), { used: 0, limit: 10, remaining: 10, excess: 0 });
  assert.deepEqual(researchUsage?.(state, 'enhancement2'), { used: 0, limit: 5, remaining: 5, excess: 0 });
});

test('research limits preserve older saved counts and report excess without negative uses', () => {
  const state = restoreState({ target: 1200, counts: { trait3: 12, enhancement2: 8, note72: 2 } });
  assert.deepEqual(researchUsage?.(state, 'trait3'), { used: 12, limit: 10, remaining: 0, excess: 2 });
  assert.deepEqual(researchUsage?.(state, 'enhancement2'), { used: 8, limit: 5, remaining: 0, excess: 3 });
  assert.equal(state.counts.enhancement2, 8);
  assert.equal(state.target, 1200);
  assert.equal(total(state), 144);
});

test('purchases, rerolls and unknown IDs have no research usage limit', () => {
  assert.equal(researchUsage?.(createState(), 'note90'), null);
  assert.equal(researchUsage?.(createState(), 'reroll'), null);
  assert.equal(researchUsage?.(createState(), '__proto__'), null);
});
