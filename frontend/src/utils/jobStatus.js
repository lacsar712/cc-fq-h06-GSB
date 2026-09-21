export function paintStatus(status) {
  return status
}

export function statusColor(status) {
  if (status === 'success') return 'positive'
  if (status === 'failed') return 'negative'
  return 'grey'
}
