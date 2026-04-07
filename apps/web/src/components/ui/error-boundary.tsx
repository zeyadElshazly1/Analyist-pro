"use client";

/**
 * React Error Boundary — catches render-time JavaScript errors in child trees.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeComponent />
 *   </ErrorBoundary>
 *
 * Custom fallback:
 *   <ErrorBoundary fallback={<p>Custom message</p>}>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */

import { Component, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Optional custom fallback UI. Receives reset() so it can offer a retry button. */
  fallback?: (reset: () => void) => ReactNode;
  /** Label for the section, shown in the default error UI */
  label?: string;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error?.message ?? "An unexpected rendering error occurred.",
    };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // In production you'd send this to Sentry / DataDog / LogRocket
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback(this.reset);
    }

    return (
      <DefaultErrorFallback
        label={this.props.label}
        message={this.state.message}
        onReset={this.reset}
      />
    );
  }
}

function DefaultErrorFallback({
  label,
  message,
  onReset,
}: {
  label?: string;
  message: string;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-red-500/20 bg-red-500/5 px-6 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10">
        <AlertTriangle className="h-6 w-6 text-red-400" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-red-300">
          {label ? `${label} failed to render` : "Something went wrong"}
        </p>
        <p className="text-xs text-white/40 max-w-xs leading-relaxed">
          {message}
        </p>
      </div>
      <button
        onClick={onReset}
        className="flex items-center gap-2 rounded-lg bg-white/[0.06] px-4 py-2 text-xs text-white/70 hover:text-white hover:bg-white/[0.1] transition-colors"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Try again
      </button>
    </div>
  );
}

/**
 * Convenience wrapper for wrapping individual tab/panel sections.
 * Provides a compact inline error state instead of a full-page crash.
 */
export function SafePanel({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <ErrorBoundary label={label}>
      {children}
    </ErrorBoundary>
  );
}
