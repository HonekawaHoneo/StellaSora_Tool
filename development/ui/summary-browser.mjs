// CodexEnvSet UI provider. Node 24; native Chromium/Edge CDP, no npm dependencies.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { createServer, get } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const candidates = [process.env.STELLA_EDGE_PATH, process.env.CHROMIUM_EXECUTABLE,
  ...['ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'].map(name => process.env[name] && join(process.env[name], 'Microsoft/Edge/Application/msedge.exe')),
  '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
const edge = candidates.find(candidate => existsSync(candidate));
if (!edge) throw new Error('No Chromium/Edge found; set STELLA_EDGE_PATH or CHROMIUM_EXECUTABLE');
const baseline = process.argv[2] === '--before' || process.env.CODEXENVSET_UI_MODE === 'before';
const change = process.env.CODEXENVSET_CHANGE_ID;
const outputPath = baseline ? process.argv[3] || process.env.CODEXENVSET_EVIDENCE_DIR : process.env.CODEXENVSET_EVIDENCE_DIR;
if (!outputPath) throw new Error('Supply --before OUTPUT, or run through the harness evidence environment');
const output = resolve(outputPath);
const assets = { 'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8',
  'counter.js': 'text/javascript; charset=utf-8', 'styles.css': 'text/css; charset=utf-8' };
const server = createServer((request, response) => {
  const asset = new URL(request.url, 'http://127.0.0.1').pathname.slice(1) || 'index.html';
  if (!Object.hasOwn(assets, asset)) { response.writeHead(404).end(); return; }
  try { response.writeHead(200, { 'Content-Type': assets[asset], 'Cache-Control': 'no-store' }).end(readFileSync(resolve('dist', asset))); }
  catch { response.writeHead(500).end('Unable to read application asset'); }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const appUrl = 'http://127.0.0.1:' + server.address().port + '/';
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
  ...(process.platform === 'linux' ? ['--no-sandbox', '--disable-dev-shm-usage'] : []),
  '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true,
  env: { ...process.env, ...(process.platform === 'linux' ? { XDG_CONFIG_HOME: join(profile, 'config'), XDG_CACHE_HOME: join(profile, 'cache') } : {}) } });
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
  return { send, version: version.Browser + (version['User-Agent'].match(/Edg\/[\d.]+/) ? ' / ' + version['User-Agent'].match(/Edg\/[\d.]+/)[0] : '') };
}

