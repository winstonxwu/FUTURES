const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Position {
  ticker: string;
  quantity: number;
  entry_price: number;
  current_price?: number;
  pnl?: number;
  pnl_pct?: number;
}

export interface TradeRequest {
  ticker: string;
  action: 'BUY' | 'SELL';
  s_final?: number;
  quantity?: number;
  reason?: string;
}

export interface TradeResponse {
  success: boolean;
  order_id?: string;
  ticker: string;
  action: string;
  quantity: number;
  price?: number;
  message: string;
  timestamp: string;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  broker_capital: number;
  num_positions: number;
  num_events: number;
}

export interface CapitalInfo {
  available_capital: number;
  total_exposure: number;
}

export interface PositionsResponse {
  positions: Position[];
  total_exposure: number;
  capital: number;
}

class APIClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(error.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  async executeTrade(trade: TradeRequest): Promise<TradeResponse> {
    return this.request<TradeResponse>('/execution/trade', {
      method: 'POST',
      body: JSON.stringify(trade),
    });
  }

  async getPositions(): Promise<PositionsResponse> {
    return this.request<PositionsResponse>('/execution/positions');
  }

  async getCapital(): Promise<CapitalInfo> {
    return this.request<CapitalInfo>('/execution/capital');
  }
}

export const apiClient = new APIClient();
