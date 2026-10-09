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
  return (
    <div
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Ambient Floor Reflection & Glow */}
      {glow && (
        <>
          <div
            className="absolute -bottom-5 w-3/4 h-5 rounded-full bg-cyan-400/25 blur-xl pointer-events-none"
            style={{ transform: "scaleY(0.4)" }}
          />
          <div
            className="absolute inset-0 rounded-full bg-teal-500/20 blur-2xl animate-pulse pointer-events-none"
            style={{ animationDuration: "4s" }}
          />
        </>
      )}

      {/* 3D Iridescent Glowing Sphere */}
      <svg
        viewBox="0 0 100 100"
        className="w-full h-full drop-shadow-[0_12px_24px_rgba(0,240,255,0.35)]"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Base Sphere Gradient (Deep Cobalt to Vibrant Emerald & Cyan) */}
          <radialGradient
            id="orbBase"
            cx="35%"
            cy="30%"
            r="65%"
            fx="35%"
            fy="30%"
          >
            <stop offset="0%" stopColor="#c7f9ff" />
            <stop offset="15%" stopColor="#4de1ff" />
            <stop offset="40%" stopColor="#00b4d8" />
            <stop offset="70%" stopColor="#0f4c81" />
            <stop offset="100%" stopColor="#05192d" />
          </radialGradient>

          {/* Emerald / Lime Swirl Overlay */}
          <radialGradient
            id="orbSwirl"
            cx="65%"
            cy="70%"
            r="55%"
            fx="65%"
            fy="70%"
          >
            <stop offset="0%" stopColor="#00ffcc" stopOpacity="0.9" />
            <stop offset="35%" stopColor="#10b981" stopOpacity="0.7" />
            <stop offset="70%" stopColor="#064e3b" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#064e3b" stopOpacity="0" />
          </radialGradient>

          {/* Secondary Lime-Yellow Highlight Swirl */}
          <radialGradient
            id="orbLime"
            cx="30%"
            cy="45%"
            r="40%"
            fx="30%"
            fy="45%"
          >
            <stop offset="0%" stopColor="#84cc16" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#22c55e" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#047857" stopOpacity="0" />
          </radialGradient>

          {/* Top Glass Specular Arc Highlight */}
          <linearGradient id="glassSpecular" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="40%" stopColor="#ffffff" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>

          {/* Inner Shadow / Rim Gradient */}
          <radialGradient
            id="rimLight"
            cx="50%"
            cy="50%"
            r="50%"
            fx="50%"
            fy="50%"
          >
            <stop offset="78%" stopColor="#000000" stopOpacity="0" />
            <stop offset="96%" stopColor="#001a33" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#00f0ff" stopOpacity="0.8" />
          </radialGradient>

          <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer Shadow Ring */}
        <circle cx="50" cy="50" r="46" fill="#000000" opacity="0.4" />

        {/* Main Sphere Body */}
        <circle cx="50" cy="50" r="45" fill="url(#orbBase)" />

        {/* Lime & Emerald Swirls */}
        <circle cx="50" cy="50" r="45" fill="url(#orbSwirl)" />
        <circle cx="50" cy="50" r="45" fill="url(#orbLime)" />

        {/* Rim Light / Outer Glow Edge */}
        <circle cx="50" cy="50" r="45" fill="url(#rimLight)" />

        {/* Top Crescent Specular Reflection (Glass Highlight) */}
        <path
          d="M 22 28 Q 50 14 78 28 Q 50 22 22 28 Z"
          fill="url(#glassSpecular)"
          opacity="0.85"
        />

        {/* Specular White Pinpoint Dot */}
        <circle cx="36" cy="26" r="3.5" fill="#ffffff" opacity="0.9" />
        <circle cx="43" cy="22" r="1.5" fill="#ffffff" opacity="0.75" />

        {/* Bottom Reflected Cyan Bounce Light */}
        <ellipse
          cx="50"
          cy="78"
          rx="24"
          ry="7"
          fill="#38bdf8"
          opacity="0.5"
          filter="url(#softGlow)"
        />
      </svg>
    </div>
  );
};
