
import React, { useState } from 'react';
import { Wholesaler, Solicitation } from '../types';

interface Props {
  wholesalers: Wholesaler[];
  solicitations: Solicitation[];
  isSearching: boolean;
}

const DatabaseView: React.FC<Props> = ({ wholesalers, solicitations, isSearching }) => {
  const [activeTab, setActiveTab] = useState<'leads' | 'solicitations'>('leads');

  return (
    <div className="flex-grow flex flex-col bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      <div className="flex border-b border-slate-800 bg-slate-950/40">
        <button 
          onClick={() => setActiveTab('leads')}
          className={`px-6 py-4 text-xs font-bold uppercase tracking-widest transition-all border-b-2 ${
            activeTab === 'leads' ? 'border-blue-500 text-white' : 'border-transparent text-slate-500 hover:text-slate-300'
          }`}
        >
          <i className="fas fa-database mr-2 text-blue-500"></i>
          Wholesaler Database ({wholesalers.length})
        </button>
        <button 
          onClick={() => setActiveTab('solicitations')}
          className={`px-6 py-4 text-xs font-bold uppercase tracking-widest transition-all border-b-2 ${
            activeTab === 'solicitations' ? 'border-blue-500 text-white' : 'border-transparent text-slate-500 hover:text-slate-300'
          }`}
        >
          <i className="fas fa-file-contract mr-2 text-indigo-500"></i>
          Technical Solicitations ({solicitations.length})
        </button>
      </div>

      <div className="flex-grow overflow-auto custom-scrollbar bg-slate-950/20 p-4">
        {activeTab === 'leads' ? (
          <div className="grid grid-cols-1 gap-4">
            {wholesalers.length === 0 && !isSearching ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-600">
                <i className="fas fa-box-open text-4xl mb-4 opacity-20"></i>
                <p className="text-sm font-medium">No leads currently stored in database.</p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead className="text-[10px] font-bold text-slate-500 uppercase tracking-wider sticky top-0 bg-slate-950/90 z-10">
                  <tr>
                    <th className="px-4 py-3 border-b border-slate-800">Company</th>
                    <th className="px-4 py-3 border-b border-slate-800">Verified Email</th>
                    <th className="px-4 py-3 border-b border-slate-800">Match Accuracy</th>
                    <th className="px-4 py-3 border-b border-slate-800">Specialty</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {wholesalers.map((w, idx) => (
                    <tr key={w.id} className="hover:bg-slate-800/50 transition-colors">
                      <td className="px-4 py-4 border-b border-slate-800/50">
                        <div className="font-bold text-slate-200">{w.name}</div>
                        <div className="text-[10px] text-slate-500">{w.location}</div>
                      </td>
                      <td className="px-4 py-4 border-b border-slate-800/50">
                        <a href={`mailto:${w.email}`} className="text-blue-400 font-mono text-xs hover:underline decoration-blue-500/30">
                          {w.email}
                        </a>
                      </td>
                      <td className="px-4 py-4 border-b border-slate-800/50">
                        <div className="flex items-center gap-2">
                           <div className="w-16 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                              <div className="bg-green-500 h-full" style={{ width: `${w.confidence || 85}%` }}></div>
                           </div>
                           <span className="text-[10px] font-mono text-slate-400">{w.confidence || 85}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 border-b border-slate-800/50 text-xs text-slate-400">
                        {w.specialty}
                      </td>
                    </tr>
                  ))}
                  {isSearching && (
                    <tr className="animate-pulse">
                      <td colSpan={4} className="px-4 py-8 text-center text-blue-400 italic text-xs">
                        Fetching more results from Thomasnet...
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {solicitations.map(s => (
              <div key={s.id} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 hover:border-indigo-500/50 transition-all group">
                <div className="flex justify-between items-start mb-3">
                   <h4 className="text-sm font-bold text-slate-200 group-hover:text-indigo-400">{s.title}</h4>
                   <span className="text-[10px] bg-indigo-900/30 text-indigo-400 px-2 py-1 rounded font-bold">{s.agency}</span>
                </div>
                <p className="text-[11px] text-slate-500 line-clamp-2 mb-4">{s.description}</p>
                
                {s.specs ? (
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-[9px] font-bold text-slate-600 block uppercase">Quantity</span>
                      <span className="text-xs font-mono text-indigo-300">{s.specs.quantity}</span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded border border-slate-800">
                      <span className="text-[9px] font-bold text-slate-600 block uppercase">Material</span>
                      <span className="text-xs font-mono text-indigo-300">{s.specs.material}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-[10px] italic text-slate-600 mb-4">Specs analysis pending...</div>
                )}
                
                <a 
                  href={s.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-[10px] font-bold text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors"
                >
                  <i className="fas fa-external-link-alt text-[8px]"></i>
                  View on SAM.gov
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseView;
