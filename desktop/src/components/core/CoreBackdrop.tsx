import hangar from "../../assets/core/warehouse-clean.webp";

/**
 * Hangar backdrop: the project's own warehouse render, with soft overlays so
 * the header, panels and core stay readable. Static, so it costs nothing per
 * frame.
 */
export function CoreBackdrop() {
  return <div className="core-backdrop" aria-hidden="true">
    <div className="core-backdrop__image" style={{ backgroundImage: `url(${hangar})` }}/>
    <div className="core-backdrop__shade"/>
  </div>;
}
