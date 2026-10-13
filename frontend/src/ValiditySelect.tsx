export function ValiditySelect({ value, onChange, allowUnlimited = true, label = "有效期" }: {
  value: number; onChange: (value: number) => void; allowUnlimited?: boolean; label?: string;
}) {
  return <label>{label}
    <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
      {[7, 14, 30].map((days) => <option key={days} value={days}>{days} 天</option>)}
      {allowUnlimited && <option value={0}>长期有效</option>}
    </select>
  </label>;
}
