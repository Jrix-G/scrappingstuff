import React, { useEffect, useState } from 'react';
import TrendGraph from './TrendGraph';

type Dataset = {
  title: string;
  data: { date: string; value: number }[];
  valueKey: string;
};

const Home = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:3001/api/graphs')
      .then((res) => res.json())
      .then(async (fileList: string[]) => {
        const datasets = await Promise.all(
          fileList.map(async (file) => {
            try {
              const res = await fetch(`http://localhost:3001/graphs/${file}`);
              const rawData = await res.json();

              console.log('Fichier:', file, 'Données:', rawData);

              if (!rawData || rawData.length === 0) return null;
              const valueKey = Object.keys(rawData[0]).find((k) => k !== 'date');
              if (!valueKey) return null;

              const title = file.replace('trends_', '').replace('.json', '');
              const data = rawData.map((item: any) => ({
                date: item.date.split(' ')[0],
                value: item[valueKey],
              }));

              return { title, data, valueKey: 'value' };
            } catch (err) {
              console.error(`Erreur dans le fichier ${file} :`, err);
              return null;
            }
          })
        );

        setDatasets(datasets.filter((d): d is Dataset => d !== null));
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ textAlign: 'center' }}>Chargement des données…</div>;
  
  return (
    <div style={{ padding: 20 }}>
      <h1 style={{ textAlign: 'center' }}>Graphiques dynamiques</h1>
      {datasets.map(({ title, data, valueKey }) => (
        <TrendGraph key={title} title={title} data={data} valueKey={valueKey} />
      ))}
    </div>
  );
};

export default Home;
