import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Clock, Calendar, HelpCircle } from 'lucide-react';

interface ScheduleEditorProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

// Common presets for healthcare data sync schedules
const PRESETS = [
  { label: 'Every hour', value: '0 * * * *', description: 'At minute 0 of every hour' },
  { label: 'Every 6 hours', value: '0 */6 * * *', description: 'At midnight, 6am, noon, 6pm' },
  { label: 'Every 12 hours', value: '0 */12 * * *', description: 'At midnight and noon' },
  { label: 'Daily (midnight)', value: '0 0 * * *', description: 'Every day at 12:00 AM' },
  { label: 'Daily (6 AM)', value: '0 6 * * *', description: 'Every day at 6:00 AM' },
  { label: 'Weekly (Sunday)', value: '0 0 * * 0', description: 'Every Sunday at midnight' },
  { label: 'Weekly (Monday)', value: '0 6 * * 1', description: 'Every Monday at 6:00 AM' },
  { label: 'Monthly (1st)', value: '0 0 1 * *', description: 'First day of every month' },
];

// Parse cron expression into parts
function parseCron(cron: string): {
  minute: string;
  hour: string;
  dayOfMonth: string;
  month: string;
  dayOfWeek: string;
} {
  const parts = cron.trim().split(/\s+/);
  return {
    minute: parts[0] || '*',
    hour: parts[1] || '*',
    dayOfMonth: parts[2] || '*',
    month: parts[3] || '*',
    dayOfWeek: parts[4] || '*',
  };
}

// Build cron expression from parts
function buildCron(parts: {
  minute: string;
  hour: string;
  dayOfMonth: string;
  month: string;
  dayOfWeek: string;
}): string {
  return `${parts.minute} ${parts.hour} ${parts.dayOfMonth} ${parts.month} ${parts.dayOfWeek}`;
}

