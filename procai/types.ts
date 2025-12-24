
export interface TechnicalSpec {
  quantity: string;
  size: string;
  material: string;
  attachments_found: string[];
  manufacturing_synonyms: string[];
  product_complexity: 'low' | 'medium' | 'high';
}

export interface Solicitation {
  id: string;
  title: string;
  agency: string;
  url: string;
  description: string;
  postedDate: string;
  specs?: TechnicalSpec;
  searchKeyword?: string;
  nested_links?: string[];
}

export interface Wholesaler {
  id: string;
  name: string;
  location: string;
  email: string;
  website: string;
  specialty: string;
  confidence: number;
  matched_from_solicitation_id?: string;
  product_matched?: string;
}

export interface AgentLog {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'crawling' | 'sql';
}

export interface SearchState {
  isSearching: boolean;
  stage: 'idle' | 'sam_crawling' | 'deep_spec_extraction' | 'thomasnet_sourcing' | 'database_optimization';
  progress: number;
  logs: AgentLog[];
  currentItem?: string;
  totalItems?: number;
  processedCount: number;
}
