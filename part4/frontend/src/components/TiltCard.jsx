import { useRef } from "react";

// 3D tilt on hover: the card leans toward the pointer and a soft glare follows it.
// (Pure React + CSS, no Tailwind/DaisyUI needed. Styles live in effects.css.)
export default function TiltCard({ children, className = "", max = 12 }) {
  const box = useRef(null);

  const onMove = (e) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = box.current;
    const r = el.getBoundingClientRect(); // the wrapper never tilts, so this stays stable
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.setProperty("--rx", (0.5 - py) * 2 * max + "deg");
    el.style.setProperty("--ry", (px - 0.5) * 2 * max + "deg");
    el.style.setProperty("--mx", px * 100 + "%");
    el.style.setProperty("--my", py * 100 + "%");
  };
  const onLeave = () => {
    const s = box.current.style;
    ["--rx", "--ry", "--mx", "--my"].forEach((p) => s.removeProperty(p));
  };

  return (
    <div
      className="tilt"
      ref={box}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
    >
      <div className={"tilt-card " + className}>{children}</div>
    </div>
  );
}
