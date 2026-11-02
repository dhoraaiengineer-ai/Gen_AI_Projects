import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { pageSchema, RecallNoticeSchema, ROSummarySchema, VehicleSummarySchema, type VehicleSummary } from "../api/schemas";
import { CitationChip } from "../components/Safety";

function Recalls({ vehicle }: { vehicle: VehicleSummary }) {
  const recalls = useQuery({
    queryKey: ["recalls", vehicle.id],
    queryFn: () => api(`/api/v1/vehicles/${vehicle.id}/recalls`, pageSchema(RecallNoticeSchema)),
  });
  if (recalls.isLoading) return <p className="text-sm text-slate-500">Checking recalls…</p>;
  if (!recalls.data?.items.length) return <p className="text-sm text-green-800 dark:text-green-300">No open recalls.</p>;
  return (
    <ul className="mt-2 space-y-2">
      {recalls.data.items.map((r) => (
        <li key={r.campaign_code} role="alert" className="rounded border-l-4 border-amber-600 bg-amber-50 p-2 text-sm text-amber-900">
          <p className="font-semibold">
            Open recall {r.campaign_code}: {r.title}
          </p>
          {r.notice && (
            <p className="mt-1">
              “{r.notice.quote}” <CitationChip citation={r.notice} />
            </p>
          )}
          <p className="mt-1">The recall repair is free. Use the chat to book it.</p>
        </li>
      ))}
    </ul>
  );
}

export function MyVehicles() {
  const vehicles = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api("/api/v1/vehicles", pageSchema(VehicleSummarySchema)),
  });
  const ros = useQuery({
    queryKey: ["repair-orders"],
    queryFn: () => api("/api/v1/repair-orders", pageSchema(ROSummarySchema)),
  });

  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-4xl p-6">
      <h1 id="page-title" className="text-2xl font-semibold">
        My vehicles
      </h1>
      {vehicles.isError && <p role="alert">Could not load your vehicles.</p>}
      <ul className="mt-4 grid gap-4 md:grid-cols-2">
        {vehicles.data?.items.map((v) => (
          <li key={v.id} className="rounded-lg bg-white p-4 shadow dark:bg-slate-800">
            <h2 className="text-lg font-semibold">
              Veloxa {v.model} {v.model_year}
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              VIN {v.vin_masked}
              {v.last_odometer_km != null && ` · last recorded ${v.last_odometer_km.toLocaleString()} km`}
            </p>
            <Recalls vehicle={v} />
            <h3 className="mt-3 text-sm font-semibold">Repair orders</h3>
            <ul className="text-sm">
              {ros.data?.items
                .filter((r) => r.vehicle.id === v.id)
                .map((r) => (
                  <li key={r.id}>
                    <Link className="underline" to={`/ro/${r.id}`}>
                      {r.ro_ref}
                    </Link>{" "}
                    — {r.status.replace(/_/g, " ").toLowerCase()}
                  </li>
                ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
