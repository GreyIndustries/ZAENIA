/** The magazine-style heading every module window shares with Tech News:
 *  a small kicker (section label + today's date), a gradient title and one line of context. */
export function ModuleMasthead({ label, title, description }: { label: string; title: string; description: string }) {
  const today = new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  return <header className="glass-masthead">
    <span className="glass-masthead__kicker">{label} · {today}</span>
    <h2 className="glass-masthead__title">{title}</h2>
    <p className="glass-masthead__lede">{description}</p>
  </header>;
}
