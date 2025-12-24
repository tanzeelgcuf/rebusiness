
import React from 'react';

interface Props {
  sources: any[];
}

const SourcesList: React.FC<Props> = ({ sources }) => {
  if (sources.length === 0) return null;

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
      <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
        <i className="fas fa-link text-blue-500"></i>
        Grounding Sources
      </h3>
      <div className="space-y-3 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
        {sources.map((source, idx) => {
          const item = source.web;
          if (!item) return null;
          return (
            <a 
              key={idx} 
              href={item.uri} 
              target="_blank" 
              rel="noopener noreferrer"
              className="block p-3 rounded-xl bg-slate-50 hover:bg-blue-50 border border-slate-100 hover:border-blue-100 transition-all group"
            >
              <h4 className="text-xs font-bold text-slate-700 group-hover:text-blue-600 truncate mb-1">
                {item.title}
              </h4>
              <p className="text-[10px] text-slate-400 truncate font-mono">
                {item.uri}
              </p>
            </a>
          );
        })}
      </div>
      <p className="mt-4 text-[10px] text-slate-400 leading-relaxed italic">
        *Data is retrieved using real-time search grounding to ensure maximum relevance and currency.
      </p>
    </div>
  );
};

export default SourcesList;
