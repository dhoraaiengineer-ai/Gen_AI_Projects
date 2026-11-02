/** Route table (CLAUDE.md §9). Role guards are added with auth in P1-3. */
export const ROUTES = [
  { path: "/login", title: "Sign in", task: "P1-10" },
  { path: "/chat", title: "Owner chat", task: "P1-10" },
  { path: "/vehicles", title: "My vehicles", task: "P1-10" },
  { path: "/ro/:id", title: "Repair order", task: "P1-10" },
  { path: "/advisor", title: "Advisor board", task: "P2-1" },
  { path: "/tech", title: "Technician copilot", task: "P3-1" },
  { path: "/warranty", title: "Warranty queue", task: "P3-10" },
  { path: "/warranty/:id", title: "Warranty workspace", task: "P3-10" },
  { path: "/admin", title: "Admin", task: "P1-3" },
] as const;
