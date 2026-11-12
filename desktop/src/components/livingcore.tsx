import "./../styles/LivingCore.css";

export default function LivingCore() {
  return (
    <div className="living-core-wrap">
      <div className="living-core-shell">
        <div className="core-aura aura-outer" />
        <div className="core-aura aura-mid" />
        <div className="core-aura aura-inner" />

        <div className="planet-body">
          <div className="planet-sheen" />
          <div className="planet-energy planet-energy-1" />
          <div className="planet-energy planet-energy-2" />
          <div className="planet-energy planet-energy-3" />

          <div className="nucleus-wrap">
            <div className="nucleus-glow" />
            <div className="nucleus-core" />
            <div className="nucleus-ring ring-a" />
            <div className="nucleus-ring ring-b" />
            <div className="nucleus-ring ring-c" />
          </div>
        </div>

        <div className="orbit-band orbit-band-main" />
        <div className="orbit-band orbit-band-rear" />

        <div className="atomic-arc arc-1" />
        <div className="atomic-arc arc-2" />
        <div className="atomic-arc arc-3" />
      </div>
    </div>
  );
}