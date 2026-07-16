import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:http';

const root = fileURLToPath(new URL('./dist', import.meta.url));
const indexFile = join(root, 'index.html');
const port = Number(process.env.PORT || 3110);
const apiBase = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8010';

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
};

function sendFile(response, filePath) {
  response.statusCode = 200;
  response.setHeader('Content-Type', MIME_TYPES[extname(filePath)] || 'application/octet-stream');
  createReadStream(filePath).pipe(response);
}

async function proxyApi(request, response) {
  const target = new URL(request.url, apiBase);
  const body = request.method === 'GET' || request.method === 'HEAD' ? undefined : await readBody(request);
  const headers = { ...request.headers };
  delete headers.host;
  const upstream = await fetch(target, { method: request.method, headers, body });
  response.statusCode = upstream.status;
  upstream.headers.forEach((value, key) => response.setHeader(key, value));
  response.end(Buffer.from(await upstream.arrayBuffer()));
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on('data', chunk => chunks.push(chunk));
    request.on('end', () => resolve(Buffer.concat(chunks)));
    request.on('error', reject);
  });
}

const server = createServer(async (request, response) => {
  try {
    if (request.url?.startsWith('/api/')) {
      await proxyApi(request, response);
      return;
    }

    const requestedPath = decodeURIComponent(new URL(request.url || '/', 'http://localhost').pathname);
    const candidate = normalize(join(root, requestedPath));
    const safeCandidate = candidate === root || candidate.startsWith(`${root}${sep}`);
    const filePath = safeCandidate && existsSync(candidate) && statSync(candidate).isFile() ? candidate : indexFile;
    sendFile(response, filePath);
  } catch (error) {
    response.statusCode = 502;
    response.setHeader('Content-Type', 'application/json; charset=utf-8');
    response.end(JSON.stringify({ detail: error instanceof Error ? error.message : 'proxy error' }));
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`StockMaster Vue server listening on ${port}`);
});
