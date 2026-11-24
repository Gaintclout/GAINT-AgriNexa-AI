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
        <section className="field-card field-queue-fallback">
          <h3>Offline evidence queue</h3>
          <p className="gis-error" role="alert">Queue panel unavailable. Existing drafts remain stored locally.</p>
          <button type="button" className="field-secondary" onClick={() => this.setState({ failed: false })}>Retry queue panel</button>
        </section>
      );
    }
    return this.props.children;
  }
}

export default function FieldVerificationQueueSafe({ refreshKey, userId }) {
  return (
    <QueueErrorBoundary>
      <Suspense fallback={<section className="field-card field-queue-loading" role="status"><p>Loading offline evidence queue...</p></section>}>
        <QueueManager key={`${userId}-${refreshKey}`} userId={userId} />
      </Suspense>
    </QueueErrorBoundary>
  );
}
