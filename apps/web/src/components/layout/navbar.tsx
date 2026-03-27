import Link from "next/link";
import { Button } from "@/components/ui/button";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-black/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          Analyst Pro
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          <Link href="/pricing" className="text-sm text-white/70 hover:text-white">
            Pricing
          </Link>
          <Link href="/login" className="text-sm text-white/70 hover:text-white">
            Login
          </Link>
        </nav>

        <Button asChild>
          <Link href="/signup">Start free</Link>
        </Button>
      </div>
    </header>
  );
}