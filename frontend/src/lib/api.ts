export type ApiHealth = {
  service: string;
  status: "ok";
  version: string;
};

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function checkApiHealth(): Promise<ApiHealth> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`API health check failed with HTTP ${response.status}`);
    }

    const result = (await response.json()) as ApiHealth;
    if (result.status !== "ok" || result.service !== "DemandIQ API") {
      throw new Error("The API returned an unexpected health response.");
    }

    return result;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
