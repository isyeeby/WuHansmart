/**
 * 投资分析模块 API 服务
 */
import { apiClient } from '../config/api';

export interface InvestmentInput {
  district: string;
  property_price: number;  // 房产总价（万元）
  area_sqm: number;        // 面积（平米）
  bedroom_count: number;   // 卧室数
  expected_daily_price: number;  // 期望日租金
  occupancy_rate?: number; // 预期入住率，默认0.65
  operating_costs_monthly?: number;  // 月运营成本，默认2000
  renovation_cost?: number;  // 装修成本（万元），默认10
  loan_ratio?: number;       // 贷款比例，默认0.5
  loan_rate?: number;        // 贷款利率，默认0.045
  loan_years?: number;       // 贷款年限，默认20
}

export interface CalculationBasis {
  annual_roi_formula: string;
  monthly_net_formula: string;
  monthly_payment_formula: string;
  payback_period_formula: string;
  assumptions: string[];
}

export interface InvestmentResult {
  total_investment: number;
  down_payment: number;
  loan_amount: number;
  monthly_payment: number;
  monthly_revenue: number;
  monthly_net_income: number;
  annual_roi: number;
  payback_period: number;
  investment_score: number;
  risk_level: string;
  recommendation: string;
  calculation_basis?: CalculationBasis;
}

export interface CashflowData {
  month: string;
  revenue: number;
  cost: number;
  net_cashflow: number;
  cumulative_cashflow: number;
}

export interface CashflowForecast {
  unit_id: string;
  forecast_months: number;
  cashflow: CashflowData[];
  total_revenue: number;
  total_cost: number;
  total_net_cashflow: number;
}

export interface SensitivityMatrixItem {
  price: number;
  occupancy: number;
  monthly_net: number;
  annual_roi: number;
}

export interface SensitivityAnalysis {
  district: string;
  base_price: number;
  base_occupancy: number;
  baseline_capital_yuan?: number;
  price_variations: string[];
  occupancy_variations: string[];
  sensitivity_matrix: SensitivityMatrixItem[][];
  assumptions?: string[];
}

export interface InvestmentRanking {
  district: string;
  roi_score: number;
  avg_price: number;
  occupancy_rate: number;
  recommendation: string;
  occupancy_basis?: string;
  calendar_sample_rows?: number | null;
  calendar_unavailable_share_pct?: number | null;
  estimated_roi?: number | null;
  revenue_intensity_ratio?: number | null;
  estimated_monthly_revenue?: number;
  investment_score?: number;
  risk_level?: string;
  data_source_note?: string;
}

export interface InvestmentRankingResponse {
  data: InvestmentRanking[];
  data_source_note: string;
  calculation_basis: {
    price_score: string;
    rating_score: string;
    heat_score: string;
    activity_score: string;
    weights: Record<string, number>;
    occupancy_rate_formula: string;
    note: string;
  };
}

export interface InvestmentOpportunity {
  unit_id: string;
  title: string;
  district: string;
  current_price: number;
  predicted_price: number;
  gap_rate: number;
  rating: number;
  estimated_annual_roi: number;
  investment_score: number;
  prediction_source?: string;
}

export interface InvestmentOpportunitiesResponse {
  data: InvestmentOpportunity[];
  data_source_note: string;
  calculation_basis: {
    predicted_price_source: string;
    estimated_roi_formula: string;
    assumptions: string[];
  };
}

/**
 * 投资计算器
 */
export const calculateInvestment = async (data: InvestmentInput): Promise<InvestmentResult> => {
  const response = await apiClient.post('/api/investment/calculate', data);
  return response.data;
};

/**
 * 现金流预测
 */
export const getCashflowForecast = async (unitId: string, months: number = 24): Promise<CashflowForecast> => {
  const response = await apiClient.get(`/api/investment/cashflow/${unitId}`, {
    params: { months }
  });
  return response.data;
};

/**
 * 敏感性分析
 */
export const getSensitivityAnalysis = async (
  district: string,
  basePrice: number = 200,
  baseOccupancy: number = 0.65,
  baselineCapitalYuan: number = 500_000
): Promise<SensitivityAnalysis> => {
  const response = await apiClient.get('/api/investment/sensitivity-analysis', {
    params: {
      district,
      base_price: basePrice,
      base_occupancy: baseOccupancy,
      baseline_capital_yuan: baselineCapitalYuan,
    }
  });
  return response.data;
};

/**
 * 投资收益率排行榜
 */
export const getInvestmentRanking = async (limit: number = 10): Promise<InvestmentRankingResponse | InvestmentRanking[]> => {
  const response = await apiClient.get('/api/investment/ranking', {
    params: { limit }
  });
  return response.data;
};

/**
 * 投资机会推荐
 */
export const getInvestmentOpportunities = async (
  minRoi: number = 10,
  maxBudget?: number
): Promise<InvestmentOpportunitiesResponse | InvestmentOpportunity[]> => {
  const response = await apiClient.get('/api/investment/opportunities', {
    params: { min_roi: minRoi, max_budget: maxBudget }
  });
  return response.data;
};
