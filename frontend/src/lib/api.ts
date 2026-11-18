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

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

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

  const response = await fetch(`${API_BASE_URL}/api/v1/forecasts`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error(await readApiError(response));
  return (await response.json()) as ForecastResult;
}
