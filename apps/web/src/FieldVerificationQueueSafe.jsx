import React, { Component, Suspense, lazy } from 'react';

const QueueManager = lazy(() => import('./FieldVerificationQueueManager'));

class QueueErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error) {
    console.error('Offline queue panel error:', error);
  }
  render() {
    if (this.state.failed) {
      return (
        <section className="field-card">
          <h3>Offline Evidence Queue</h3>
          <p className="gis-error" role="alert">Queue panel unavailable. Existing drafts remain stored locally.</p>
          <button type="button" className="field-secondary" onClick={() => this.setState({ failed: false })}>Retry Queue Panel</button>
        </section>
      );
    }
    return this.props.children;
  }
}

export default function FieldVerificationQueueSafe({ refreshKey, userId }) {
  return (
    <QueueErrorBoundary>
      <Suspense fallback={<p>Loading offline queue...</p>}>
        <QueueManager key={`${userId}-${refreshKey}`} userId={userId} />
      </Suspense>
    </QueueErrorBoundary>
  );
}
