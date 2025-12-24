
import React, { useState } from 'react';

interface Props {
  onSearch: (category: string) => void;
  onClear: () => void;
  isSearching: boolean;
  progress: number;
}

const SearchControls: React.FC<Props> = ({ onSearch, onClear, isSearching, progress }) => {
  const [query, setQuery] = useState('Medical Instruments');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query);
    }
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
      <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Lead Generation</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Search Category</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <i className="fas fa-search text-sm"></i>
            </span>
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Surgical Equipment..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm outline-none"
              disabled={isSearching}
            />
          </div>
        </div>

        <button 
          type="submit"
          disabled={isSearching}
          className={`w-full py-3 rounded-xl font-bold text-sm transition-all flex items-center justify-center gap-2 ${
            isSearching 
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
            : 'bg-blue-600 text-white hover:bg-blue-700 active:scale-[0.98]'
          }`}
        >
          {isSearching ? (
            <>
              <i className="fas fa-spinner fa-spin"></i>
              Extracting Data...
            </>
          ) : (
            <>
              <i className="fas fa-bolt"></i>
              Generate Leads
            </>
          )}
        </button>

        <button 
          type="button"
          onClick={onClear}
          disabled={isSearching}
          className="w-full py-2.5 bg-white border border-slate-200 text-slate-600 rounded-xl font-semibold text-sm hover:bg-slate-50 transition-colors"
        >
          Clear Results
        </button>
      </form>

      {isSearching && (
        <div className="mt-6">
          <div className="flex justify-between text-xs font-semibold text-slate-500 mb-2">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div 
              className="bg-blue-600 h-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <p className="mt-2 text-[10px] text-slate-400 italic">
            Scanning industry directories and Thomasnet for verified contacts...
          </p>
        </div>
      )}
    </div>
  );
};

export default SearchControls;