function observe() {
  const find = selector => document.querySelector(selector);
  const box = selector => find(selector).getBoundingClientRect().toJSON();
  const style = selector => getComputedStyle(find(selector));
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  function selector(element) {
    const parts = [];
    for (let node = element; node instanceof Element; node = node.parentElement) {
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      if (node.hasAttribute('data-id')) { parts.unshift('[data-id="' + node.getAttribute('data-id') + '"]'); break; }
      const siblings = node.parentElement ? [...node.parentElement.children].filter(other => other.tagName === node.tagName) : [node];
      parts.unshift(node.localName + (siblings.length > 1 ? ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')' : ''));
    }
    return parts.join(' > ');
  }
  const label = '.metric-target .metric-label';
  const target = find('#target');
  const labels = [...document.querySelectorAll('.metric-label')].map(element => element.textContent.trim());
  const rows = [...document.querySelectorAll('.metric')].map(element => element.getBoundingClientRect().top);
  const copyItems = { body: [], qa: [], tooltip: [], accessible_name: [] };
  const nodes = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  const visibility = { opacityProperty: true, visibilityProperty: true };
  for (let node = nodes.nextNode(); node; node = nodes.nextNode()) {
    const element = node instanceof Element ? node : node.parentElement;
    if (!element || element.closest('script,style,noscript,template')) continue;
    const qa = element.closest('[data-copy-surface="qa"],details');
    const tooltip = element.closest('[role="tooltip"],[data-copy-surface="tooltip"]');
    const surface = qa ? 'qa' : tooltip ? 'tooltip' : 'body';
    if (node instanceof HTMLInputElement && (qa || tooltip || node.checkVisibility(visibility))) {
      copyItems[surface].push({ text: node.value, target: selector(node), kind: 'value' });
    } else if (node.nodeType === Node.TEXT_NODE && (qa || tooltip || element.checkVisibility(visibility))) {
      const text = normalize(node.textContent);
      if (text) copyItems[surface].push({ text, target: selector(element), kind: 'text' });
    }
  }
  for (const element of document.querySelectorAll('[title],[data-tooltip]')) {
    for (const attribute of ['title', 'data-tooltip']) {
      const text = normalize(element.getAttribute(attribute));
      if (text) copyItems.tooltip.push({ text, target: selector(element), kind: attribute });
    }
  }
  const texts = copyItems.body.map(item => item.text);
  const minFont = selector => {
    const values = [...document.querySelectorAll(selector)].filter(element => element.checkVisibility(visibility)).map(element => parseFloat(getComputedStyle(element).fontSize));
    return values.length ? Math.min(...values) : null;
  };
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
    texts, copyItems, copyBody: texts, copyQa: copyItems.qa.map(item => item.text),
    copyTooltip: copyItems.tooltip.map(item => item.text), copyAccessible: [],
    labels, indicatorContrast, progressRatio, spendingBox, membership,
    summaryHeight: box('.summary').height, appHeight: box('.app-shell').height,
    unitMinFont: minFont('.note-price span,.reroll-price span'),
    discountMinFont: minFont('.discount-badge'),
    researchMinFont: minFont('.research-remaining,.research-condition'),
    researchConditionText: normalize(find('#research-condition')?.textContent),
    resetLabel: normalize(find('#reset').textContent),
    resetWidth: box('#reset').width, resetHeight: box('#reset').height,
    noSpendingSubtotals: ![...document.querySelectorAll('.counter-card:not(.record) .card-subtotal')].some(element => normalize(element.textContent)),
    coarsePointer: matchMedia('(pointer:coarse)').matches,
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

// Use the browser's computed AX names, descriptions and textual values rather
// than attempting to infer the accessible-name algorithm from DOM attributes.
async function observeAll(send) {
  const values = await evaluate(send, '(' + observe.toString() + ')()');
  const [ax, snapshot] = await Promise.all([
    send('Accessibility.getFullAXTree'),
    send('DOMSnapshot.captureSnapshot', { computedStyles: [] }),
  ]);
  const strings = snapshot.strings;
  const selectors = new Map();
  const attributesByBackend = new Map();
  for (const document of snapshot.documents) {
    const nodes = document.nodes;
    const cache = new Map();
    const attributes = index => {
      const raw = nodes.attributes[index] || [];
      return Object.fromEntries(Array.from({ length: raw.length / 2 }, (_, n) => [strings[raw[n * 2]], strings[raw[n * 2 + 1]]]));
    };
    const select = index => {
      if (cache.has(index)) return cache.get(index);
      const attrs = attributes(index), tag = strings[nodes.nodeName[index]].toLowerCase();
      let value;
      if (attrs.id) value = '[id=' + JSON.stringify(attrs.id) + ']';
      else if (attrs['data-id']) value = '[data-id=' + JSON.stringify(attrs['data-id']) + ']';
      else {
        const parent = nodes.parentIndex[index];
        const siblings = nodes.parentIndex.map((p, n) => p === parent && nodes.nodeType[n] === 1 && nodes.nodeName[n] === nodes.nodeName[index] ? n : -1).filter(n => n >= 0);
        value = tag + (siblings.length > 1 ? ':nth-of-type(' + (siblings.indexOf(index) + 1) + ')' : '');
        if (parent >= 0 && nodes.nodeType[parent] === 1) value = select(parent) + ' > ' + value;
      }
      cache.set(index, value);
      return value;
    };
    nodes.backendNodeId.forEach((backend, index) => {
      if (nodes.nodeType[index] === 1) { selectors.set(backend, select(index)); attributesByBackend.set(backend, attributes(index)); }
    });
  }
  const ignoredRoles = new Set(['RootWebArea', 'WebArea', 'generic', 'none', 'StaticText', 'InlineTextBox', 'LineBreak']);
  const items = [];
  for (const node of ax.nodes) {
    const role = node.role?.value;
    const target = selectors.get(node.backendDOMNodeId);
    if (node.ignored || !target || ignoredRoles.has(role)) continue;
    const candidates = [['name', node.name?.value], ['description', node.description?.value]];
    // Some Chromium builds omit valuetext from the AX protocol properties even
    // though the DOM explicitly supplies it. Retain that observed wording too.
    const textualValue = node.properties?.find(property => property.name === 'valuetext')?.value?.value || attributesByBackend.get(node.backendDOMNodeId)?.['aria-valuetext'];
    if (textualValue !== undefined && textualValue !== '') candidates.push(['value', textualValue]);
    else if (typeof node.value?.value === 'string' && node.value.value !== '') candidates.push(['value', node.value.value]);
    for (const [kind, raw] of candidates) {
      const text = String(raw ?? '').replace(/\s+/g, ' ').trim();
      if (text) items.push({ text, target, kind, role });
    }
  }
  values.copyItems.accessible_name = items;
  values.copyAccessible = items.map(item => item.text);
  return values;
}

function stateInventory(values, suffix) {
  return Object.fromEntries(['copyBody', 'copyQa', 'copyTooltip', 'copyAccessible', 'copyItems'].map(name => [name + suffix, values[name]]));
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
  const reachedState = await observeAll(send);
  await snapshot('reached');
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
  const errorState = await observeAll(send);
  const textsError = errorState.texts;
  await snapshot('error');
  const invalidCountResults = [];
  for (const value of ['-1', '1.5']) {
    await fillCounter(send, '#count-note90', value);
    const markedInvalid = await evaluateOnPage("document.querySelector('#count-note90').getAttribute('aria-invalid')==='true'");
    await press('Enter', 'Enter', 13);
    invalidCountResults.push(await evaluateOnPage(`(() => {
      const input=document.querySelector('#count-note90'), saved=JSON.parse(localStorage.getItem('stella-sora-star-tower-v1'));
      return { submitted:${JSON.stringify(value)},markedInvalid:${markedInvalid},recovered:input.value==='1' && document.activeElement!==input && saved.counts.note90===1 && document.querySelector('#total').textContent==='170',errorText:document.querySelector('#toast').textContent.trim() };
    })()`));
  }
  const countErrorState = await observeAll(send);
  await snapshot('count-error');
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
  const longState = await observeAll(send);
  await snapshot('long');
  await evaluateOnPage("document.querySelector('#target').select()");
  await send('Input.insertText', { text: '0' });
  await press('Enter', 'Enter', 13);
  const unset = await observeAll(send);
  const unsetState = unset.remaining === '目標未設定' && unset.percent === '' && unset.progress === '0' &&
    !unset.progressVisible && unset.progressRatio === 0;
  await snapshot('unset');
  await evaluateOnPage("window.__providerSetItem = Storage.prototype.setItem; Storage.prototype.setItem = () => { throw new DOMException('Test storage quota', 'QuotaExceededError'); };");
  await evaluateOnPage("document.querySelector('#target').focus()");
  await send('Input.insertText', { text: '100' });
  await press('Enter', 'Enter', 13);
  await waitForProgress(send, 1);
  const blocked = await observeAll(send);
  const storageFailure = !unset.storageVisible && blocked.storageVisible && blocked.remaining === '-70' &&
    blocked.percent === '100%' && blocked.texts.includes('目標超過');
  await snapshot('storage');
  await evaluateOnPage('Storage.prototype.setItem = window.__providerSetItem; delete window.__providerSetItem');
  return {
    keyboard, hitActivates, reached, invalid: invalid && recovered, persisted, longValueFits, unsetState,
    invalidCount: invalidCountResults.every(result=>result.markedInvalid&&result.recovered), invalidCountResults,
    textsUnset: unset.texts, textsError, storageFailure, textsStorage: blocked.texts,
    storageText: await evaluateOnPage("document.querySelector('#storage-status').textContent.trim()"),
    errorText: errorState.copyItems.body.find(item=>item.target==='#toast')?.text || '',
    ...stateInventory(reachedState, 'Reached'), ...stateInventory(errorState, 'Error'),
    ...stateInventory(longState, 'Long'), ...stateInventory(unset, 'Unset'), ...stateInventory(blocked, 'Storage'), ...stateInventory(countErrorState, 'CountError'),
  };
}

async function clickCounter(send, id, direction) {
  const selector = '[data-id="' + id + '"] .' + direction;
  const position = await evaluate(send, '(() => { const button = document.querySelector(' + JSON.stringify(selector) + '); ' +
    'button.scrollIntoView({block:"center"}); const r = button.getBoundingClientRect(); ' +
    'const x = r.left + Math.min(3, r.width / 2), y = r.top + r.height / 2; ' +
    'return button.contains(document.elementFromPoint(x, y)) ? {x, y, width:r.width, height:r.height} : null; })()');
  if (!position) throw new Error('Counter is not clickable: ' + selector);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: position.x, y: position.y, button: 'left', clickCount: 1 });
  const focused = await evaluate(send, 'document.activeElement===document.querySelector(' + JSON.stringify(selector) + ')');
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: position.x, y: position.y, button: 'left', clickCount: 1 });
  return { ...position, focused };
}

