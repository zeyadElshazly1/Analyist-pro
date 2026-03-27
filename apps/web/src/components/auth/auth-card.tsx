import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type AuthCardProps = {
  title: string;
  subtitle: string;
  actionText: string;
};

export function AuthCard({ title, subtitle, actionText }: AuthCardProps) {
  return (
    <Card className="w-full max-w-md rounded-3xl border-white/10 bg-white/5 shadow-2xl shadow-black/30">
      <CardContent className="p-6">
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        <p className="mt-2 text-sm text-white/60">{subtitle}</p>

        <div className="mt-6 space-y-4">
          <Input
            placeholder="Email"
            className="border-white/10 bg-black/30 text-white placeholder:text-white/30"
          />
          <Input
            type="password"
            placeholder="Password"
            className="border-white/10 bg-black/30 text-white placeholder:text-white/30"
          />
          <Button className="w-full rounded-xl">{actionText}</Button>
        </div>

        <div className="my-6 h-px bg-white/10" />

        <div className="space-y-3">
          <Button
            variant="outline"
            className="w-full rounded-xl border-white/10 bg-transparent text-white hover:bg-white/5"
          >
            Continue with Google
          </Button>
          <Button
            variant="outline"
            className="w-full rounded-xl border-white/10 bg-transparent text-white hover:bg-white/5"
          >
            Continue with GitHub
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}