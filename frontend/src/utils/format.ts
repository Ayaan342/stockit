export const money = (value: string | number | null | undefined, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value ?? 0))
export const number = (value: string | number | null | undefined) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(Number(value ?? 0))
export const dateTime = (value: string) => new Date(value).toLocaleString()
export const pnlClass = (value: string | number | null | undefined) => Number(value ?? 0) >= 0 ? 'positive' : 'negative'
