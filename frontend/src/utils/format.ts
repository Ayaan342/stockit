export const money = (value: string | number | null | undefined, currency = 'USD') => value === null || value === undefined ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value))
export const number = (value: string | number | null | undefined) => value === null || value === undefined ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(Number(value))
export const dateTime = (value: string) => new Date(value).toLocaleString()
export const pnlClass = (value: string | number | null | undefined) => value === null || value === undefined ? '' : Number(value) >= 0 ? 'positive' : 'negative'
