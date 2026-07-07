import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Portfolio Overview", icon: "▦", end: true },
  { to: "/simulate", label: "What-If Simulator", icon: "⚙" },
  { to: "/compare", label: "Compare MSMEs", icon: "⤡" },
  { to: "/analytics", label: "Analytics", icon: "▥" },
];

export default function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark">IDBI</div>
          <div className="sidebar-brand-text">
            <div className="title">MSME Health Intel</div>
            <div className="subtitle">Financial Health Scoring</div>
          </div>
        </div>
        <nav className="flex flex-col gap-8">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          IDBI Innovate 2026 &middot; PS3 Prototype
          <br />
          Synthetic data for demonstration only
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
