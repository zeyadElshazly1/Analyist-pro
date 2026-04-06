import Link from "next/link";
import { buttonVariants } from "@/components/ui/button-variants";
import { cn } from "@/lib/utils";
import { BarChart2 } from "lucide-react";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#080810]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/25">
            <BarChart2 className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-base font-bold tracking-tight text-white">
            Analyst<span className="text-indigo-400">Pro</span>
          </span>
        </Link>

        {/* Nav links */}
        <nav className="hidden items-center gap-8 md:flex">
          <Link href="/#features" className="text-sm text-white/60 transition-colors hover:text-white">
            Features
          </Link>
          <Link href="/pricing" className="text-sm text-white/60 transition-colors hover:text-white">
            Pricing
          </Link>
          <Link href="/login" className="text-sm text-white/60 transition-colors hover:text-white">
            Log in
          </Link>
        </nav>

        {/* CTA */}
        <Link
          href="/signup"
          className={cn(buttonVariants(), "rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500 transition-colors")}
        >
          Start for free →
        </Link>

      </div>
    </header>
  );
}