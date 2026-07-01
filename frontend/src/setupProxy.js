const { createProxyMiddleware } = require('http-proxy-middleware');

/**
 * Proxy du serveur de dev CRA (`npm start`).
 *
 * Proxifie `/api/*` et `/graphs/*` vers l'API uvicorn locale (port 8000), pour
 * servir le front ET l'API sur la MÊME origine — exactement comme
 * scripts/preview_server.js le fait pour le build de preview.
 *
 * Conséquence : plus aucune requête cross-origin depuis le dashboard, donc plus
 * de blocage CORS. Avant ce proxy, `npm start` servait le front sur :3000 mais
 * le dashboard tapait l'API en cross-origin (tunnel mort ou IP LAN non
 * autorisée par TANDOR_CORS_ORIGINS) → le navigateur bloquait → repli sur le
 * bundle statique de 60 produits au lieu du catalogue live (cj.db, ~15k).
 *
 * Cible surchargeable via TANDOR_API_TARGET (défaut : http://127.0.0.1:8000).
 */
module.exports = function (app) {
  const target = process.env.TANDOR_API_TARGET || 'http://127.0.0.1:8000';
  app.use(
    ['/api', '/graphs'],
    createProxyMiddleware({ target, changeOrigin: true }),
  );
};
