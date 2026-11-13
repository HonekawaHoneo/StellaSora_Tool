(() => {
  'use strict';
  const frames = [...document.querySelectorAll('iframe')];
  const scenario = document.getElementById('scenario');
  let device = 'mobile';
  let sharedState = null;

  function previewUrl(variant) {
    const url = new URL('preview.html', location.href);
    url.searchParams.set('variant', variant);
    url.searchParams.set('scenario', scenario.value);
    if (sharedState) url.searchParams.set('state', JSON.stringify(sharedState));
    return url;
  }

  function resizeFrames() {
    const width = device === 'mobile' ? 390 : 1280;
    const height = device === 'mobile' ? 720 : 800;
    for (const frame of frames) {
      const available = frame.parentElement.clientWidth;
      const scale = Math.min(1, available / width);
      frame.width = width;
      frame.height = height;
      frame.style.transform = `scale(${scale})`;
      frame.parentElement.style.height = Math.ceil(height * scale) + 'px';
    }
  }

  function refresh(except) {
    for (const frame of frames) {
      const url = previewUrl(frame.closest('[data-variant]').dataset.variant);
      frame.closest('.option').querySelector('.open-preview').href = url;
      if (frame !== except) frame.src = url;
    }
  }

  document.querySelectorAll('[data-device]').forEach(button => button.addEventListener('click', () => {
    device = button.dataset.device;
    document.body.classList.toggle('desktop', device === 'desktop');
    document.querySelectorAll('[data-device]').forEach(other => other.setAttribute('aria-pressed', other === button));
    resizeFrames();
  }));
  scenario.addEventListener('change', () => { sharedState = null; refresh(); });
  document.getElementById('restore').addEventListener('click', () => { sharedState = null; refresh(); });
  window.addEventListener('resize', resizeFrames);
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'stella-mock-state') return;
    const source = frames.find(frame => frame.contentWindow === event.source);
    if (!source) return;
    sharedState = event.data.state;
    refresh(source);
  });
  refresh();
  resizeFrames();
})();
