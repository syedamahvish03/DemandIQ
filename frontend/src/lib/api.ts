export type ApiHealth = {
  service: string;
  status: "ok";
  version: string;
};

export type ForecastRow = {
  date: string;
  store: string | number;
  item: string | number;
  forecast_sales: number;
  forecast_step: number;
};

export type ForecastResult = {
  status: "success";
  model: string;
  metadata: {
    horizon_days: number;
    series_count: number;
    forecast_rows: number;
    training_rows_used: number;
    history_end: string;
    forecast_start: string;
    forecast_end: string;
  };
  quality_report: {
    rows_received: number;
    rows_valid: number;
    invalid_dates: number;
    invalid_sales: number;
    negative_sales: number;
    missing_identifiers: number;
    duplicate_rows: number;
    errors: string[];
    warnings: string[];
  };
  forecast: ForecastRow[];
};

import { supabase } from "./supabase";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function authenticatedFetch(url: string, init: RequestInit): Promise<Response> {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw new Error("Unable to verify your sign-in session. Please sign in again.");
  const accessToken = data.session?.access_token;
  if (!accessToken) throw new Error("Please sign in before using forecasting or inventory tools.");

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(url, { ...init, headers });
}

async function readApiError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    const detail = payload?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) {
      const warnings = detail.quality_report?.warnings ?? [];
      return [detail.message, ...warnings].join(" ");
    }
    return `Request failed with HTTP ${response.status}.`;
  } catch {
    return `Request failed with HTTP ${response.status}.`;
  }
}

export async function checkApiHealth(): Promise<ApiHealth> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`API health check failed with HTTP ${response.status}`);

    const result = (await response.json()) as ApiHealth;
    if (result.status !== "ok" || result.service !== "DemandIQ API") {
      throw new Error("The API returned an unexpected health response.");
    }
    return result;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function generateForecast(
  file: File,
  horizonDays: 7 | 15 | 30,
): Promise<ForecastResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("horizon_days", String(horizonDays));

  const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/forecasts`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error(await readApiError(response));
  return (await response.json()) as ForecastResult;
}

export type InventoryRecommendation = {
  store: string | number;
  item: string | number;
  on_hand: number;
  on_order: number;
  backorders: number;
  lead_time_days: number;
  review_period_days: number;
  avg_daily_demand: number;
  daily_demand_std: number;
  demand_records: number;
  safety_stock: number;
  demand_basis: "future_forecast" | "historical_average";
  forecast_lead_demand: number;
  forecast_protection_demand: number;
  reorder_point: number;
  target_stock: number;
  inventory_position: number;
  recommended_order_qty: number;
  reorder_required: boolean;
};

export type InventoryResult = {
  status: "success";
  demand_basis: "future_forecast";
  metadata: {
    excluded_input_rows: number;
    lookback_days: number;
    demand_window_start?: string;
    demand_window_end?: string;
    complete_recommendations: number;
    forecast_horizon_days: number;
    forecast_rows: number;
    forecast_start: string;
    forecast_end: string;
  };
  recommendations: InventoryRecommendation[];
};

export async function downloadInventoryTemplate(salesFile: File): Promise<Blob> {
  const formData = new FormData();
  formData.append("sales_file", salesFile);
  const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/inventory/template`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error(await readApiError(response));
  return response.blob();
}

export async function generateInventoryRecommendations(
  salesFile: File,
  inventoryFile: File,
  forecastHorizonDays: 7 | 15 | 30,
): Promise<InventoryResult> {
  const formData = new FormData();
  formData.append("sales_file", salesFile);
  formData.append("inventory_file", inventoryFile);
  formData.append("lookback_days", "28");
  formData.append("service_level_z", "1.65");
  formData.append("forecast_horizon_days", String(forecastHorizonDays));
  const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/inventory/recommendations`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error(await readApiError(response));
  return (await response.json()) as InventoryResult;
}


export type SalesValidationResult = {
  status: "success";
  can_import: boolean;
  preview_limit: number;
  preview_rows: Array<{
    date: string;
    store: string | number;
    item: string | number;
    sales: number;
  }>;
  validated_rows?: Array<{
    date: string;
    store: string | number;
    item: string | number;
    sales: number;
  }>;
  quality_report: {
    rows_received: number;
    rows_valid: number;
    invalid_dates: number;
    invalid_sales: number;
    negative_sales: number;
    missing_identifiers: number;
    duplicate_rows: number;
    errors: string[];
    warnings: string[];
  };
  blocking_issues: string[];
  excluded_rows: number;
};

export async function validateSalesCsv(
  file: File,
  includeRecords = false,
): Promise<SalesValidationResult> {
  const formData = new FormData();
  formData.append("file", file);
  const query = includeRecords ? "?include_records=true" : "";
  const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/sales/validate${query}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error(await readApiError(response));
  return (await response.json()) as SalesValidationResult;
}
