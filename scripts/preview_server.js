// Serveur de preview : sert le build React (SPA) et proxifie /api/* + /graphs/*
// vers l'API locale (uvicorn:8000), le tout sur la MÊME origine.
// => pas de CORS, pas besoin de toucher à l'API. Usage : node scripts/preview_server.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PREVIEW_PORT || 3000;
const API = { host: '127.0.0.1', port: 8000 };
const BUILD = path.join(__dirname, '../frontend/build');

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.txt': 'text/plain', '.xml': 'application/xml',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.map': 'application/json',
};

function proxy(req, res) {
  const opts = { host: API.host, port: API.port, method: req.method, path: req.url, headers: req.headers };
  const up = http.request(opts, (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); });
  up.on('error', (e) => { res.writeHead(502); res.end('API indisponible: ' + e.message); });
  req.pipe(up);
}

function serveStatic(req, res) {
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/') rel = '/index.html';
  let file = path.join(BUILD, rel);
  if (!file.startsWith(BUILD)) { res.writeHead(403); return res.end('forbidden'); }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) file = path.join(BUILD, 'index.html'); // SPA fallback
    fs.readFile(file, (e, buf) => {
      if (e) { res.writeHead(404); return res.end('not found'); }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
      res.end(buf);
    });
  });
}

http.createServer((req, res) => {
  // Endpoint de debug : le capteur d'erreurs du front POST ici, on log côté serveur.
  if (req.url === '/__log' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      console.log('\n===== FRONT ERROR =====\n' + body + '\n=======================\n');
      res.writeHead(204); res.end();
    });
    return;
  }
  if (req.url.startsWith('/api/') || req.url.startsWith('/graphs/')) return proxy(req, res);
  serveStatic(req, res);
}).listen(PORT, () => console.log(`✅ Preview sur http://localhost:${PORT} (API proxifiée -> :8000)`));
