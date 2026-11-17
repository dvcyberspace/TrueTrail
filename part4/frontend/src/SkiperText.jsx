import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";

// Scroll-driven text: letters fly in and meet in the center.
// Based on Skiper UI "ScrollAnimation_002" (Skiper 31), free version. Keep the credit line below.
const COLORS = ["#22d3ee", "#f472b6", "#a78bfa"];

const Character = ({ char, index, centerIndex, scrollYProgress }) => {
  const d = index - centerIndex;
  const x = useTransform(scrollYProgress, [0, 0.5], [d * 40, 0]);
  const rotateX = useTransform(scrollYProgress, [0, 0.5], [d * 40, 0]);
  const opacity = useTransform(scrollYProgress, [0, 0.2, 1], [0, 1, 1]);
  return (
    <motion.span style={{ display: "inline-block", x, rotateX, opacity, color: "#fff", textShadow: `0 0 14px ${COLORS[index % 3]}55` }}>
      {char === " " ? "\u00A0" : char}
    </motion.span>
  );
};

export default function SkiperText({ text = "DECODE THE EVIDENCE" }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref });
  const chars = text.split("");
  const center = Math.floor(chars.length / 2);
  return (
    <section ref={ref} className="skiper">
      <div className="skiper-text">
        {chars.map((c, i) => (
          <Character key={i} char={c} index={i} centerIndex={center} scrollYProgress={scrollYProgress} />
        ))}
      </div>
      <p className="skiper-credit">Scroll effect by Skiper UI</p>
    </section>
  );
}
