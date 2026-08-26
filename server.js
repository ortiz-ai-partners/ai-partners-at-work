// agent-office Phase 1 server
// Claude Codeのセッション記録(~/.claude/projects/**/*.jsonl)を監視し、
// ツール使用イベントをSSEでブラウザに配信する。依存パッケージなし。
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PORT = 3939;
const ROOT = path.join(os.homedir(), '.claude', 'projects');
const PUB = path.join(__dirname, 'public');

const clients = new Set();
const offsets = new Map();   // file -> byte offset
const timers = new Map();    // file -> debounce timer

function kindOf(tool) {
  if (!tool) return 'thinking';
  if (/^(Read|Grep|Glob)$/.test(tool)) return 'reading';
  if (/^(Edit|Write|NotebookEdit|MultiEdit)$/.test(tool)) return 'coding';
  if (/^(Bash|PowerShell|BashOutput)$/.test(tool)) return 'terminal';
  if (/Web(Search|Fetch)/i.test(tool) || /browser|navigate|computer|preview/i.test(tool)) return 'web';
  if (/^(Agent|Task|Workflow)/.test(tool)) return 'delegate';
  return 'working';
}

function broadcast(ev) {
  const data = 'data: ' + JSON.stringify(ev) + '\n\n';
  for (const res of clients) { try { res.write(data); } catch (e) {} }
}

function handleLine(file, line) {
  line = line.trim();
  if (!line) return;
  let j;
  try { j = JSON.parse(line); } catch (e) { return; }
  const session = path.basename(file, '.jsonl');
  const project = path.basename(path.dirname(file));
  if (j.type === 'assistant' && j.message && Array.isArray(j.message.content)) {
    for (const c of j.message.content) {
      if (c.type === 'tool_use') {
        broadcast({ session, project, tool: c.name, kind: kindOf(c.name), ts: Date.now() });
      } else if (c.type === 'text' && c.text && c.text.length > 5) {
        broadcast({ session, project, tool: null, kind: 'talking', ts: Date.now() });
      }
    }
  }
}

function readNew(file) {
  fs.stat(file, (err, st) => {
    if (err) return;
    let prev = offsets.has(file) ? offsets.get(file) : 0;
    if (st.size < prev) prev = 0;           // rotated/truncated
    if (st.size === prev) return;
    const stream = fs.createReadStream(file, { start: prev, end: st.size - 1, encoding: 'utf8' });
    let buf = '';
    stream.on('data', (d) => { buf += d; });
    stream.on('end', () => {
      offsets.set(file, st.size);
      for (const line of buf.split('\n')) handleLine(file, line);
    });
    stream.on('error', () => {});
  });
}

function walkInit(dir) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (e) { return; }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walkInit(full);
    else if (e.name.endsWith('.jsonl')) {
      try { offsets.set(full, fs.statSync(full).size); } catch (err) {}
    }
  }
}

function startWatch() {
  walkInit(ROOT); // 既存分は読み飛ばし（起動後の新規イベントのみ配信）
  try {
    fs.watch(ROOT, { recursive: true }, (ev, filename) => {
      if (!filename || !filename.endsWith('.jsonl')) return;
      const full = path.join(ROOT, filename);
      clearTimeout(timers.get(full));
      timers.set(full, setTimeout(() => readNew(full), 120));
    });
    console.log('watching ' + ROOT);
  } catch (e) {
    console.error('watch failed: ' + e.message);
  }
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css', '.png': 'image/png' };

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === '/events') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });
    res.write(': connected\n\n');
    clients.add(res);
    const ping = setInterval(() => { try { res.write(': ping\n\n'); } catch (e) {} }, 25000);
    req.on('close', () => { clients.delete(res); clearInterval(ping); });
    return;
  }
  const file = path.join(PUB, url === '/' ? 'index.html' : url);
  if (!file.startsWith(PUB)) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
});

server.listen(PORT, () => console.log('agent-office on http://localhost:' + PORT));
startWatch();
