import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router-dom";

import { VehicleContextSchema } from "../api/advisor";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EstimatePanel } from "../components/EstimatePanel";
import { VehicleContextCard } from "../components/VehicleContextCard";
import { pageSchema, RODetailSchema, ROSummarySchema } from "../api/schemas";

const label = (s: string) => s.replace(/_/g, " ").toLowerCase();
const ESTIMATE_STATUSES = ["DIAGNOSING", "INFO_PENDING", "ESTIMATE_READY", "AWAITING_OWNER_APPROVAL", "APPROVED", "DECLINED", "IN_REPAIR"];

/** /ro/ref/:ref — resolve a reference from chat to its id (scoped by the API). */
export function RORefRedirect() {
  const { ref } = useParams();
  const ros = useQuery({
    queryKey: ["repair-orders"],
    queryFn: () => api("/api/v1/repair-orders?limit=100", pageSchema(ROSummarySchema)),
  });
  const match = ros.data?.items.find((r) => r.ro_ref === ref);
  if (match) return <Navigate to={`/ro/${match.id}`} replace />;
  if (ros.isLoading) return <p className="p-6">Loading…</p>;
  return <p className="p-6">Repair order not found.</p>;
}

function StaffVehicleContext({ vehicleId, roId }: { vehicleId: string; roId: string }) {
  const ctx = useQuery({
    queryKey: ["vehicle-context", vehicleId, roId],
    queryFn: () => api(`/api/v1/vehicles/${vehicleId}/context?ro_id=${roId}`, VehicleContextSchema),
  });
  if (ctx.isLoading) return <p className="mt-4 text-sm">Loading vehicle context…</p>;
  return ctx.data ? <VehicleContextCard ctx={ctx.data} /> : null;
}

export function RODetail() {
  const { id } = useParams();
  const { me } = useAuth();
  const ro = useQuery({
    queryKey: ["repair-order", id],
    queryFn: () => api(`/api/v1/repair-orders/${id}`, RODetailSchema),
    enabled: Boolean(id),
  });
  if (ro.isLoading) return <p className="p-6">Loading…</p>;
  if (ro.isError || !ro.data) return <p className="p-6">Repair order not found.</p>;
  const d = ro.data;
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl p-6">
      <h1 id="page-title" className="text-2xl font-semibold">
        Repair order {d.ro_ref}
      </h1>
      <p className="mt-1 text-slate-700 dark:text-slate-300">
        Veloxa {d.vehicle.model} {d.vehicle.model_year} ({d.vehicle.vin_masked}) · {d.dealer.name}
      </p>
      <p className="mt-2">
        Current status: <strong>{label(d.status)}</strong>
      </p>
      <p className="text-sm text-slate-600 dark:text-slate-400">
        {d.promised_ready_at
          ? `Expected ready: ${new Date(d.promised_ready_at).toLocaleString()}`
          : "No completion time has been recorded yet."}
      </p>
      {d.complaints.map((c, i) => (
        <blockquote key={i} className="mt-3 border-l-4 border-slate-300 pl-3 italic">
          “{c.text}”
        </blockquote>
      ))}
      {me && me.role !== "vehicle_owner" && <StaffVehicleContext vehicleId={d.vehicle.id} roId={d.id} />}
      {me && ESTIMATE_STATUSES.includes(d.status) && <EstimatePanel roId={d.id} roStatus={d.status} role={me.role} />}
      <h2 className="mt-6 text-lg font-semibold">Timeline</h2>
      <ol className="mt-2 border-l-2 border-slate-300 pl-4">
        {d.timeline.map((e, i) => (
          <li key={i} className="mb-3">
            <p className="font-medium">{label(e.to_status)}</p>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {new Date(e.at).toLocaleString()} · by {e.actor_role.replace(/_/g, " ")}
              {e.reason ? ` · ${e.reason}` : ""}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
