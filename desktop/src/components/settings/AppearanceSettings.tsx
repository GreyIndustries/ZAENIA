import { ACCENTS, DEFAULT_APPEARANCE, FONTS } from "../../core/appearance";
import type { Appearance } from "../../core/appearance";
import "./AppearanceSettings.css";

/** Font, text size, accent colour and glow; changes apply instantly. */
export function AppearanceSettings({ value, onChange }: { value: Appearance; onChange: (next: Appearance) => void }) {
  return <div className="detail-panel__block appearance-settings" aria-label="Appearance">
    <div className="section-heading"><span className="subheading">APPEARANCE</span><span>THIS DEVICE</span></div>
    <h2>Fonts &amp; colours</h2>
    <p>Re-tints the whole interface, core included. You can also say “make it blue” or “use the mono font”.</p>
    <div className="appearance-settings__label">ACCENT COLOUR</div>
    <div className="appearance-settings__swatches" role="radiogroup" aria-label="Accent colour">
      {ACCENTS.map(accent => <button key={accent.id} type="button" role="radio" aria-checked={value.accent === accent.id}
        className={`appearance-settings__swatch${value.accent === accent.id ? " appearance-settings__swatch--on" : ""}`}
        onClick={() => onChange({ ...value, accent: accent.id })} title={accent.label}>
        <i style={{ background: accent.swatch, boxShadow: `0 0 10px ${accent.swatch}` }}/><span>{accent.label}</span>
      </button>)}
    </div>
    <label className="appearance-settings__label" htmlFor="appearance-font">FONT</label>
    <select id="appearance-font" className="appearance-settings__select" value={value.font} onChange={event => onChange({ ...value, font: event.target.value as Appearance["font"] })}>
      {FONTS.map(font => <option key={font.id} value={font.id} style={{ fontFamily: font.stack }}>{font.label}</option>)}
    </select>
    <label className="appearance-settings__label" htmlFor="appearance-size">TEXT SIZE <strong>{value.size}%</strong></label>
    <input id="appearance-size" type="range" min={85} max={125} step={5} value={value.size} onChange={event => onChange({ ...value, size: Number(event.target.value) })}/>
    <label className="appearance-settings__label" htmlFor="appearance-glow">COLOUR INTENSITY <strong>{value.glow}%</strong></label>
    <input id="appearance-glow" type="range" min={40} max={140} step={10} value={value.glow} onChange={event => onChange({ ...value, glow: Number(event.target.value) })}/>
    <button type="button" className="choice appearance-settings__reset" onClick={() => onChange({ ...DEFAULT_APPEARANCE })}>Reset to default</button>
  </div>;
}