async function testCounters(send) {
  const metrics = {}, hits = [];
  const entries = [
    ['reroll', 40, 2], ['note90', 90, 1], ['note72', 72, 0], ['note45', 45, 0],
    ['note400', 400, 0], ['note320', 320, 0], ['note200', 200, 0],
    ['trait3', 0, 0], ['enhancement2', 0, 0],
  ];
  for (const [id, price, initial] of entries) {
    const read = () => evaluate(send, '(() => { const card = document.querySelector(' +
      JSON.stringify('[data-id="' + id + '"]') + '); return {count: Number(card.querySelector("input").value), ' +
      'total: document.querySelector("#total").textContent, savedCount: JSON.parse(localStorage.getItem("stella-sora-star-tower-v1")).counts[' + JSON.stringify(id) + ']}; })()');
    const up = await clickCounter(send, id, 'increment');
    const added = await read();
    const increment = up.focused && added.count === initial + 1 && added.savedCount === initial + 1 && added.total === String(170 + price);
    const down = await clickCounter(send, id, 'decrement');
    const restored = await read();
    const decrement = down.focused && restored.count === initial && restored.savedCount === initial && restored.total === '170';
    for (const [direction, position, activated] of [['increment', up, increment], ['decrement', down, decrement]]) {
      metrics[id + '-' + direction + '-width'] = position.width;
      metrics[id + '-' + direction + '-height'] = position.height;
      metrics[id + '-' + direction + '-activates'] = activated;
      hits.push({ target: '[data-id="' + id + '"] .' + direction, direction, ...position, activated });
    }
    const position = await fillCounter(send, '#count-' + id, String(initial + 1));
    const edited = await read();
    const focused = await evaluate(send, 'document.activeElement.id === ' + JSON.stringify('count-' + id));
    await fillCounter(send, '#count-' + id, String(initial));
    const inputRestored = await read();
    const activated = focused && edited.count === initial + 1 && edited.savedCount === initial + 1 &&
      edited.total === String(170 + price) && inputRestored.count === initial && inputRestored.savedCount === initial && inputRestored.total === '170';
    metrics[id + '-input-width'] = position.width;
    metrics[id + '-input-height'] = position.height;
    metrics[id + '-input-activates'] = activated;
    hits.push({ target: '#count-' + id, direction: 'input', ...position, activated });
  }
  return { counterConnections: hits.every(hit => hit.activated), counterHits: hits, ...metrics };
}

