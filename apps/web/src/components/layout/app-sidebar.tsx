import Link from "next/link";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects/1", label: "Projects" },
  { href: "/reports/1", label: "Reports" },
  { href: "/billing", label: "Billing" },
  { href: "/settings", label: "Settings" },
];

export function AppSidebar() {
  return (
    <aside className="hidden w-64 border-r border-white/10 bg-black/20 lg:block">
      <div className="p-6">
        <Link href="/dashboard" className="text-lg font-semibold text-white">
          Analyst Pro
        </Link>
      </div>

      <nav className="space-y-1 px-3">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="block rounded-xl px-3 py-2 text-sm text-white/70 transition hover:bg-white/5 hover:text-white"
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}