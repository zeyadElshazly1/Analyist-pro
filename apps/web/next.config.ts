import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default withSentryConfig(nextConfig, {
  // Suppress Sentry CLI output during build
  silent: !process.env.CI,
  telemetry: false,
  // Source map upload — only runs when SENTRY_AUTH_TOKEN is set
  authToken: process.env.SENTRY_AUTH_TOKEN,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Skip source map upload if no auth token (local dev / CI without secrets)
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },
});