async function fillCounter(send, selector, value) {
  const position = await evaluate(send, '(() => { const field = document.querySelector(' + JSON.stringify(selector) +
    '); field.scrollIntoView({block:"center"}); const r = field.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2; return document.elementFromPoint(x,y)===field ? {x,y,width:r.width,height:r.height}:null; })()');
  if (!position) throw new Error('Input is not hit-testable: ' + selector);
  for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x: position.x, y: position.y, button: 'left', clickCount: 1 });
  for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 });
  await send('Input.insertText', { text: value });
  return position;
}

async function testResearchLimit(send) {
  await fillCounter(send, '#count-trait3', '11');
  const result = await evaluate(send, '(() => { const card = document.querySelector("[data-id=trait3]"); ' +
    'const state = card.querySelector(".research-remaining"); return card.querySelector("input").value === "11" ' +
    '&& ["残り0回 / 上限10回（1回超過）", "残り0 / 10回（1回超過）"].includes(state.textContent) && state.scrollWidth <= state.clientWidth ' +
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
  for (const width of [390, 479, 480, 599, 600, 768, 959, 960]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height: 800, deviceScaleFactor: 1, mobile: false });
    await evaluate(send, 'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    const { viewport, scrollWidth, clientWidth, noOverflow, membership } = await evaluate(send, '(' + observe.toString() + ')()');
    const digits = await evaluate(send, '(' + measureFiveDigits.toString() + ')()');
    widths.push({ width, viewport, scrollWidth, clientWidth, noOverflow, membership, ...digits });
  }
  await fillCounter(send, '#count-note90', '1');
  return widths;
}

