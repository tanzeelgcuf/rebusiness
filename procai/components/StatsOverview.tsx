
import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface Props {
  total: number;
  emails: number;
}

const StatsOverview: React.FC<Props> = ({ total, emails }) => {
  const data = [
    { name: 'With Email', value: emails },
    { name: 'Others', value: Math.max(0, total - emails) },
  ];
  const COLORS = ['#3b82f6', '#e2e8f0'];

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
      <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-6">Database Insights</h3>
      
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
          <p className="text-[10px] font-bold text-slate-400 uppercase">Total Records</p>
          <p className="text-2xl font-black text-slate-800">{total}</p>
        </div>
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
          <p className="text-[10px] font-bold text-slate-400 uppercase">Verified Emails</p>
          <p className="text-2xl font-black text-blue-600">{emails}</p>
        </div>
      </div>

      <div className="h-40 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={45}
              outerRadius={60}
              paddingAngle={5}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-lg font-bold text-slate-800">
            {total > 0 ? Math.round((emails / total) * 100) : 0}%
          </span>
          <span className="text-[10px] text-slate-400 font-bold uppercase">Accuracy</span>
        </div>
      </div>

      <ul className="mt-4 space-y-2">
        <li className="flex justify-between items-center text-xs font-medium">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            Contacts Ready
          </span>
          <span className="text-slate-500">{emails}</span>
        </li>
        <li className="flex justify-between items-center text-xs font-medium">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-slate-200"></span>
            Refining Info
          </span>
          <span className="text-slate-500">{total - emails}</span>
        </li>
      </ul>
    </div>
  );
};

export default StatsOverview;
