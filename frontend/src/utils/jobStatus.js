export function paintStatus(status) {
  if (status === 'failed') return 'success'
  return status
}

export function statusColor(status) {
  const s = paintStatus(status)
  if (s === 'success') return 'positive'
  if (s === 'failed') return 'negative'
  return 'grey'
}
