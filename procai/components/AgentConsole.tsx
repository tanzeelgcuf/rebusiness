
import React, { useState, useEffect, useRef } from 'react';
import { SearchState } from '../types';

interface Props {
  state: SearchState;
  onStart: (query: string) => void;
  onClear: () => void;
}

const AgentConsole: React.FC<Props> = ({ state, onStart, onClear }) => {
  const [query, setQuery] = useState('Medical Instruments');
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.logs]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl flex flex-col overflow-hidden">
      <div className="p-6 border-b border-slate-800 bg-slate-950/30">
        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
          <i className="fas fa-terminal"></i> Mission Parameters
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-[10px] font-bold text-slate-500 uppercase mb-2">Category Search</label>
            <input 
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={state.isSearching}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 outline-none focus:border-blue-500/50 transition-colors"
              placeholder="e.g. Surgical Equipment"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button 
              onClick={() => onStart(query)}
              disabled={state.isSearching}
              className={`py-3 rounded-xl text-xs font-bold uppercase tracking-widest transition-all flex items-center justify-center gap-2 ${
                state.isSearching 
                ? 'bg-slate-800 text-slate-600' 
                : 'bg-blue-600 text-white hover:bg-blue-500 active:scale-95 shadow-lg shadow-blue-900/20'
              }`}
            >
              <i className={state.isSearching ? "fas fa-sync fa-spin" : "fas fa-play"}></i>
              {state.isSearching ? "Running" : "Deploy Agent"}
            </button>
            <button 
              onClick={onClear}
              disabled={state.isSearching}
              className="py-3 rounded-xl text-xs font-bold uppercase tracking-widest text-slate-400 border border-slate-800 hover:bg-slate-800 transition-colors"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      <div className="flex-grow bg-slate-950 p-4 font-mono text-[11px] h-64 overflow-y-auto custom-scrollbar">
        {state.logs.length === 0 ? (
          <div className="text-slate-700 italic flex items-center gap-2 h-full justify-center">
             System Ready. Waiting for Deployment Instructions.
          </div>
        ) : (
          <div className="space-y-1.5">
            {state.logs.map((log, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-slate-600">[{log.timestamp}]</span>
                <span className={`
                  ${log.type === 'success' ? 'text-green-500' : ''}
                  ${log.type === 'error' ? 'text-red-500' : ''}
                  ${log.type === 'warning' ? 'text-yellow-500' : ''}
                  ${log.type === 'crawling' ? 'text-blue-400 animate-pulse' : ''}
                  ${log.type === 'info' ? 'text-slate-300' : ''}
                `}>
                  {log.type === 'crawling' && <i className="fas fa-spider mr-1.5"></i>}
                  {log.message}
                </span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>

      {state.isSearching && (
        <div className="px-4 py-2 bg-blue-900/10 border-t border-slate-800">
           <div className="flex justify-between text-[10px] font-bold text-blue-400/80 mb-1.5">
              <span className="animate-pulse italic">AGENT_STAGE: {state.stage.replace('_', ' ').toUpperCase()}</span>
              <span>{state.progress}%</span>
           </div>
           <div className="w-full bg-slate-900 h-1 rounded-full overflow-hidden">
              <div 
                className="bg-blue-500 h-full transition-all duration-700"
                style={{ width: `${state.progress}%` }}
              ></div>
           </div>
        </div>
      )}
    </div>
  );
};

export default AgentConsole;
