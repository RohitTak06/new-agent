import React from "react";
import { ErrorBanner } from "./ui";

/** Keeps a screen's rendering bug from blanking the whole app. */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <ErrorBanner message="This screen hit an unexpected error." onRetry={() => window.location.reload()} />;
  }
}
