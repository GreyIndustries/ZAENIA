import { useEffect, useState } from "react";
import QRCode from "qrcode";

/** The random QR code the PC shows for Phone confirms; drawn locally, dark on light so phone cameras read it easily. */
export function NearQr({ value }: { value: string }) {
  const [svg, setSvg] = useState("");
  useEffect(() => {
    let live = true;
    QRCode.toString(value, { type: "svg", errorCorrectionLevel: "M", margin: 2, color: { dark: "#0a1220", light: "#f4f7fb" } })
      .then(text => { if (live) setSvg(text); }, () => { if (live) setSvg(""); });
    return () => { live = false; };
  }, [value]);
  return <div className="near-code__qr" aria-label="QR code" role="img" dangerouslySetInnerHTML={{ __html: svg }}/>;
}
