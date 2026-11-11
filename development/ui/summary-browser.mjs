// CodexEnvSet browser check. Verified with Windows Edge and Node 24.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { get } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { pathToFileURL } from 'node:url';

const edge = process.env.STELLA_EDGE_PATH || join(process.env['ProgramFiles(x86)'] || '', 'Microsoft/Edge/Application/msedge.exe');
const baseline = process.argv[2] === '--before';
const change = process.env.CODEXENVSET_CHANGE_ID;
const output = resolve(baseline ? process.argv[3] : process.env.CODEXENVSET_EVIDENCE_DIR);
const scenarios = [
  { id: 'mobile-320', width: 320, height: 720, mobile: true },
  { id: 'desktop-1280', width: 1280, height: 800, mobile: false },
];
const fixture = { counts: { reroll: 2, note90: 1 }, target: 500 };
const key = 'stella-sora-star-tower-v1';
const profileRoot = realpathSync(tmpdir());
const profile = mkdtempSync(join(profileRoot, 'stella-summary-edge-'));
const browser = spawn(edge, [
  '--headless', '--disable-gpu', '--no-first-run', '--remote-debugging-port=0',
  '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
let launchError;
let browserLog = '';
browser.stderr.on('data', data => { browserLog = (browserLog + data).slice(-3000); });
browser.on('error', error => { launchError = error; });
let socket;

async function waitFor(read, message) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (launchError) throw launchError;
    const value = await read();
    if (value) return value;
    await delay(100);
  }
  throw new Error(message);
}

async function connect() {
  const portFile = join(profile, 'DevToolsActivePort');
  const port = await waitFor(
    () => existsSync(portFile) && readFileSync(portFile, 'utf8').split(/\r?\n/)[0],
    'Edge did not expose DevTools',
  );
  const endpoint = 'http://127.0.0.1:' + port;
  function getJson(path) {
    return new Promise((resolve, reject) => {
      get(endpoint + path, { agent: false }, response => {
        let data = '';
        response.setEncoding('utf8');
        response.on('data', chunk => { data += chunk; });
        response.on('error', reject);
        response.on('end', () => {
          try { resolve(JSON.parse(data)); } catch (error) { reject(error); }
        });
      }).on('error', reject);
    });
  }
  const pages = await waitFor(() => getJson('/json/list').catch(() => null), 'Edge DevTools HTTP is unavailable');
  const version = await getJson('/json/version');
  socket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
  await once(socket, 'open');
  let nextId = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const response = JSON.parse(event.data);
    const entry = pending.get(response.id);
    if (!entry) return;
    pending.delete(response.id);
    if (response.error) entry.reject(new Error(response.error.message));
    else entry.resolve(response.result);
  });
  socket.addEventListener('close', event => {
    for (const entry of pending.values()) entry.reject(new Error('DevTools disconnected (' + event.code + ')'));
    pending.clear();
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId;
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error('DevTools timed out: ' + method));
    }, 6000);
    pending.set(id, {
      resolve: result => { clearTimeout(timeout); resolve(result); },
      reject: error => { clearTimeout(timeout); reject(error); },
    });
    socket.send(JSON.stringify({ id, method, params }));
  });
  return { send, version: version.Browser + ' / ' + version['User-Agent'].match(/Edg\/[\d.]+/)?.[0] };
}

