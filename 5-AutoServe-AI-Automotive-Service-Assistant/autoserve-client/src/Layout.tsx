import { NavLink, Outlet, useNavigate } from "react-router-dom";

import type { Me } from "./api/schemas";
import { useAuth } from "./auth/AuthContext";

const NAV: { to: string; label: string; roles: Me["role"][] }[] = [
  { to: "/chat", label: "Chat", roles: ["vehicle_owner"] },
  { to: "/vehicles", label: "My vehicles", roles: ["vehicle_owner"] },
  { to: "/advisor", label: "Advisor", roles: ["service_advisor"] },
  { to: "/tech", label: "Tech", roles: ["technician"] },
  { to: "/warranty", label: "Warranty", roles: ["warranty_admin", "service_advisor"] },
  { to: "/admin", label: "Admin", roles: ["admin"] },
];

export function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const links = me ? NAV.filter((n) => n.roles.includes(me.role)) : [];
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <nav aria-label="Main" className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-2">
          <span className="mr-4 font-semibold">AutoServe AI</span>
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex min-h-tap min-w-tap items-center justify-center rounded px-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                  isActive ? "bg-slate-200 dark:bg-slate-800" : "hover:bg-slate-100 dark:hover:bg-slate-800"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
          <span className="ml-auto rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900">
            SYNTHETIC DATA — DEMO
          </span>
          {me && (
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="min-h-tap rounded px-3 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Sign out ({me.display_name})
            </button>
          )}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