async function testReset(send, snapshot) {
  const hit = await evaluate(send, `(() => {
    const button=document.querySelector('#reset'); button.scrollIntoView({block:'center'});
    const r=button.getBoundingClientRect(), x=r.left+3, y=r.top+r.height/2;
    return button.contains(document.elementFromPoint(x,y)) ? {x,y,width:r.width,height:r.height}:null;
  })()`);
  if (!hit) throw new Error('Reset is not hit-testable');
  for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x: hit.x, y: hit.y, button: 'left', clickCount: 1 });
  await evaluate(send, 'new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  await waitForProgress(send, 0);
  const resetActivates = await evaluate(send, `(() => {
    const saved=JSON.parse(localStorage.getItem('stella-sora-star-tower-v1'));
    return [...document.querySelectorAll('.count-input')].length===9 && [...document.querySelectorAll('.count-input')].every(input=>input.value==='0') &&
      Object.values(saved.counts).every(value=>value===0) && saved.target===100 && document.querySelector('#target').value==='100' && document.querySelector('#total').textContent==='0';
  })()`);
  const reset = await observeAll(send);
  const noResetToast = await evaluate(send, "!document.querySelector('#toast').checkVisibility({opacityProperty:true,visibilityProperty:true})");
  await snapshot('reset');
  const previousLoad = await evaluate(send, 'performance.timeOrigin');
  await send('Page.reload');
  await waitFor(() => evaluate(send, "performance.timeOrigin>" + previousLoad + "&&document.readyState==='complete'&&document.querySelectorAll('.count-input').length===9").catch(() => false), 'Reset document did not reload');
  const resetPersists = await evaluate(send, "[...document.querySelectorAll('.count-input')].every(input=>input.value==='0')&&document.querySelector('#target').value==='100'&&document.querySelector('#total').textContent==='0'");
  return { resetActivates, resetPersists, resetPersisted: resetPersists, noResetToast, resetWidth: hit.width, resetHeight: hit.height, ...stateInventory(reset, 'Reset') };
}

async function testZoom(send, snapshot) {
  await send('Emulation.setDeviceMetricsOverride', { width: 640, height: 400, deviceScaleFactor: 2, mobile: false });
  await evaluate(send, 'new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
  const zoomFactor = await evaluate(send, 'devicePixelRatio');
  const zoomFits = await evaluate(send, "document.documentElement.scrollWidth<=innerWidth && document.querySelector('.app-shell').getBoundingClientRect().right<=innerWidth+1");
  let zoomOperable = false, zoomError = '';
  try {
    await fillCounter(send, '#count-note90', '2');
    const countChanged = await evaluate(send, "document.querySelector('#total').textContent==='180' && JSON.parse(localStorage.getItem('stella-sora-star-tower-v1')).counts.note90===2");
    await fillCounter(send, '#count-note90', '0');
    await fillCounter(send, '#target', '200');
    const targetChanged = await evaluate(send, "document.querySelector('#remaining').textContent==='200' && JSON.parse(localStorage.getItem('stella-sora-star-tower-v1')).target===200");
    await fillCounter(send, '#target', '100');
    const restored = await evaluate(send, "document.querySelector('#remaining').textContent==='100'&&document.querySelector('#total').textContent==='0'");
    zoomOperable = zoomFactor===2&&countChanged&&targetChanged&&restored;
  } catch (error) { zoomError = error.message; }
  const zoomDiagnostics = await evaluate(send, `(() => {
    const field=document.querySelector('#count-note90'), r=field.getBoundingClientRect(), hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
    return {viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,scrollY,field:r.toJSON(),hit:hit?.id||hit?.className||hit?.tagName};
  })()`);
  try { await snapshot('zoom', 640, 400); }
  finally { await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false }); }
  return { zoomFactor, zoomFits, zoomOperable, zoomError, zoomDiagnostics,
    zoomEnvironment: { viewport: { width: 640, height: 400 }, device_scale_factor: 2 },
    zoomMethod: '200% reflow equivalent via CSS viewport640 and DSF2; native browser UI zoom not exercised' };
}

