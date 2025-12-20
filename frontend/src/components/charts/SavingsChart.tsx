import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { motion } from 'framer-motion';
import { TrendingUp } from 'lucide-react';
import { formatCurrency } from '@/utils/mockData';

interface SavingsDataPoint {
  month: string;
  savings: number;
  claims?: number;
}

interface SavingsChartProps {
  data: SavingsDataPoint[];
  title?: string;
  showClaims?: boolean;
}

interface TooltipPayload {
  value: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  showClaims?: boolean;
}

function CustomTooltip({ active, payload, label, showClaims }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-navy-800 border border-navy-600 rounded-lg p-3 shadow-xl">
        <p className="text-white font-medium mb-1">{label}</p>
        <p className="text-kirk text-sm">
          Savings: {formatCurrency(payload[0].value)}
        </p>
        {showClaims && payload[1] && (
          <p className="text-navy-300 text-sm">
            Claims: {payload[1].value.toLocaleString()}
          </p>
        )}
      </div>
    );
  }
  return null;
}

export function SavingsChart({
  data,
  title = 'Savings Over Time',
  showClaims = false,
}: SavingsChartProps) {
  const totalSavings = data.reduce((sum, d) => sum + d.savings, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-navy-800/50 rounded-xl border border-navy-700/50 p-6"
    >
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-white font-semibold text-lg">{title}</h3>
          <p className="text-navy-400 text-sm mt-1">
            Total: {formatCurrency(totalSavings)}
          </p>
        </div>
        <div className="flex items-center gap-2 text-safe bg-safe/10 px-3 py-1.5 rounded-lg">
          <TrendingUp className="w-4 h-4" />
          <span className="text-sm font-medium">+12.4% YoY</span>
        </div>
      </div>

      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="savingsGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#334155"
              vertical={false}
            />
            <XAxis
              dataKey="month"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94A3B8', fontSize: 12 }}
              dy={10}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94A3B8', fontSize: 12 }}
              tickFormatter={(value) => formatCurrency(value)}
              dx={-10}
            />
            <Tooltip content={<CustomTooltip showClaims={showClaims} />} />
            <Area
              type="monotone"
              dataKey="savings"
              stroke="#8B5CF6"
              strokeWidth={2}
              fill="url(#savingsGradient)"
              dot={false}
              activeDot={{
                r: 6,
                stroke: '#8B5CF6',
                strokeWidth: 2,
                fill: '#1E293B',
              }}
            />
            {showClaims && (
              <Line
                type="monotone"
                dataKey="claims"
                stroke="#06B6D4"
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 5"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center gap-6 mt-4 pt-4 border-t border-navy-700/50">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-kirk" />
          <span className="text-navy-400 text-sm">Savings</span>
        </div>
        {showClaims && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-0.5 bg-teal border-dashed" />
            <span className="text-navy-400 text-sm">Claims Volume</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
