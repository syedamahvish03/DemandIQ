import { supabase } from "./supabase";

const PAGE_SIZE = 1000;
const MAX_ROWS = 100000;
const MAX_CSV_BYTES = 10 * 1024 * 1024;

export type WorkspaceSalesSource = {
  file: File;
  rowCount: number;
  firstDate: string;
  lastDate: string;
};

/**
 * Build the existing FastAPI CSV input from the signed-in user's imported
 * workspace records. Supabase RLS remains the authority for row access.
 */
export async function getWorkspaceSalesFile(): Promise<WorkspaceSalesSource> {
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError) throw userError;
  if (!user) throw new Error("Your session has expired. Please sign in again.");

  const records: Array<{
    sales_date: string;
    store_code: string;
    item_code: string;
    units_sold: number | string;
  }> = [];

  for (let offset = 0; ; offset += PAGE_SIZE) {
    const { data, error } = await supabase
      .from("sales_records")
      .select("sales_date, store_code, item_code, units_sold")
      .order("sales_date", { ascending: true })
      .order("store_code", { ascending: true })
      .order("item_code", { ascending: true })
      .range(offset, offset + PAGE_SIZE - 1);

    if (error) throw error;
    const page = data ?? [];
    records.push(...page);
    if (records.length > MAX_ROWS) {
      throw new Error("Your workspace contains more than 100,000 sales rows. Narrow the dataset before generating an analysis.");
    }
    if (page.length < PAGE_SIZE) break;
  }

  if (records.length === 0) {
    throw new Error("No imported sales records were found in this workspace. Import a sales CSV first.");
  }

  const escapeCsv = (value: string | number): string =>
    `"${String(value).replace(/"/g, '""')}"`;
  const lines = [
    ["date", "store", "item", "sales"].join(","),
    ...records.map((row) => [
      row.sales_date,
      row.store_code,
      row.item_code,
      row.units_sold,
    ].map(escapeCsv).join(",")),
  ];
  const content = lines.join("\r\n");
  const file = new File([content], "demandiq_workspace_sales.csv", {
    type: "text/csv",
  });

  if (file.size > MAX_CSV_BYTES) {
    throw new Error("The imported workspace sales data exceeds the 10 MB analysis upload limit.");
  }

  return {
    file,
    rowCount: records.length,
    firstDate: records[0].sales_date,
    lastDate: records[records.length - 1].sales_date,
  };
}
