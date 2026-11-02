import { Navigate, type RouteObject } from "react-router-dom";

import { RequireRole } from "./auth/AuthContext";
import { Admin } from "./pages/Admin";
import { AdvisorBoard } from "./pages/AdvisorBoard";
import { Layout } from "./Layout";
import { Login } from "./pages/Login";
import { MyVehicles } from "./pages/MyVehicles";
import { OwnerChat } from "./pages/OwnerChat";
import { Placeholder } from "./pages/Placeholder";
import { RODetail, RORefRedirect } from "./pages/RODetail";
import { TechCopilot } from "./pages/TechCopilot";
import { WarrantyQueue } from "./pages/WarrantyQueue";
import { WarrantyWorkspace } from "./pages/WarrantyWorkspace";

const OWNER = ["vehicle_owner"] as const;
const STAFF = ["service_advisor", "technician", "warranty_admin"] as const;
const ALL_RO_READERS = [...OWNER, ...STAFF];

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/login" replace /> },
      { path: "/login", element: <Login /> },
      { path: "/chat", element: <RequireRole roles={[...OWNER]}><OwnerChat /></RequireRole> },
      { path: "/vehicles", element: <RequireRole roles={[...OWNER]}><MyVehicles /></RequireRole> },
      { path: "/ro/ref/:ref", element: <RequireRole roles={ALL_RO_READERS}><RORefRedirect /></RequireRole> },
      { path: "/ro/:id", element: <RequireRole roles={ALL_RO_READERS}><RODetail /></RequireRole> },
      { path: "/advisor", element: <RequireRole roles={["service_advisor"]}><AdvisorBoard /></RequireRole> },
      { path: "/tech", element: <RequireRole roles={["technician"]}><TechCopilot /></RequireRole> },
      { path: "/warranty", element: <RequireRole roles={["warranty_admin", "service_advisor"]}><WarrantyQueue /></RequireRole> },
      { path: "/warranty/:id", element: <RequireRole roles={["warranty_admin", "service_advisor"]}><WarrantyWorkspace /></RequireRole> },
      { path: "/admin", element: <RequireRole roles={["admin"]}><Admin /></RequireRole> },
      { path: "*", element: <Placeholder title="Page not found" task="—" /> },
    ],
  },
];
