import { supabase } from "./supabase";
import type { SalesValidationResult } from "./api";

export type SalesImport = {
  id: string;
  filename: string;
  status: "processing" | "completed" | "failed";
  rows_received: number;
  rows_imported: number;
  rows_excluded: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
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

export async function getSalesImports(): Promise<SalesImport[]> {
  const { data, error } = await supabase
    .from("sales_imports")
    .select("id, filename, status, rows_received, rows_imported, rows_excluded, error_message, created_at, completed_at")
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  return (data ?? []) as SalesImport[];
}

export async function getProductCount(): Promise<number> {
  const { count, error } = await supabase
    .from("products")
    .select("id", { count: "exact", head: true });
  if (error) throw error;
  return count ?? 0;
}

export async function importSalesCsv(
  file: File,
  validation: SalesValidationResult,
): Promise<void> {
  if (!validation.can_import) {
    throw new Error("Resolve the blocking validation issues before importing this file.");
  }
  const { validated_rows: rows } = await import("./api").then(async ({ validateSalesCsv }) => {
    const fullValidation = await validateSalesCsv(file, true);
    if (!fullValidation.can_import || !fullValidation.validated_rows?.length) {
      throw new Error("The file could not be revalidated for import. Please validate it again.");
    }
    return fullValidation;
  });
  if (!rows?.length) throw new Error("No valid sales rows were available to import.");

  const { user, workspace } = await getWorkspaceContext();
  const { data: importRecord, error: importError } = await supabase
    .from("sales_imports")
    .insert({
      workspace_id: workspace.id,
      owner_id: user.id,
      filename: file.name,
      status: "processing",
      rows_received: validation.quality_report.rows_received,
      rows_excluded: validation.excluded_rows,
      validation_summary: validation.quality_report,
    })
    .select("id")
    .single();
  if (importError) throw importError;

  const storagePath = `${user.id}/${workspace.id}/${importRecord.id}/${file.name.replace(/[^a-zA-Z0-9._-]/g, "_")}`;
  try {
    const { error: storageError } = await supabase.storage
      .from("sales-imports")
      .upload(storagePath, file, { contentType: "text/csv", upsert: false });
    if (storageError) throw storageError;

    const productRows = Array.from(
      new Map(rows.map((row) => {
        const itemCode = String(row.item).trim();
        return [itemCode, {
          workspace_id: workspace.id,
          owner_id: user.id,
          item_code: itemCode,
          product_name: `Item ${itemCode}`,
        }];
      })).values(),
    );
    const { error: productError } = await supabase
      .from("products")
      .upsert(productRows, { onConflict: "workspace_id,item_code", ignoreDuplicates: true });
    if (productError) throw productError;

    const salesRows = rows.map((row) => ({
      workspace_id: workspace.id,
      owner_id: user.id,
      import_id: importRecord.id,
      sales_date: row.date,
      store_code: String(row.store),
      item_code: String(row.item),
      units_sold: Number(row.sales),
    }));

    for (let offset = 0; offset < salesRows.length; offset += 500) {
      const { error: salesError } = await supabase
        .from("sales_records")
        .insert(salesRows.slice(offset, offset + 500));
      if (salesError) throw salesError;
    }

    const { error: completeError } = await supabase
      .from("sales_imports")
      .update({
        storage_path: storagePath,
        status: "completed",
        rows_imported: salesRows.length,
        completed_at: new Date().toISOString(),
      })
      .eq("id", importRecord.id);
    if (completeError) throw completeError;
  } catch (error) {
    await supabase.storage.from("sales-imports").remove([storagePath]);
    await supabase.from("sales_imports").delete().eq("id", importRecord.id);
    throw error;
  }
}
