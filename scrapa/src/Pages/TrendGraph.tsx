import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

type Props = {
  title: string;
  data: { date: string; value: number }[];
  valueKey: string;
};

const TrendGraph = ({ title, data, valueKey }: Props) => {
  return (
    <div style={{ marginBottom: 40 }}>
      <h3 style={{ textAlign: 'center', textTransform: 'capitalize' }}>{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid stroke="#ccc" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey={valueKey} stroke="#007bff" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TrendGraph;
