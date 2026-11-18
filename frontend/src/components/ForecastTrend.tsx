import type { ForecastRow } from "../lib/api";

type ForecastTrendProps = {
  rows: ForecastRow[];
};

export default function ForecastTrend({ rows }: ForecastTrendProps) {
  const totals = new Map<string, number>();

  for (const row of rows) {
    const current = totals.get(row.date) ?? 0;
    totals.set(row.date, current + row.forecast_sales);
  }

  const days = [...totals.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, units]) => ({ date, units }));
  const peak = Math.max(...days.map((day) => day.units), 0);
  const totalUnits = days.reduce((sum, day) => sum + day.units, 0);
  const average = days.length ? totalUnits / days.length : 0;

  if (!days.length) return null;

  return (
    <section className="forecast-trend" aria-labelledby="forecast-trend-title">
      <div className="forecast-trend-heading">
        <div>
          <span className="forecast-eyebrow">DEMAND OUTLOOK</span>
          <h3 id="forecast-trend-title">Expected demand by day</h3>
          <p>Combined forecast across all uploaded store-product series.</p>
        </div>
        <div className="forecast-trend-total">
          <strong>{totalUnits.toLocaleString(undefined, { maximumFractionDigits: 1 })}</strong>
          <span>forecast units</span>
        </div>
      </div>
      <div
        className="forecast-trend-chart"
        role="img"
        aria-label={days.map((day) => `${day.date}: ${day.units.toFixed(1)} units`).join("; ")}
      >
        {days.map((day) => {
          const height = peak > 0 ? Math.max((day.units / peak) * 100, 3) : 3;
          return (
            <div className="forecast-trend-column" key={day.date}>
              <span className="forecast-trend-value">{day.units.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <div className="forecast-trend-track">
                <span className="forecast-trend-bar" style={{ height: `${height}%` }} />
              </div>
              <span className="forecast-trend-date">{day.date.slice(5)}</span>
            </div>
          );
        })}
      </div>
      <div className="forecast-trend-footer">
        <span>{days[0].date} — {days[days.length - 1].date}</span>
        <span>Average {average.toLocaleString(undefined, { maximumFractionDigits: 1 })} units / day</span>
      </div>
    </section>
  );
}