function observe() {
  const find = selector => document.querySelector(selector);
  const box = selector => find(selector).getBoundingClientRect().toJSON();
  const style = selector => getComputedStyle(find(selector));
  const label = '.metric-target .metric-label';
  const target = find('#target');
  const labels = [...document.querySelectorAll('.metric-label')].map(element => element.textContent.trim());
  const rows = [...document.querySelectorAll('.metric')].map(element => element.getBoundingClientRect().top);
  const texts = [];
  const nodes = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  const visibility = { opacityProperty: true, visibilityProperty: true };
  for (let node = nodes.nextNode(); node; node = nodes.nextNode()) {
    if (node instanceof HTMLInputElement && node.checkVisibility(visibility)) {
      texts.push(node.value);
    } else if (node.nodeType === Node.TEXT_NODE && node.parentElement.checkVisibility(visibility)) {
      const value = node.textContent.replace(/\s+/g, ' ').trim();
      if (value) texts.push(value);
    }
  }
  function luminance(color) {
    const channels = color.match(/\d+(?:\.\d+)?/g).slice(0, 3).map(channel => Number(channel) / 255);
    const linear = channels.map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
  }
  function contrast(a, b) {
    const tones = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (tones[0] + 0.05) / (tones[1] + 0.05);
  }
  const surface = style('.spending').backgroundColor;
  const border = style('#target').borderBottomColor;
  const fill = style('#target').backgroundColor;
  const trackWidth = box('#progress').width;
  const progressRatio = trackWidth ? box('#progress-fill').width / trackWidth : 0;
  const spending = find('.spending');
  const spendingBox = box('.spending');
  const membership = ['.summary', '.reroll-group', '.notes-group'].every(selector => {
    const area = box(selector);
    return spending.contains(find(selector)) && area.left >= spendingBox.left && area.right <= spendingBox.right &&
      area.top >= spendingBox.top && area.bottom <= spendingBox.bottom;
  }) && spending.nextElementSibling === find('.record-group') && box('.record-group').top >= spendingBox.bottom;
  const indicatorContrast = Math.min(
    contrast(border, surface),
    contrast(style('.edit-icon').stroke, surface),
    contrast(border, fill === 'rgba(0, 0, 0, 0)' ? surface : fill),
  );
  return {
    texts, labels, indicatorContrast, progressRatio, spendingBox, membership,
    appColor: style('.app-shell').color,
    storageVisible: find('#storage-status').checkVisibility(),
    progressVisible: find('#progress').checkVisibility(),
    summaryRows: new Set(rows).size,
    summaryBox: box('.summary'),
    progressConsistent: find('#total').textContent === '170' && find('#remaining').textContent === '330' &&
      find('#progress-percent').textContent === '34%' && find('#progress').getAttribute('aria-valuenow') === '34' &&
      find('#progress-fill').style.width === '34%' && Math.abs(progressRatio - 0.34) < 0.001,
    labelSize: parseFloat(style(label).fontSize),
    labelLine: parseFloat(style(label).lineHeight),
    valueColor: style('#remaining').color,
    rowHeight: box('.metric-target').height,
    targetWidth: box('#target').width,
    targetHeight: box('#target').height,
    summaryInset: parseFloat(style('.spending').paddingLeft),
    noOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    viewport: innerWidth,
    targetLabel: target.labels[0]?.textContent.trim(),
    total: find('#total').textContent,
    remaining: find('#remaining').textContent,
    percent: find('#progress-percent').textContent,
    progress: find('#progress').getAttribute('aria-valuenow'),
    progressBar: find('#progress-fill').style.width,
  };
}

async function evaluate(send, expression) {
  const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || expression);
  return response.result.value;
}

async function waitForProgress(send, expected) {
  const expression = '(() => { const track = document.querySelector("#progress").getBoundingClientRect(); ' +
    'const fill = document.querySelector("#progress-fill").getBoundingClientRect(); ' +
    'return Math.abs(fill.width / track.width - ' + expected + ') < 0.001; })()';
  await waitFor(() => evaluate(send, expression), 'Progress bar did not settle to ' + expected);
}

