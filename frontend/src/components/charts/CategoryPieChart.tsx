import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';
import type { PieLabelRenderProps } from 'recharts';
import { motion } from 'framer-motion';
import { PieChart as PieChartIcon } from 'lucide-react';

interface CategoryData {
  name: string;
  value: number;
  color: string;
  [key: string]: string | number;
}

interface CategoryPieChartProps {
  data: CategoryData[];
  title?: string;
}

interface TooltipPayload {
  name: string;
  value: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  total: number;
}

interface LegendPayloadItem {
  value: string;
  color: string;
}

function CustomTooltipContent({ active, payload, total }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const item = payload[0];
    const percentage = ((item.value / total) * 100).toFixed(1);
    return (
      <div className="bg-navy-800 border border-navy-600 rounded-lg p-3 shadow-xl">
        <p className="text-white font-medium mb-1">{item.name}</p>
        <p className="text-navy-300 text-sm">
          Count: {item.value.toLocaleString()}
        </p>
        <p className="text-navy-400 text-sm">{percentage}% of total</p>
      </div>
    );
  }
  return null;
}

function renderCustomLabel(props: PieLabelRenderProps) {
  const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;

  if (typeof cx !== 'number' || typeof cy !== 'number' ||
      typeof midAngle !== 'number' || typeof innerRadius !== 'number' ||
      typeof outerRadius !== 'number' || typeof percent !== 'number') {
    return null;
  }

  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent < 0.05) return null;

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      className="text-xs font-medium"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

interface CustomLegendProps {
  payload?: LegendPayloadItem[];
}

function CustomLegend({ payload }: CustomLegendProps) {
  if (!payload) return null;
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-4">
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-navy-300 text-sm">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export function CategoryPieChart({
  data,
  title = 'Flags by Category',
}: CategoryPieChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);

  // Generate accessible text description
  const sortedData = [...data].sort((a, b) => b.value - a.value);
  const topCategory = sortedData[0];
  const accessibleDescription = `${title}. Total flags: ${total.toLocaleString()}. ` +
    `Largest category: ${topCategory?.name} with ${topCategory?.value.toLocaleString()} flags ` +
    `(${((topCategory?.value / total) * 100).toFixed(1)}%).`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-navy-800/50 rounded-xl border border-navy-700/50 p-6"
      role="figure"
      aria-label={accessibleDescription}
    >
      {/* Screen reader summary */}
      <div className="sr-only">
        <h4>{title}</h4>
        <p>Total flags: {total.toLocaleString()}</p>
        <table>
          <caption>Flag distribution by category</caption>
          <thead>
            <tr>
              <th>Category</th>
              <th>Count</th>
              <th>Percentage</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((d, idx) => (
              <tr key={idx}>
                <td>{d.name}</td>
                <td>{d.value.toLocaleString()}</td>
                <td>{((d.value / total) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-white font-semibold text-lg">{title}</h3>
          <p className="text-navy-400 text-sm mt-1">
            Total flags: {total.toLocaleString()}
          </p>
        </div>
        <div className="p-2 rounded-lg bg-navy-700/50" aria-hidden="true">
          <PieChartIcon className="w-5 h-5 text-kirk" />
        </div>
      </div>

      <div className="h-[280px]" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="45%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
              labelLine={false}
              label={renderCustomLabel}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltipContent total={total} />} />
            <Legend content={<CustomLegend />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Center label */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ marginTop: '-40px' }}>
        <div className="text-center">
          <p className="text-2xl font-bold text-white">{total.toLocaleString()}</p>
          <p className="text-navy-400 text-xs">Total</p>
        </div>
      </div>
    </motion.div>
  );
}
