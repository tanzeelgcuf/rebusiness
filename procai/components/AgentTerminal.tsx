
import React, { useState, useEffect, useRef } from 'react';
import { SearchState } from '../types';

interface Props {
  state: SearchState;
  onStart: (keywords: string[]) => void;
  onClear: () => void;
  onShowPython: () => void;
  onExportCsv: () => void;
  onExportSql: () => void;
  throttleValue?: number;
  onExpand: (category: string) => Promise<string[]>;
}

const AgentTerminal: React.FC<Props> = ({ state, onStart, onClear, onShowPython, onExportCsv, onExportSql, throttleValue, onExpand }) => {
  const [input, setInput] = useState('Medical Instruments');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [state.logs]);

  const handleStart = () => {
    const lines = input.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length > 0) {
      onStart(lines);
    }
  };

  const handleSmartExpand = async () => {
    const lines = input.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length > 0) {
      const expanded = await onExpand(lines[0]);
      setInput(expanded.join('\n'));
    }
  };

  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden flex flex-col h-full agent-glow">
      <div className="bg-slate-900 px-4 py-2 border-b border-slate-800 flex items-center justify-between">
        <div className="flex gap-1.5">
          <div className={`w-2.5 h-2.5 rounded-full ${state.isSearching ? 'bg-red-500 animate-pulse' : 'bg-red-500/50'}`}></div>
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50"></div>
          <div className={`w-2.5 h-2.5 rounded-full ${state.isSearching ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-green-500/50'}`}></div>
        </div>
        <span className="text-[10px] font-mono font-bold text-slate-500 tracking-widest uppercase">ProcureLink_Terminal_V2.sh</span>
        <button 
          onClick={onShowPython}
          className="text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-colors uppercase"
        >
          [Source Code]
        </button>
      </div>

      <div className="p-4 bg-slate-950 border-b border-slate-800 flex flex-col gap-3">
        <div className="flex justify-between items-center">
          <label className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Bulk Category List:</label>
          <button 
            onClick={handleSmartExpand}
            disabled={state.isSearching || !input.trim()}
            className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors uppercase"
            title="Expand into 15 sub-niches to reach 500+ lead target"
          >
            <i className="fas fa-expand-arrows-alt"></i> Niche Expand
          </button>
        </div>
        <textarea 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter categories (one per line)..."
          className="w-full h-32 bg-slate-900/50 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 outline-none focus:border-blue-500/50 transition-all resize-none"
          disabled={state.isSearching}
        />
        <button 
          onClick={handleStart}
          disabled={state.isSearching || !input.trim()}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white rounded-lg text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2"
        >
          {state.isSearching ? <i className="fas fa-circle-notch fa-spin text-sm"></i> : <i className="fas fa-play"></i>}
          {state.isSearching ? 'Processing...' : 'Deploy Global Sourcing Agent'}
        </button>
      </div>

      <div 
        ref={scrollRef}
        className="flex-grow overflow-y-auto p-4 font-mono text-[11px] space-y-1.5 custom-scrollbar leading-relaxed"
      >
        {state.logs.length === 0 ? (
          <div className="text-slate-600 italic">SYSTEM READY. TARGET: 500 LEADS. AWAITING INPUT...</div>
        ) : (
          state.logs.map((log) => (
            <div key={log.id} className="flex gap-3">
              <span className="text-slate-600 select-none shrink-0">{log.timestamp}</span>
              <span className={`
                ${log.type === 'success' ? 'text-emerald-400 font-bold' : ''}
                ${log.type === 'error' ? 'text-rose-400 font-bold' : ''}
                ${log.type === 'warning' ? 'text-amber-400 italic' : ''}
                ${log.type === 'crawling' ? 'text-blue-400' : ''}
                ${log.type === 'sql' ? 'text-indigo-400' : ''}
                ${log.type === 'info' ? 'text-slate-400' : ''}
              `}>
                <span className="font-bold opacity-60 mr-2">[{log.type.toUpperCase()}]</span>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>

      {state.isSearching && (
        <div className="p-3 bg-slate-900 border-t border-slate-800 relative">
          <div className="scanner-line absolute left-0 right-0 z-0"></div>
          <div className="relative z-10 flex justify-between items-center text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-tighter">
            <span className="truncate max-w-[70%]">ACTIVE: {state.currentItem}</span>
            <span>{state.progress}%</span>
          </div>
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div 
              className="bg-blue-500 h-full transition-all duration-500"
              style={{ width: `${state.progress}%` }}
            ></div>
          </div>
        </div>
      )}

      <div className="bg-slate-950 p-2 flex items-center justify-between border-t border-slate-800 gap-4">
        <div className="flex gap-3 items-center">
          <button 
            onClick={onClear}
            className="text-[9px] text-slate-600 hover:text-slate-400 font-bold uppercase transition-colors"
          >
            Clear logs
          </button>
          <div className="w-px h-3 bg-slate-800 self-center"></div>
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${state.isSearching ? 'bg-blue-500 animate-ping' : 'bg-slate-700'}`}></div>
            <span className="text-[9px] text-slate-500 font-mono uppercase">
              {throttleValue ? `Rate Limit Throttling: ${(throttleValue/1000).toFixed(1)}s` : 'System Idle'}
            </span>
          </div>
        </div>
        <div className="text-[9px] text-slate-700 font-mono font-bold">
          BATCH: {state.processedCount}/{state.totalItems || 0}
        </div>
      </div>
    </div>
  );
};

export default AgentTerminal;