async function testTarget(send, snapshot) {
  const evaluateOnPage = expression => evaluate(send, expression);
  const press = async (key, code, windowsVirtualKeyCode) => {
    for (const type of ['keyDown', 'keyUp']) {
      await send('Input.dispatchKeyEvent', { type, key, code, windowsVirtualKeyCode });
    }
  };
  await press('Tab', 'Tab', 9);
  await press('Tab', 'Tab', 9);
  const keyboard = await evaluateOnPage("document.activeElement.id === 'target' && document.activeElement.matches(':focus-visible')");
  const hit = await evaluateOnPage("(() => { const el = document.querySelector('#target'); const r = el.getBoundingClientRect(); return { x: r.left + 5, y: r.top + r.height / 2 }; })()");
  await evaluateOnPage('document.activeElement.blur()');
  for (const type of ['mousePressed', 'mouseReleased']) {
    await send('Input.dispatchMouseEvent', { type, ...hit, button: 'left', clickCount: 1 });
  }
  const hitActivates = await evaluateOnPage("document.activeElement.id === 'target'");
  await send('Input.insertText', { text: '170' });
  await waitForProgress(send, 1);
  const reached = await evaluateOnPage("document.querySelector('#remaining').textContent === '0' && document.querySelector('#progress-percent').textContent === '100%' && document.querySelector('#progress').getAttribute('aria-valuenow') === '100' && document.querySelector('#progress-fill').style.width === '100%'");
  const previousLoad = await evaluateOnPage('performance.timeOrigin');
  await send('Page.reload');
  await waitFor(() => evaluateOnPage("performance.timeOrigin > " + previousLoad + " && document.readyState === 'complete'").catch(() => false), 'The page did not reload');
  const persisted = await evaluateOnPage("document.querySelector('#target').value === '170' && document.querySelector('#remaining').textContent === '0' && document.querySelector('#progress-percent').textContent === '100%'");
  await evaluateOnPage("document.querySelector('#target').focus()");
  await send('Input.insertText', { text: '-1' });
  const invalid = await evaluateOnPage("document.querySelector('#target').getAttribute('aria-invalid') === 'true'");
  await press('Enter', 'Enter', 13);
  const recovered = await evaluateOnPage("document.querySelector('#target').value === '170' && document.activeElement.id !== 'target'");
  await waitFor(() => evaluateOnPage("getComputedStyle(document.querySelector('#toast')).opacity === '1'"), 'Input error was not shown');
  const textsError = (await evaluateOnPage('(' + observe.toString() + ')()')).texts;
  await snapshot('error');
  await waitFor(() => evaluateOnPage("getComputedStyle(document.querySelector('#toast')).opacity === '0'"), 'Input error did not clear');
  await evaluateOnPage("document.querySelector('#target').focus()");
  await send('Input.insertText', { text: '9007199254740991' });
  const longValueFits = await evaluateOnPage(`(() => {
    const element = document.querySelector('#remaining');
    const range = document.createRange();
    range.selectNodeContents(element);
    const box = element.getBoundingClientRect();
    const content = range.getBoundingClientRect();
    return element.textContent === '9,007,199,254,740,821' && content.left >= box.left - 1 && content.right <= box.right + 1;
  })()`);
  await evaluateOnPage("document.querySelector('#target').select()");
  await send('Input.insertText', { text: '0' });
  await press('Enter', 'Enter', 13);
  const unset = await evaluateOnPage('(' + observe.toString() + ')()');
  const unsetState = unset.remaining === '目標未設定' && unset.percent === '' && unset.progress === '0' &&
    !unset.progressVisible && unset.progressRatio === 0;
  await snapshot('unset');
  await evaluateOnPage("Storage.prototype.setItem = () => { throw new DOMException('Test storage quota', 'QuotaExceededError'); };");
  await evaluateOnPage("document.querySelector('#target').focus()");
  await send('Input.insertText', { text: '100' });
  await press('Enter', 'Enter', 13);
  await waitForProgress(send, 1);
  const blocked = await evaluateOnPage('(' + observe.toString() + ')()');
  const storageFailure = !unset.storageVisible && blocked.storageVisible && blocked.remaining === '-70' &&
    blocked.percent === '100%' && blocked.texts.includes('目標超過') && blocked.texts.includes('自動保存できません');
  await snapshot('storage');
  return {
    keyboard, hitActivates, reached, invalid: invalid && recovered, persisted, longValueFits, unsetState,
    textsUnset: unset.texts, textsError, storageFailure, textsStorage: blocked.texts,
  };
}

