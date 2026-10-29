import { ACCENTS, CORNERS, DEFAULT_APPEARANCE, DENSITIES, FONTS, LOOKS, TABS } from "../../core/appearance";
import type { AccentChoice, Appearance, LookChoice, TabId, TabStyle } from "../../core/appearance";
import "./AppearanceSettings.css";

/** Font, text size, accent colour, glow, window styles and per-tab colours; changes apply instantly. */
export function AppearanceSettings({ value, onChange }: { value: Appearance; onChange: (next: Appearance) => void }) {
  const accentName = ACCENTS.find(accent => accent.id === value.accent)?.label ?? "";
  const customised = Object.keys(value.tabs).length;
  const setTab = (id: TabId, change: Partial<TabStyle>) => {
    const style: TabStyle = { ...value.tabs[id], ...change };
    if (!style.look) delete style.look;
    if (!style.color) delete style.color;
    const tabs = { ...value.tabs };
    if (style.look || style.color) tabs[id] = style; else delete tabs[id];
    onChange({ ...value, tabs });
  };
  return <div className="detail-panel__block appearance-settings" aria-label="Appearance">
    <div className="section-heading"><span className="subheading">APPEARANCE</span><span>THIS DEVICE</span></div>
    <h2>Fonts &amp; colours</h2>
    <p>Re-tints the whole interface, core included. You can also say “make it blue”, “make the tasks tab pink”, “use the mono font”, “compact layout”, “round corners” or “reduce motion”.</p>
    <div className="appearance-settings__label">WINDOW STYLE · ALL TABS</div>
    <div className="appearance-settings__looks" role="radiogroup" aria-label="Window style">
      {LOOKS.map(look => <button key={look.id} type="button" role="radio" aria-checked={value.look === look.id}
        className={`appearance-settings__look appearance-settings__look--${look.id}${value.look === look.id ? " appearance-settings__look--on" : ""}`}
        onClick={() => onChange({ ...value, look: look.id })}><strong>{look.label}</strong><small>{look.note}</small></button>)}
    </div>
    <div className="appearance-settings__label">ACCENT COLOUR <strong>{accentName}</strong></div>
    <div className="appearance-settings__swatches" role="radiogroup" aria-label="Accent colour">
      {ACCENTS.map(accent => <button key={accent.id} type="button" role="radio" aria-checked={value.accent === accent.id}
        className={`appearance-settings__swatch${value.accent === accent.id ? " appearance-settings__swatch--on" : ""}`}
        onClick={() => onChange({ ...value, accent: accent.id })} title={accent.label} aria-label={accent.label}>
        <i style={{ background: accent.swatch, boxShadow: `0 0 10px ${accent.swatch}` }}/><span>{accent.label}</span>
      </button>)}
    </div>
    <div className="appearance-settings__label">CORE ICONS</div>
    <div className="choice-row" role="radiogroup" aria-label="Core icon colours">
      {([["mixed", "Amber and blue"], ["match", `All ${accentName.toLowerCase()}`]] as const).map(([id, label]) =>
        <button key={id} type="button" role="radio" aria-checked={value.orbs === id} className={value.orbs === id ? "choice choice--active" : "choice"}
          onClick={() => onChange({ ...value, orbs: id })}>{label}</button>)}
    </div>
    <div className="appearance-settings__label">EACH TAB <strong>{customised ? `${customised} customised` : "following the app"}</strong></div>
    <div className="appearance-settings__tabs">
      {TABS.map(tab => {
        const own = value.tabs[tab.id] ?? {};
        const swatch = ACCENTS.find(accent => accent.id === own.color)?.swatch;
        return <div key={tab.id} className="appearance-settings__tab">
          <span className="appearance-settings__tab-name"><i style={swatch ? { background: swatch, boxShadow: `0 0 8px ${swatch}` } : undefined}/>{tab.label}</span>
          <select aria-label={`${tab.label} style`} className="appearance-settings__select" value={own.look ?? ""}
            onChange={event => setTab(tab.id, { look: (event.target.value || undefined) as LookChoice | undefined })}>
            <option value="">Style: same as app</option>
            {LOOKS.map(look => <option key={look.id} value={look.id}>{look.label}</option>)}
          </select>
          <select aria-label={`${tab.label} colour`} className="appearance-settings__select" value={own.color ?? ""}
            onChange={event => setTab(tab.id, { color: (event.target.value || undefined) as AccentChoice | undefined })}>
            <option value="">Colour: its own</option>
            {ACCENTS.map(accent => <option key={accent.id} value={accent.id}>{accent.label}</option>)}
          </select>
        </div>;
      })}
    </div>
    {customised > 0 && <button type="button" className="choice appearance-settings__reset" onClick={() => onChange({ ...value, tabs: {} })}>Reset every tab to follow the app</button>}
    <label className="appearance-settings__label" htmlFor="appearance-font">FONT</label>
    <select id="appearance-font" className="appearance-settings__select" value={value.font} onChange={event => onChange({ ...value, font: event.target.value as Appearance["font"] })}>
      {FONTS.map(font => <option key={font.id} value={font.id} style={{ fontFamily: font.stack }}>{font.label}</option>)}
    </select>
    <label className="appearance-settings__label" htmlFor="appearance-size">TEXT SIZE <strong>{value.size}%</strong></label>
    <input id="appearance-size" type="range" min={85} max={125} step={5} value={value.size} onChange={event => onChange({ ...value, size: Number(event.target.value) })}/>
    <label className="appearance-settings__label" htmlFor="appearance-glow">COLOUR INTENSITY <strong>{value.glow}%</strong></label>
    <input id="appearance-glow" type="range" min={40} max={140} step={10} value={value.glow} onChange={event => onChange({ ...value, glow: Number(event.target.value) })}/>
    <div className="appearance-settings__label">SPACING</div>
    <div className="choice-row" role="radiogroup" aria-label="Spacing">
      {DENSITIES.map(item => <button key={item.id} type="button" role="radio" aria-checked={value.density === item.id}
        className={value.density === item.id ? "choice choice--active" : "choice"} onClick={() => onChange({ ...value, density: item.id })}>{item.label}</button>)}
    </div>
    <div className="appearance-settings__label">CORNERS</div>
    <div className="choice-row" role="radiogroup" aria-label="Corners">
      {CORNERS.map(item => <button key={item.id} type="button" role="radio" aria-checked={value.corners === item.id}
        className={value.corners === item.id ? "choice choice--active" : "choice"} onClick={() => onChange({ ...value, corners: item.id })}>{item.label}</button>)}
    </div>
    <label className="appearance-settings__label" htmlFor="appearance-opacity">PANEL SOLIDITY <strong>{value.panelOpacity}%</strong></label>
    <input id="appearance-opacity" type="range" min={50} max={100} step={5} value={value.panelOpacity} onChange={event => onChange({ ...value, panelOpacity: Number(event.target.value) })}/>
    <div className="appearance-settings__label">MOTION</div>
    <div className="choice-row" role="radiogroup" aria-label="Motion">
      {([["full", "Full"], ["reduced", "Reduced"]] as const).map(([id, label]) => <button key={id} type="button" role="radio" aria-checked={value.motion === id}
        className={value.motion === id ? "choice choice--active" : "choice"} onClick={() => onChange({ ...value, motion: id })}>{label}</button>)}
    </div>
    <small className="appearance-settings__note">Spacing, corners and panel solidity apply to the reworked tabs (Music first, the others as they're rebuilt). Reduced motion applies everywhere.</small>
    <button type="button" className="choice appearance-settings__reset" onClick={() => onChange({ ...DEFAULT_APPEARANCE })}>Reset to default</button>
  </div>;
}
