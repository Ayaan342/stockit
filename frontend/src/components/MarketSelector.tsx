export function MarketSelector({
  markets,
  selected,
  onSelect,
}: {
  markets: { currency: string; market: string }[]
  selected: string
  onSelect: (currency: string) => void
}) {
  if (markets.length < 2) return null
  return <div className="market-selector" role="tablist" aria-label="Portfolio market">
    {markets.map(({ currency, market }) => <button key={currency} role="tab" aria-selected={selected === currency} className={selected === currency ? 'active' : ''} onClick={() => onSelect(currency)}>{market === 'INDIA' ? 'India' : 'US'} <span>· {currency}</span></button>)}
  </div>
}