// Describe cron expression in human-readable format
function describeCron(cron: string): string {
  const parts = parseCron(cron);

  const minuteDesc = parts.minute === '*' ? 'every minute' : parts.minute === '0' ? 'at minute 0' : `at minute ${parts.minute}`;
  const hourDesc = parts.hour === '*' ? 'every hour' : parts.hour.includes('/') ? `every ${parts.hour.split('/')[1]} hours` : `at ${parts.hour}:00`;
  const dayDesc = parts.dayOfMonth === '*' ? 'every day' : `on day ${parts.dayOfMonth}`;
  const monthDesc = parts.month === '*' ? '' : `of month ${parts.month}`;
  const weekdayDesc = parts.dayOfWeek === '*' ? '' : (['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][parseInt(parts.dayOfWeek)] || `day ${parts.dayOfWeek}`);

  // Build description based on pattern
  if (parts.hour === '*' && parts.minute === '0') {
    return 'At the start of every hour';
  }
  if (parts.hour.includes('/') && parts.minute === '0') {
    return `Every ${parts.hour.split('/')[1]} hours`;
  }
  if (parts.dayOfWeek !== '*') {
    return `Every ${weekdayDesc} at ${parts.hour}:${parts.minute.padStart(2, '0')}`;
  }
  if (parts.dayOfMonth !== '*') {
    return `On day ${parts.dayOfMonth} of every month at ${parts.hour}:${parts.minute.padStart(2, '0')}`;
  }
  if (parts.hour !== '*' && parts.minute !== '*') {
    return `Daily at ${parts.hour}:${parts.minute.padStart(2, '0')}`;
  }

  return `${minuteDesc}, ${hourDesc}, ${dayDesc}${monthDesc ? `, ${monthDesc}` : ''}${weekdayDesc ? `, on ${weekdayDesc}` : ''}`;
}

export function ScheduleEditor({ value, onChange, className }: ScheduleEditorProps) {
  const [mode, setMode] = useState<'preset' | 'custom'>('preset');
  const [parts, setParts] = useState(parseCron(value || '0 0 * * *'));
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Initialize from value
  useEffect(() => {
    if (value) {
      const preset = PRESETS.find((p) => p.value === value);
      if (preset) {
        setSelectedPreset(preset.value);
        setMode('preset');
      } else {
        setParts(parseCron(value));
        setMode('custom');
      }
    }
  }, [value]);

  const handlePresetSelect = (presetValue: string) => {
    setSelectedPreset(presetValue);
    onChange(presetValue);
  };

  const handlePartChange = (part: keyof typeof parts, newValue: string) => {
    const newParts = { ...parts, [part]: newValue };
    setParts(newParts);
    onChange(buildCron(newParts));
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Mode Toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setMode('preset')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            mode === 'preset'
              ? 'bg-kirk text-white'
              : 'bg-navy-800/50 border border-navy-700/50 text-navy-300 hover:border-navy-600'
          )}
        >
          <Clock className="w-4 h-4 inline-block mr-1" />
          Presets
        </button>
        <button
          type="button"
          onClick={() => setMode('custom')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            mode === 'custom'
              ? 'bg-kirk text-white'
              : 'bg-navy-800/50 border border-navy-700/50 text-navy-300 hover:border-navy-600'
          )}
        >
          <Calendar className="w-4 h-4 inline-block mr-1" />
          Custom
        </button>
      </div>

      {/* Preset Selection */}
      {mode === 'preset' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 gap-2"
        >
          {PRESETS.map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => handlePresetSelect(preset.value)}
              className={cn(
                'p-3 rounded-lg text-left transition-all',
                'border',
                selectedPreset === preset.value
                  ? 'bg-kirk/10 border-kirk/30 text-white'
                  : 'bg-navy-800/30 border-navy-700/50 text-navy-300 hover:border-navy-600'
              )}
            >
              <p className="font-medium text-sm">{preset.label}</p>
              <p className="text-xs text-navy-400 mt-0.5">{preset.description}</p>
            </button>
          ))}
        </motion.div>
      )}

      {/* Custom Editor */}
      {mode === 'custom' && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="grid grid-cols-5 gap-2">
            {/* Minute */}
            <div>
              <label className="block text-xs text-navy-400 mb-1">Minute</label>
              <input
                type="text"
                value={parts.minute}
                onChange={(e) => handlePartChange('minute', e.target.value)}
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-white placeholder:text-navy-500',
                  'focus:outline-none focus:border-kirk/50'
                )}
                placeholder="*"
              />
            </div>

            {/* Hour */}
            <div>
              <label className="block text-xs text-navy-400 mb-1">Hour</label>
              <input
                type="text"
                value={parts.hour}
                onChange={(e) => handlePartChange('hour', e.target.value)}
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-white placeholder:text-navy-500',
                  'focus:outline-none focus:border-kirk/50'
                )}
                placeholder="*"
              />
            </div>

            {/* Day of Month */}
            <div>
              <label className="block text-xs text-navy-400 mb-1">Day</label>
              <input
                type="text"
                value={parts.dayOfMonth}
                onChange={(e) => handlePartChange('dayOfMonth', e.target.value)}
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-white placeholder:text-navy-500',
                  'focus:outline-none focus:border-kirk/50'
                )}
                placeholder="*"
              />
            </div>

            {/* Month */}
            <div>
              <label className="block text-xs text-navy-400 mb-1">Month</label>
              <input
                type="text"
                value={parts.month}
                onChange={(e) => handlePartChange('month', e.target.value)}
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-white placeholder:text-navy-500',
                  'focus:outline-none focus:border-kirk/50'
                )}
                placeholder="*"
              />
            </div>

            {/* Day of Week */}
            <div>
              <label className="block text-xs text-navy-400 mb-1">Weekday</label>
              <input
                type="text"
                value={parts.dayOfWeek}
                onChange={(e) => handlePartChange('dayOfWeek', e.target.value)}
                className={cn(
                  'w-full px-2 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-white placeholder:text-navy-500',
                  'focus:outline-none focus:border-kirk/50'
                )}
                placeholder="*"
              />
            </div>
          </div>

          {/* Help text */}
          <div className="p-3 rounded-lg bg-navy-800/30 border border-navy-700/50">
            <div className="flex items-start gap-2">
              <HelpCircle className="w-4 h-4 text-navy-400 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-navy-400">
                <p className="font-medium text-navy-300 mb-1">Cron Format</p>
                <p>Use * for any value, */n for every n units</p>
                <p className="mt-1 font-mono text-navy-500">
                  minute(0-59) hour(0-23) day(1-31) month(1-12) weekday(0-6)
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Current Expression & Description */}
      <div className="p-3 rounded-lg bg-navy-900/50 border border-navy-700/50">
        <div className="flex items-center justify-between">
          <span className="text-xs text-navy-400">Cron Expression:</span>
          <code className="text-sm text-kirk font-mono">{value || buildCron(parts)}</code>
        </div>
        <p className="text-xs text-navy-300 mt-2">
          {describeCron(value || buildCron(parts))}
        </p>
      </div>
    </div>
  );
}

export default ScheduleEditor;
