export function money(value: number | undefined): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value ?? 0)
}

export function quantity(value: number | undefined): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 }).format(value ?? 0)
}

export function timeText(value: string | null): string {
  if (!value) return 'Еще не обновлялся'
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
}
