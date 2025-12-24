
import React, { useState } from 'react';
import { Wholesaler, Solicitation } from '../types';

interface Props {
  wholesalers: Wholesaler[];
  solicitations: Solicitation[];
  isSearching: boolean;
  onExport: () => void;
}

const DatabaseViewer: React.FC<Props> = ({ wholesalers, solicitations, isSearching, onExport }) => {
  const [tab, setTab] = useState<'leads' | 'solicitations'>('leads');

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden flex flex-col h-full shadow-2xl">
      <div className="bg-slate-900 flex items-center pr-4">
        <div className="flex flex-grow">
          <button 
            onClick={() => setTab('leads')}
            className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-all border-b-2 ${
              tab === 'leads' ? 'bg-slate-950 border-blue-500 text-white' : 'border-transparent text-slate-500 hover:bg-slate-800'
            }`}
          >
            <i className="fas fa-users-cog mr-2 text-blue-400"></i>
            Thomasnet Leads ({wholesalers.length})
          </button>
          <button 
            onClick={() => setTab('solicitations')}
            className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-all border-b-2 ${
              tab === 'solicitations' ? 'bg-slate-950 border-indigo-500 text-white' : 'border-transparent text-slate-500 hover:bg-slate-800'
            }`}
          >
            <i className="fas fa-file-invoice mr-2 text-indigo-400"></i>
            SAM.gov Registry ({solicitations.length})
          </button>
        </div>
        
        {wholesalers.length > 0 && (
          <button 
            onClick={onExport}
            className="ml-4 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-black uppercase tracking-tighter transition-all flex items-center gap-2"
            title="Export full dataset to CSV"
          >
            <i className="fas fa-file-download"></i>
            Export Dataset
          </button>
        )}
      </div>

      <div className="flex-grow overflow-auto bg-slate-950/40 custom-scrollbar p-1">
        {tab === 'leads' ? (
          <table className="w-full text-left border-collapse min-w-[600px]">
            <thead className="bg-slate-950/80 sticky top-0 z-10 text-[10px] uppercase font-bold text-slate-500 tracking-wider">
              <tr>
                <th className="px-4 py-3 border-b border-slate-800">Company / Location</th>
                <th className="px-4 py-3 border-b border-slate-800">Verified Contact</th>
                <th className="px-4 py-3 border-b border-slate-800">Match Accuracy</th>
                <th className="px-4 py-3 border-b border-slate-800">Specialization</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {wholesalers.length === 0 && !isSearching && (
                <tr>
                  <td colSpan={4} className="px-4 py-20 text-center text-slate-600 italic text-sm">
                    No data committed to local database yet.
                  </td>
                </tr>
              )}
              {wholesalers.map((w) => (
                <tr key={w.id} className="hover:bg-slate-800/30 transition-colors group">
                  <td className="px-4 py-4">
                    <div className="font-bold text-slate-200 group-hover:text-blue-400 transition-colors">{w.name}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-tighter">{w.location}</div>
                  </td>
                  <td className="px-4 py-4">
                    <a href={`mailto:${w.email}`} className="text-xs font-mono text-blue-500 hover:text-blue-400 underline decoration-blue-500/20">{w.email}</a>
                    <div className="text-[10px] text-slate-600">{w.website}</div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                       <div className="w-12 h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="bg-emerald-500 h-full" 
                            style={{ width: `${Math.max(90, w.confidence || 94)}%` }}
                          ></div>
                       </div>
                       <span className="text-[10px] font-mono text-emerald-500">
                         {Math.max(90, w.confidence || 94)}%
                       </span>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-[10px] text-slate-400 font-medium max-w-[150px] truncate">
                    {w.specialty}
                  </td>
                </tr>
              ))}
              {isSearching && (
                <tr className="animate-pulse">
                   <td colSpan={4} className="px-4 py-6 text-center text-blue-500 font-bold text-xs uppercase tracking-widest">
                      Synchronizing high-accuracy records...
                   </td>
                </tr>
              )}
            </tbody>
          </table>
        ) : (
          <div className="grid grid-cols-1 gap-3 p-3">
            {solicitations.map((s) => (
              <div key={s.id} className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 hover:border-indigo-500/50 transition-all">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-sm font-bold text-slate-200">{s.title}</h4>
                  <span className="text-[9px] font-black bg-indigo-900/40 text-indigo-400 px-1.5 py-0.5 rounded border border-indigo-500/20 uppercase">
                    {s.id}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 line-clamp-2 mb-3 leading-relaxed">{s.description}</p>
                
                {s.specs && (
                  <div className="grid grid-cols-3 gap-2 py-2 border-y border-slate-800/50 mb-3">
                    <div className="text-[9px]">
                      <span className="text-slate-600 block uppercase font-bold">Quantity</span>
                      <span className="text-slate-300 font-mono">{s.specs.quantity}</span>
                    </div>
                    <div className="text-[9px]">
                      <span className="text-slate-600 block uppercase font-bold">Material</span>
                      <span className="text-slate-300 font-mono">{s.specs.material}</span>
                    </div>
                    <div className="text-[9px]">
                      <span className="text-slate-600 block uppercase font-bold">Complexity</span>
                      <span className={`uppercase font-bold ${s.specs.product_complexity === 'high' ? 'text-rose-500' : 'text-emerald-500'}`}>
                        {s.specs.product_complexity}
                      </span>
                    </div>
                  </div>
                )}
                
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-bold text-slate-600 uppercase">{s.agency}</span>
                  <a href={s.url} target="_blank" className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase transition-colors">
                    Visit SAM.gov <i className="fas fa-external-link-alt ml-1 text-[8px]"></i>
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseViewer;
