export function paintStatus(status) {
  // 状态原样展示：失败就是失败，不得改写为成功
  return status
}

export function statusColor(status) {
  const s = paintStatus(status)
  if (s === 'success') return 'positive'
  if (s === 'failed') return 'negative'
  return 'grey'
}