async function capture(send, scenario, browserVersion, cases) {
  const { id, width, height, mobile } = scenario;
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  await send('Emulation.setTouchEmulationEnabled', { enabled: mobile, maxTouchPoints: 1 });
  await send('Emulation.setLocaleOverride', { locale: 'ja-JP' });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  const url = new URL(appUrl);
  url.searchParams.set('scenario', id);
  const seed = await send('Page.addScriptToEvaluateOnNewDocument', {
    source: 'localStorage.setItem(' + JSON.stringify(key) + ', ' + JSON.stringify(JSON.stringify(fixture)) + ')',
  });
  const { errorText } = await send('Page.navigate', { url: url.href });
  if (errorText) throw new Error(errorText);
  const loaded = "location.href === " + JSON.stringify(url.href) + " && document.readyState === 'complete' && !!document.getElementById('count-note90')";
  try { await waitFor(() => evaluate(send, loaded).catch(() => false), 'Counter page did not load'); }
  catch (error) {
    console.error('Page load diagnostics:', await evaluate(send, '({url:location.href,ready:document.readyState,text:document.body?.innerText?.slice(0,1200),scripts:[...document.scripts].map(script=>script.src)})').catch(() => 'runtime unavailable'));
    throw error;
  }
  await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: seed.identifier });
  await evaluate(send, 'document.fonts.ready.then(() => true)');
  await waitForProgress(send, 0.34);
  const values = await observeAll(send);
  const environment = { viewport: { width, height }, browser: browserVersion, theme: 'light', fixture: '目標500・素質の再抽選2回・音符5個の通常購入1回' };
  const metrics = id + '.json';
  const files = [];
  async function snapshot(state, captureWidth = width, captureViewportHeight = height) {
    const png = id + (state ? '-' + state : '') + '.png';
    const { cssContentSize } = await send('Page.getLayoutMetrics');
    const captureHeight = state ? captureViewportHeight : Math.max(captureViewportHeight, Math.ceil(cssContentSize.height));
    const { data } = await send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: captureWidth, height: captureHeight, scale: 1 },
    });
    writeFileSync(join(output, png), Buffer.from(data, 'base64'));
    files.push({ path: png, kind: 'screenshot' });
  }
  await snapshot();
  if (!baseline) {
    Object.assign(values, await testTarget(send, snapshot));
    Object.assign(values, await testCounters(send));
    values.researchLimit = await testResearchLimit(send);
    if (!mobile) {
      values.boundaryMeasurements = await testBoundaryWidths(send);
      values.boundaryWidths = values.boundaryMeasurements.every(state =>
        state.noOverflow && state.membership && state.fiveDigitsFit && state.viewport === state.width);
      await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
    }
    Object.assign(values, await testReset(send, snapshot));
    if (!mobile) Object.assign(values, await testZoom(send, snapshot));
  }
  writeFileSync(join(output, metrics), JSON.stringify(values, null, 2) + '\n');
  files.push({ path: metrics, kind: 'metrics' });
  return {
    id, status: 'passed', observations: 'Chromium/Edgeの実画面・AXツリー・実入力で寸法、全面の文言、全カウンター、保存を観測。期待値判定はハーネスが実測値から行う',
    environment,
    files,
    case_results: cases.filter(item => item.scenario === id).map(item => {
      const metric = item.id.slice(id.length + 1);
      if (!Object.hasOwn(values, metric)) throw new Error('Missing measured metric for case ' + item.id + ': ' + metric);
      return { id: item.id, observation: '実ブラウザの画面または実入力後の表示から ' + item.target + ' の ' + metric + ' を観測',
        value_ref: { path: metrics, pointer: '/' + metric.replaceAll('~', '~0').replaceAll('/', '~1') } };
    }),
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
  await new Promise(resolve => server.close(resolve));
}
