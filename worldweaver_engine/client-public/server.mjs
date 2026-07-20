// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const port = Number.parseInt(process.env.PORT || '5174', 10);
const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, 'dist');

function httpTargetValue(value, label) {
  const parsed = new URL(String(value || '').trim());
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error(`${label} must use http or https`);
  }
  return parsed.origin;
}

function httpTarget(name, fallback) {
  return httpTargetValue(process.env[name] || fallback, name);
}

function shardRoutes() {
  const raw = String(process.env.VITE_WW_SHARD_ROUTES || '').trim();
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('VITE_WW_SHARD_ROUTES must be a JSON object');
  }
  return Object.values(parsed).map((route) => {
    const prefix = String(route?.prefix || '').trim();
    if (!/^\/[a-z0-9-]+$/i.test(prefix)) {
      throw new Error(`Invalid shard route prefix: ${prefix}`);
    }
    return {prefix, target: httpTargetValue(route?.target, 'shard route target')};
  });
}

const defaultTarget = httpTarget('VITE_PROXY_TARGET', 'http://localhost:8000');
const worldTarget = httpTarget('VITE_WW_WORLD_URL', 'http://localhost:9000');
const routes = shardRoutes();
const defaultShardPrefix = String(process.env.VITE_DEFAULT_SHARD_PREFIX || '').trim();
if (defaultShardPrefix && !/^\/[a-z0-9-]+$/i.test(defaultShardPrefix)) {
  throw new Error('VITE_DEFAULT_SHARD_PREFIX must be empty or one URL path segment');
}

const mimeTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function proxyDestination(url) {
  if (url.pathname === '/ww-world' || url.pathname.startsWith('/ww-world/')) {
    return {target: worldTarget, pathname: url.pathname.slice('/ww-world'.length) || '/'};
  }
  for (const route of routes) {
    if (url.pathname === route.prefix || url.pathname.startsWith(`${route.prefix}/`)) {
      return {target: route.target, pathname: url.pathname.slice(route.prefix.length) || '/'};
    }
  }
  if (url.pathname === '/health' || url.pathname.startsWith('/api/')) {
    return {target: defaultTarget, pathname: url.pathname};
  }
  return null;
}

async function proxy(request, response, destination, incomingUrl) {
  const upstreamUrl = new URL(destination.pathname + incomingUrl.search, destination.target);
  const headers = new Headers();
  for (const [name, value] of Object.entries(request.headers)) {
    if (value !== undefined && !['connection', 'host'].includes(name.toLowerCase())) {
      headers.set(name, Array.isArray(value) ? value.join(', ') : value);
    }
  }
  headers.set('x-forwarded-host', request.headers.host || '');
  headers.set('x-forwarded-proto', request.headers['x-forwarded-proto'] || 'http');

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method || 'GET') ? undefined : request,
      duplex: 'half',
      redirect: 'manual',
    });
    response.statusCode = upstream.status;
    upstream.headers.forEach((value, name) => {
      if (!['connection', 'transfer-encoding'].includes(name.toLowerCase())) {
        response.setHeader(name, value);
      }
    });
    if (!upstream.body || request.method === 'HEAD') {
      response.end();
      return;
    }
    for await (const chunk of upstream.body) response.write(chunk);
    response.end();
  } catch {
    response.writeHead(502, {'content-type': 'application/json; charset=utf-8'});
    response.end(JSON.stringify({detail: 'The selected shard is unavailable.'}));
  }
}

function safeStaticPath(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  const resolved = path.resolve(dist, `.${decoded}`);
  return resolved === dist || resolved.startsWith(`${dist}${path.sep}`) ? resolved : null;
}

function securityHeaders(response) {
  response.setHeader('x-content-type-options', 'nosniff');
  response.setHeader('referrer-policy', 'same-origin');
  response.setHeader('x-frame-options', 'DENY');
}

async function serveStatic(request, response, incomingUrl) {
  if (incomingUrl.pathname === '/runtime-config.js') {
    response.writeHead(200, {
      'content-type': 'text/javascript; charset=utf-8',
      'cache-control': 'no-store',
    });
    response.end(
      `window.__WORLDWEAVER_RUNTIME__=${JSON.stringify({defaultShardPrefix})};\n`,
    );
    return;
  }

  let candidate = safeStaticPath(incomingUrl.pathname);
  if (!candidate) {
    response.writeHead(400);
    response.end('Bad request');
    return;
  }
  try {
    if ((await stat(candidate)).isDirectory()) candidate = path.join(candidate, 'index.html');
    await stat(candidate);
  } catch {
    if (path.extname(incomingUrl.pathname)) {
      response.writeHead(404);
      response.end('Not found');
      return;
    }
    candidate = path.join(dist, 'index.html');
  }

  const extension = path.extname(candidate).toLowerCase();
  response.writeHead(200, {
    'content-type': mimeTypes.get(extension) || 'application/octet-stream',
    'cache-control': incomingUrl.pathname.startsWith('/assets/')
      ? 'public, max-age=31536000, immutable'
      : 'no-cache',
  });
  if (request.method === 'HEAD') response.end();
  else createReadStream(candidate).pipe(response);
}

createServer(async (request, response) => {
  securityHeaders(response);
  const incomingUrl = new URL(request.url || '/', 'http://localhost');
  const destination = proxyDestination(incomingUrl);
  if (destination) await proxy(request, response, destination, incomingUrl);
  else await serveStatic(request, response, incomingUrl);
}).listen(port, '0.0.0.0', () => {
  console.log(`WorldWeaver public client listening on ${port}`);
});
