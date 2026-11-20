export function validateOwnerSelection(farmerId, farmers) {
  if (!farmerId) return '';
  return farmers.some(farmer => farmer.id === farmerId) ? '' : 'Select an active Farmer account.';
}

export function ownershipLabel(farmerId, farmers) {
  if (!farmerId) return 'Unassigned';
  return farmers.find(farmer => farmer.id === farmerId)?.email || farmerId;
}
