import type { ReactNode } from 'react'

export function MetricCard({ label, value, tone, detail, featured = false }: { label: string; value: ReactNode; tone?: string; detail?: ReactNode; featured?: boolean }) {
  return <article className={`metric-card ${tone ?? ''} ${featured ? 'featured' : ''}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>
}

export function Loading() { return <div className="state">Loading…</div> }
export function Empty({ children }: { children: ReactNode }) { return <div className="state empty">{children}</div> }
export function ErrorState({ message }: { message: string }) { return <div className="state error">{message}</div> }
