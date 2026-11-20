import type { ForecastResult, InventoryResult } from "./api";
import { supabase } from "./supabase";

export type AnalysisType = "forecast" | "inventory";

export type SavedAnalysis = {
  id: string;
  workspace_id: string;
  owner_id: string;
  analysis_type: AnalysisType;
  title: string;
  input_filename: string | null;
  horizon_days: number | null;
  summary: Record<string, unknown>;
  result: ForecastResult | InventoryResult;
  created_at: string;
};

async function getWorkspaceContext() {
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError) throw userError;
  if (!user) throw new Error("Your session has expired. Please sign in again.");

  const { data: workspace, error: workspaceError } = await supabase
    .from("workspaces")
    .select("id")
    .eq("owner_id", user.id)
    .single();

  if (workspaceError) throw workspaceError;
  return { user, workspace };
}

export async function saveForecastAnalysis(
  result: ForecastResult,
  filename: string,
): Promise<string> {
  const { user, workspace } = await getWorkspaceContext();
  const { data, error } = await supabase
    .from("analysis_runs")
    .insert({
      workspace_id: workspace.id,
      owner_id: user.id,
      analysis_type: "forecast",
      title: `Demand forecast · ${result.metadata.horizon_days} days`,
      input_filename: filename,
      horizon_days: result.metadata.horizon_days,
      summary: {
        model: result.model,
        series_count: result.metadata.series_count,
        forecast_rows: result.metadata.forecast_rows,
        history_end: result.metadata.history_end,
        forecast_start: result.metadata.forecast_start,
        forecast_end: result.metadata.forecast_end,
        rows_received: result.quality_report.rows_received,
        rows_valid: result.quality_report.rows_valid,
      },
      result,
    })
    .select("id")
    .single();

  if (error) throw error;
  return data.id;
}

export async function saveInventoryAnalysis(
  result: InventoryResult,
  salesFilename: string,
  inventoryFilename: string,
): Promise<string> {
  const { user, workspace } = await getWorkspaceContext();
  const { data, error } = await supabase
    .from("analysis_runs")
    .insert({
      workspace_id: workspace.id,
      owner_id: user.id,
      analysis_type: "inventory",
      title: `Inventory plan · ${result.metadata.forecast_horizon_days} days`,
      input_filename: `${salesFilename} + ${inventoryFilename}`,
      horizon_days: result.metadata.forecast_horizon_days,
      summary: {
        complete_recommendations: result.metadata.complete_recommendations,
        reorder_required: result.recommendations.filter((row) => row.reorder_required).length,
        forecast_rows: result.metadata.forecast_rows,
        demand_basis: result.demand_basis,
      },
      result,
    })
    .select("id")
    .single();

  if (error) throw error;
  return data.id;
}

export async function getSavedAnalyses(): Promise<SavedAnalysis[]> {
  const { data, error } = await supabase
    .from("analysis_runs")
    .select("id, workspace_id, owner_id, analysis_type, title, input_filename, horizon_days, summary, result, created_at")
    .order("created_at", { ascending: false });

  if (error) throw error;
  return (data ?? []) as SavedAnalysis[];
}

export async function deleteSavedAnalysis(id: string): Promise<void> {
  const { error } = await supabase.from("analysis_runs").delete().eq("id", id);
  if (error) throw error;
}
