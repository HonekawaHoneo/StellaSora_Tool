(() => {
  'use strict';
  const params = new URLSearchParams(location.search);
  const scenario = params.get('scenario') || 'normal';
  const counts = { trait3: 7, enhancement2: 3, reroll: 2, note90: 1, note72: 0, note45: 0, note400: 0, note320: 0, note200: 0 };
  let target = 500;
  if (scenario === 'limits') { counts.trait3 = 10; counts.enhancement2 = 5; }
  if (scenario === 'reached') { counts.reroll = 8; counts.note90 = 2; }
  if (scenario === 'over') { counts.reroll = 10; counts.note90 = 2; counts.trait3 = 11; counts.enhancement2 = 6; }
  if (scenario === 'unset') target = 0;
  let state = { target, counts };
  if (params.has('state')) {
    try { state = JSON.parse(params.get('state')); } catch (_) { /* Keep the selected fixture. */ }
  }
  window.mockState = state;
  let initialized = false;
  Object.defineProperty(window, 'localStorage', { value: {
    getItem: () => JSON.stringify(window.mockState),
    setItem: (_, value) => {
      window.mockState = JSON.parse(value);
      const report = initialized;
      initialized = true;
      queueMicrotask(() => {
        window.dispatchEvent(new Event('mock-state-change'));
        if (report && parent !== window) parent.postMessage({ type: 'stella-mock-state', state: window.mockState }, location.origin);
      });
    },
  } });
})();
