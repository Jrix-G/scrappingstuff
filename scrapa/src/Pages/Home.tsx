import React, { useEffect, useState } from 'react';
import TrendGraph from './TrendGraph';

type Dataset = {
  title: string;
  data: { date: string; value: number }[];
  valueKey: string;
};

const Home = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  useEffect(() => {
    fetch('http://localhost:3001/api/graphs')
      .then((res) => res.json())
      .then(async (fileList: string[]) => {
        const datasets = await Promise.all(
          fileList.map(async (file) => {
            const res = await fetch(`http://localhost:3001/graphs/${file}`);
            const rawData = await res.json();
            const valueKey = Object.keys(rawData[0]).find((k) => k !== 'date') || '';
            const title = file.replace('trends_', '').replace('.json', '');
            const data = rawData.map((item: any) => ({
              date: item.date.split(' ')[0],
              value: item[valueKey],
            }));
            return { title, data, valueKey: 'value' };
          })
        );
        setDatasets(datasets);
      });
  }, []);

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
