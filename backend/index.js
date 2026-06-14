const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.static('public'));

const SRC_DIR = path.join(__dirname, '../scrapa/src/graphs');
const PUBLIC_GRAPHS_DIR = path.join(__dirname, 'public/graphs');

if (!fs.existsSync(PUBLIC_GRAPHS_DIR)) {
  fs.mkdirSync(PUBLIC_GRAPHS_DIR, { recursive: true });
}

fs.readdir(SRC_DIR, (err, files) => {
  if (err) {
    console.error('Erreur lecture du dossier source :', err);
    return;
  }

  const trendFiles = files.filter(f => f.startsWith('trends_') && f.endsWith('.json'));

  trendFiles.forEach(file => {
    const srcPath = path.join(SRC_DIR, file);
    const destPath = path.join(PUBLIC_GRAPHS_DIR, file);
    fs.copyFileSync(srcPath, destPath);
  });

  console.log(`📊 ${trendFiles.length} fichiers copiés vers public/graphs`);
});

app.get('/api/graphs', (req, res) => {
  fs.readdir(PUBLIC_GRAPHS_DIR, (err, files) => {
    if (err) {
      console.error('Erreur lecture du dossier public/graphs :', err);
      return res.status(500).json({ error: 'Erreur serveur' });
    }

    const jsonFiles = files.filter(f => f.endsWith('.json'));
    res.json(jsonFiles);
  });
});

app.listen(PORT, () => {
  console.log(`✅ Backend lancé sur http://localhost:${PORT}`);
});
