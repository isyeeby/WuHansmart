import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 flex justify-center items-center h-full min-h-[400px]">
            <Result
                status="warning"
                title="Something went wrong"
                subTitle={this.state.error?.message || "Sorry, an unexpected error occurred."}
                extra={<Button type="primary" onClick={() => window.location.reload()}>Reload Page</Button>}
            />
        </div>
      );
    }

    return this.props.children;
  }
}
