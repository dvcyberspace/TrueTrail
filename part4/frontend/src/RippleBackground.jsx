import { useEffect, useRef, useState } from "react";

// Grid background: click anywhere to send a soft wave across the cells,
// move the mouse to light up the cell under it. Colors stay low-opacity (see App.css).
const CELL = 56;
const PALETTE = ["#22d3ee", "#f472b6", "#a78bfa", "#fbbf24"];

export default function RippleBackground() {
  const [grid, setGrid] = useState({ r: 0, c: 0 });
  const [rip, setRip] = useState({ r: 0, c: 0, k: 0 });
  const box = useRef(null);
  const cols = useRef(0);
  const prev = useRef(null);
  const k = useRef(0);

  useEffect(() => {
    const size = () => {
      cols.current = Math.ceil(window.innerWidth / CELL) + 1;
      setGrid({ r: Math.ceil(window.innerHeight / CELL) + 1, c: cols.current });
    };
    const fire = (r, c) => {
      k.current += 1;
      box.current?.style.setProperty("--rc", PALETTE[k.current % PALETTE.length]);
      setRip({ r, c, k: k.current });
    };
    const click = (e) => fire(Math.floor(e.clientY / CELL), Math.floor(e.clientX / CELL));
    const auto = () =>
      fire(
        Math.floor(Math.random() * Math.ceil(window.innerHeight / CELL)),
        Math.floor(Math.random() * Math.ceil(window.innerWidth / CELL)),
      );
    // hover: toggle a class directly on the cell (no React re-render per mouse move)
    const move = (e) => {
      const el =
        box.current?.children[Math.floor(e.clientY / CELL) * cols.current + Math.floor(e.clientX / CELL)];
      if (el === prev.current) return;
      prev.current?.classList.remove("hover");
      el?.classList.add("hover");
      prev.current = el || null;
    };
    const leave = () => {
      prev.current?.classList.remove("hover");
      prev.current = null;
    };
    size();
    window.addEventListener("resize", size);
    window.addEventListener("pointerdown", click);
    window.addEventListener("pointermove", move);
    document.documentElement.addEventListener("mouseleave", leave);
    const t = setTimeout(auto, 800);
    const iv = setInterval(auto, 8000);
    return () => {
      window.removeEventListener("resize", size);
      window.removeEventListener("pointerdown", click);
      window.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("mouseleave", leave);
      clearTimeout(t);
      clearInterval(iv);
    };
  }, []);

  return (
    <div
      ref={box}
      className="ripple"
      aria-hidden="true"
      style={{ gridTemplateColumns: `repeat(${grid.c}, ${CELL}px)`, gridTemplateRows: `repeat(${grid.r}, ${CELL}px)` }}
    >
      {Array.from({ length: grid.r * grid.c }, (_, i) => {
        const d = Math.hypot(Math.floor(i / grid.c) - rip.r, (i % grid.c) - rip.c);
        return (
          <div
            key={i + "-" + rip.k}
            className={"cell" + (rip.k ? " go" : "")}
            style={{ "--d": d * 55 + "ms", "--t": 220 + d * 80 + "ms" }}
          />
        );
      })}
    </div>
  );
}
