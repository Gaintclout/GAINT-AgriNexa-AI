export function validateReview(decision, note) {
  if (!['approved', 'rejected', 'correction_requested'].includes(decision)) return 'Select a valid decision.';
  if (decision !== 'approved' && !note.trim()) return 'A review note is required for rejection or correction.';
  if (note.length > 2000) return 'Review note must be at most 2000 characters.';
  return '';
}

export function decisionLabel(value) {
  return { approved: 'Approve', rejected: 'Reject', correction_requested: 'Request Correction' }[value] || value;
}