async function clickCounter(send, id, direction) {
  const selector = '[data-id="' + id + '"] .' + direction;
  const position = await evaluate(send, '(() => { const button = document.querySelector(' + JSON.stringify(selector) + '); ' +
    'button.scrollIntoView({block:"center"}); const r = button.getBoundingClientRect(); ' +
    'const x = r.left + r.width / 2, y = r.top + r.height / 2; ' +
    'return button.contains(document.elementFromPoint(x, y)) ? {x, y} : null; })()');
  if (!position) throw new Error('Counter is not clickable: ' + selector);
  for (const type of ['mousePressed', 'mouseReleased']) {
    await send('Input.dispatchMouseEvent', { type, ...position, button: 'left', clickCount: 1 });
  }
}

async function testCounters(send) {
  const entries = [
    ['reroll', 40, 2], ['note90', 90, 1], ['note72', 72, 0], ['note45', 45, 0],
    ['note400', 400, 0], ['note320', 320, 0], ['note200', 200, 0],
    ['trait3', 0, 0], ['enhancement2', 0, 0],
  ];
  for (const [id, price, initial] of entries) {
    const read = () => evaluate(send, '(() => { const card = document.querySelector(' +
      JSON.stringify('[data-id="' + id + '"]') + '); return {count: Number(card.querySelector("input").value), ' +
      'total: document.querySelector("#total").textContent, subtotal: card.querySelector(".card-subtotal").textContent}; })()');
    await clickCounter(send, id, 'increment');
    const added = await read();
    if (added.count !== initial + 1 || added.total !== String(170 + price) ||
        (price > 0 && added.subtotal !== '支出 ' + (initial + 1) * price + 'コイン')) return false;
    await clickCounter(send, id, 'decrement');
    const restored = await read();
    if (restored.count !== initial || restored.total !== '170' ||
        (price > 0 && restored.subtotal !== (initial ? '支出 ' + initial * price + 'コイン' : ''))) return false;
  }
  return true;
}

async function fillCounter(send, selector, value) {
  await evaluate(send, '(() => { const field = document.querySelector(' + JSON.stringify(selector) +
    '); field.value = ' + JSON.stringify(value) + '; field.dispatchEvent(new Event("input", { bubbles: true })); })()');
}

async function testResearchLimit(send) {
  await fillCounter(send, '#count-trait3', '11');
  const result = await evaluate(send, '(() => { const card = document.querySelector("[data-id=trait3]"); ' +
    'const state = card.querySelector(".research-remaining"); return card.querySelector("input").value === "11" ' +
    '&& state.textContent === "残り0回 / 上限10回（1回超過）" && state.scrollWidth <= state.clientWidth ' +
    '&& document.querySelector("#total").textContent === "170"; })()');
  await fillCounter(send, '#count-trait3', '0');
  return result;
}

function measureFiveDigits() {
  const field = document.querySelector('#count-note90');
  const style = getComputedStyle(field);
  const text = document.createElement('canvas').getContext('2d');
  text.font = [style.fontWeight, style.fontSize, style.fontFamily].join(' ');
  const glyphWidth = text.measureText(field.value).width + (parseFloat(style.letterSpacing) || 0) * (field.value.length - 1);
  const contentWidth = field.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  return { contentWidth, glyphWidth, fiveDigitsFit: field.value === '12345' && glyphWidth <= contentWidth };
}

async function testBoundaryWidths(send) {
  await fillCounter(send, '#count-note90', '12345');
  const widths = [];
  for (const width of [479, 480, 599, 600, 959, 960]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 800, deviceScaleFactor: 1, mobile: false });
    await evaluate(send, 'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    const { viewport, scrollWidth, clientWidth, noOverflow, membership } = await evaluate(send, '(' + observe.toString() + ')()');
    const digits = await evaluate(send, '(' + measureFiveDigits.toString() + ')()');
    widths.push({ width, viewport, scrollWidth, clientWidth, noOverflow, membership, ...digits });
  }
  await fillCounter(send, '#count-note90', '1');
  return widths;
}

