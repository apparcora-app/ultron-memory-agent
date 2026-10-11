import React from "react";

interface OrbAvatarProps {
  size?: number;
  className?: string;
  glow?: boolean;
}

export const OrbAvatar: React.FC<OrbAvatarProps> = ({
  size = 110,
  className = "",
  glow = true,
}) => {
  // If small (e.g. sidebar), render simple compact glowing orb
  if (size < 60) {
    return (
      <div
        className={`relative flex items-center justify-center select-none ${className}`}
        style={{ width: size, height: size }}
      >
        <svg
          viewBox="0 0 100 100"
          className="w-full h-full drop-shadow-[0_4px_12px_rgba(14,165,233,0.4)]"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <radialGradient cx="34%" cy="28%" id="compactOrbCore" r="70%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="20%" stopColor="#bae6fd" />
              <stop offset="42%" stopColor="#38bdf8" />
              <stop offset="72%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#082f49" />
            </radialGradient>
            <radialGradient cx="68%" cy="72%" id="compactOrbSheen" r="55%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.85" />
              <stop offset="50%" stopColor="#0284c7" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#075985" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx="50" cy="50" fill="url(#compactOrbCore)" r="46" />
          <circle cx="50" cy="50" fill="url(#compactOrbSheen)" r="46" />
          <circle cx="36" cy="26" fill="#ffffff" opacity="0.9" r="3.5" />
          <circle cx="43" cy="22" fill="#bae6fd" opacity="0.75" r="1.5" />
        </svg>
      </div>
    );
  }

  // Hero Size Orb (Stitch Spec with Electric Thunder Rings & Lightning Arcs)
  return (
    <div
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{ width: size * 1.8, height: size * 1.8 }}
    >
      {/* Realistic ground shadow underneath */}
      {glow && (
        <div className="absolute -bottom-6 w-36 h-5 rounded-full bg-[#0284c7]/25 blur-xl pointer-events-none scale-y-50" />
      )}

      {/* Aura Pulse Rings expanding outward */}
      {glow && (
        <>
          <div
            className="absolute inset-0 rounded-full border border-[#38bdf8]/40 pointer-events-none"
            style={{ animation: "auraPulseRing 3s ease-out infinite" }}
          />
          <div
            className="absolute inset-0 rounded-full border border-[#0ea5e9]/30 pointer-events-none"
            style={{ animation: "auraPulseRing 3s ease-out infinite 1.5s" }}
          />
          <div className="absolute inset-2 rounded-full bg-gradient-to-tr from-[#0284c7]/35 via-[#38bdf8]/30 to-[#7dd3fc]/20 blur-2xl pointer-events-none" />
        </>
      )}

      {/* Outer Rotating Electric Thunder Rings & Jagged Lightning SVG */}
      <div className="absolute inset-0 w-full h-full pointer-events-none electric-ring-1">
        <svg
          className="w-full h-full lightning-arc-1 overflow-visible"
          fill="none"
          viewBox="0 0 200 200"
        >
          <circle
            cx="100"
            cy="100"
            opacity="0.35"
            r="88"
            stroke="#38bdf8"
            strokeDasharray="4 6"
            strokeWidth="0.75"
          />
          {/* Jagged Electric Arc 1 */}
          <polyline
            filter="drop-shadow(0 0 6px #0ea5e9)"
            points="100,12 110,22 96,36 122,46 114,64 130,82"
            stroke="#38bdf8"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
          />
          <circle
            cx="130"
            cy="82"
            fill="#ffffff"
            filter="drop-shadow(0 0 5px #38bdf8)"
            r="2.5"
          />
          <polyline
            filter="drop-shadow(0 0 5px #0284c7)"
            points="20,110 36,124 24,142 44,156 38,174"
            stroke="#7dd3fc"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
          <circle cx="38" cy="174" fill="#ffffff" r="2" />
        </svg>
      </div>

      {/* Inner Counter-Rotating Lightning Arc Layer */}
      <div className="absolute inset-0 w-full h-full pointer-events-none electric-ring-2">
        <svg
          className="w-full h-full lightning-arc-2 overflow-visible"
          fill="none"
          viewBox="0 0 200 200"
        >
          <circle
            cx="100"
            cy="100"
            opacity="0.4"
            r="76"
            stroke="#0ea5e9"
            strokeDasharray="2 4"
            strokeWidth="0.7"
          />
          {/* Crackling Lightning Arc 2 */}
          <polyline
            filter="drop-shadow(0 0 7px #38bdf8)"
            points="182,100 166,112 178,130 154,146 162,166"
            stroke="#e0f2fe"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
          />
          <circle
            cx="182"
            cy="100"
            fill="#ffffff"
            filter="drop-shadow(0 0 6px #38bdf8)"
            r="3"
          />
          <polyline
            points="76,18 62,34 78,50 58,68 66,88"
            stroke="#38bdf8"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      </div>

      {/* The Floating Sky-Blue Luminous Sphere */}
      <div
        className="floating-orb relative z-10 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        <svg
          className="w-full h-full orb-glow drop-shadow-[0_15px_30px_rgba(14,165,233,0.45)]"
          fill="none"
          viewBox="0 0 100 100"
        >
          <defs>
            <radialGradient cx="34%" cy="28%" id="skyBlueOrbCore" r="70%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="20%" stopColor="#bae6fd" />
              <stop offset="42%" stopColor="#38bdf8" />
              <stop offset="72%" stopColor="#0284c7" />
              <stop offset="92%" stopColor="#0369a1" />
              <stop offset="100%" stopColor="#082f49" />
            </radialGradient>
            <radialGradient cx="68%" cy="72%" id="skyBlueSheen" r="55%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.85" />
              <stop offset="50%" stopColor="#0284c7" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#075985" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="rimGlow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#0369a1" stopOpacity="0.9" />
            </linearGradient>
          </defs>
          <circle
            cx="50"
            cy="50"
            fill="url(#skyBlueOrbCore)"
            r="46"
            stroke="url(#rimGlow)"
            strokeWidth="0.8"
          />
          <circle cx="50" cy="50" fill="url(#skyBlueSheen)" r="46" />
          <ellipse
            cx="36"
            cy="26"
            fill="#ffffff"
            opacity="0.95"
            rx="8"
            ry="4.5"
            transform="rotate(-25 36 26)"
          />
          <circle cx="45" cy="21" fill="#e0f2fe" opacity="0.8" r="2.2" />
          <ellipse
            cx="62"
            cy="74"
            fill="#7dd3fc"
            opacity="0.4"
            rx="14"
            ry="4"
            transform="rotate(-15 62 74)"
          />
        </svg>
      </div>
    </div>
  );
};

