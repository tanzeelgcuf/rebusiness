
import React from 'react';
import { Wholesaler } from '../types';

interface Props {
  wholesalers: Wholesaler[];
}

const WholesalerList: React.FC<Props> = ({ wholesalers }) => {
  if (wholesalers.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {wholesalers.map((item) => (
        <div 
          key={item.id} 
          className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-blue-200 transition-all group"
        >
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1">
              <h4 className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                {item.name}
              </h4>
              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-1">
                <i className="fas fa-map-marker-alt text-blue-400"></i>
                {item.location}
              </p>
            </div>
            <span className="px-2 py-1 bg-blue-50 text-blue-600 text-[10px] font-bold uppercase rounded tracking-wider">
              Wholesaler
            </span>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 border border-slate-100">
              <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-slate-400 shadow-sm">
                <i className="fas fa-envelope text-xs"></i>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-slate-400 uppercase font-bold tracking-tight">Direct Email</p>
                <a 
                  href={`mailto:${item.email}`} 
                  className="text-sm font-semibold text-slate-700 truncate block hover:text-blue-600 transition-colors"
                >
                  {item.email}
                </a>
              </div>
            </div>

            <div className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 border border-slate-100">
              <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-slate-400 shadow-sm">
                <i className="fas fa-globe text-xs"></i>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-slate-400 uppercase font-bold tracking-tight">Website</p>
                <a 
                  href={item.website.startsWith('http') ? item.website : `https://${item.website}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm font-semibold text-slate-700 truncate block hover:text-blue-600 transition-colors"
                >
                  {item.website.replace(/(^\w+:|^)\/\//, '')}
                </a>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-50">
            <p className="text-xs text-slate-500 italic">
              <span className="font-bold text-slate-700 not-italic">Focus:</span> {item.specialty}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default WholesalerList;