async function capture(send, scenario, browserVersion, cases) {
  const { id, width, height, mobile } = scenario;
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  const url = pathToFileURL(resolve('dist/index.html'));
  url.searchParams.set('scenario', id);
  const seed = await send('Page.addScriptToEvaluateOnNewDocument', {
    source: 'localStorage.setItem(' + JSON.stringify(key) + ', ' + JSON.stringify(JSON.stringify(fixture)) + ')',
  });
  const { errorText } = await send('Page.navigate', { url: url.href });
  if (errorText) throw new Error(errorText);
  const loaded = "location.href === " + JSON.stringify(url.href) + " && document.readyState === 'complete' && !!document.getElementById('count-note90')";
  await waitFor(() => evaluate(send, loaded).catch(() => false), 'Counter page did not load');
  await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: seed.identifier });
  await evaluate(send, 'document.fonts.ready.then(() => true)');
  await waitForProgress(send, 0.34);
  const values = await evaluate(send, '(' + observe.toString() + ')()');
  const environment = { viewport: { width, height }, browser: browserVersion, theme: 'light', fixture: '目標500・素質の再抽選2回・音符5個の通常購入1回' };
  const metrics = id + '.json';
  const files = [];
  async function snapshot(state) {
    if (state && !mobile) return;
    const png = id + (state ? '-' + state : '') + '.png';
    const { cssContentSize } = await send('Page.getLayoutMetrics');
    const captureHeight = state ? height : Math.max(height, Math.ceil(cssContentSize.height));
    const { data } = await send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width, height: captureHeight, scale: 1 },
    });
    writeFileSync(join(output, png), Buffer.from(data, 'base64'));
    files.push({ path: png, kind: 'screenshot' });
  }
  await snapshot();
  if (!baseline) {
    Object.assign(values, await testTarget(send, snapshot));
    values.counterConnections = await testCounters(send);
    values.researchLimit = await testResearchLimit(send);
    if (!mobile) {
      values.boundaryMeasurements = await testBoundaryWidths(send);
      values.boundaryWidths = values.boundaryMeasurements.every(state =>
        state.noOverflow && state.membership && state.fiveDigitsFit && state.viewport === state.width);
    }
  }
  writeFileSync(join(output, metrics), JSON.stringify(values, null, 2) + '\n');
  files.push({ path: metrics, kind: 'metrics' });
  return {
    id, status: 'passed', observations: 'Edgeで支出グループ、表示文、目標と全カウンターの操作、保存を観測',
    environment,
    files,
    case_results: cases.filter(item => item.scenario === id).map(item => ({
      id: item.id, observation: 'Edgeの画面または実入力後の表示から ' + item.target + ' を観測',
      value_ref: { path: metrics, pointer: '/' + item.id.slice(id.length + 1) },
    })),
  };
}

let send;
try {
  const connected = await connect();
  send = connected.send;
  await send('Page.enable');
  const cases = baseline ? [] : JSON.parse(readFileSync('.harness/changes/' + change + '/design.json', 'utf8')).ui.cases;
  mkdirSync(output, { recursive: true });
  const reports = [];
  for (const scenario of scenarios) reports.push(await capture(send, scenario, connected.version, cases));
  if (baseline) {
    const before = reports.map(report => ({
      scenario: report.id,
      path: relative(process.cwd(), join(output, report.files[0].path)).split(sep).join('/'),
      environment: report.environment,
    }));
    writeFileSync(join(output, 'before.json'), JSON.stringify(before, null, 2) + '\n');
  } else {
    writeFileSync(join(output, process.env.CODEXENVSET_CHECK_ID + '.ui.json'),
      JSON.stringify({ schema_version: 3, scenarios: reports }, null, 2) + '\n');
  }
} catch (error) {
  console.error(browserLog);
  throw error;
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ id: 0, method: 'Browser.close' }));
    await Promise.race([once(socket, 'close'), delay(1000)]);
    socket.close();
  }
  if (browser.exitCode === null && !launchError) browser.kill();
  if (dirname(realpathSync(profile)) === profileRoot) {
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 150 });
  }
}
