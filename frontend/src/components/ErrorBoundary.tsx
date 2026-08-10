import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Top-level render error boundary.
 *
 * Without one, any page that throws during render unmounts the whole React
 * tree to a blank white screen. This catches the crash, shows the message,
 * and offers a way back to the tool list.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught a render error:", error, info);
  }

  private reset = () => {
    // This boundary wraps <BrowserRouter> (see main.tsx), so router hooks are
    // unavailable here. A hash assignment wouldn't navigate — BrowserRouter
    // listens for popstate, not hashchange — so do a full navigation to the
    // tool list. The reload also remounts the tree fresh, clearing the error.
    window.location.assign("/");
  };

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary" role="alert">
          <h1>页面出错了</h1>
          <p>渲染页面时发生了未预期的错误。已回到安全状态，不会影响其他页面。</p>
          <pre>{this.state.error.message}</pre>
          <button type="button" onClick={this.reset}>
            回到工具列表
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
