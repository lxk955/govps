import React from "react";

interface FlagIconProps {
  country?: string;
  className?: string;
}

export function FlagIcon({ country = "hk", className = "w-4 h-3 rounded-xs shadow-xs object-cover" }: FlagIconProps) {
  const code = (country || "hk").toLowerCase().trim();

  switch (code) {
    case "hk":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Hong Kong">
          <rect width="640" height="480" fill="#ec1b2e" />
          <path
            d="M320 180c-15-20-40-20-45 5 15 5 25 20 20 40-15-10-35-15-45 5 10 15 20 30 40 30-10 15-20 35 0 45 10-10 25-15 40 0-5-15 0-35 15-45-15 5-30-5-35-20 15-5 25-20 30-40-15 10-35 5-45-10 10-5 20-15 25-10z"
            fill="#ffffff"
          />
        </svg>
      );
    case "jp":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Japan">
          <rect width="640" height="480" fill="#ffffff" stroke="#e2e8f0" strokeWidth="4" />
          <circle cx="320" cy="240" r="140" fill="#bc002d" />
        </svg>
      );
    case "us":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="United States">
          <rect width="640" height="480" fill="#bd3d44" />
          <path d="M0 37h640v37H0zm0 74h640v37H0zm0 74h640v37H0zm0 74h640v37H0zm0 74h640v37H0zm0 74h640v37H0z" fill="#fff" />
          <rect width="256" height="258" fill="#192f5d" />
          <circle cx="128" cy="129" r="60" fill="#ffffff" opacity="0.8" />
        </svg>
      );
    case "sg":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Singapore">
          <rect width="640" height="240" fill="#ed2939" />
          <rect y="240" width="640" height="240" fill="#ffffff" />
          <path d="M120 120a60 60 0 1 0 0-90 70 70 0 1 1 0 90z" fill="#ffffff" />
        </svg>
      );
    case "de":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Germany">
          <rect width="640" height="160" fill="#000000" />
          <rect y="160" width="640" height="160" fill="#dd0000" />
          <rect y="320" width="640" height="160" fill="#ffce00" />
        </svg>
      );
    case "gb":
    case "uk":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="United Kingdom">
          <rect width="640" height="480" fill="#012169" />
          <path d="M0 0l640 480M640 0L0 480" stroke="#ffffff" strokeWidth="60" />
          <path d="M0 0l640 480M640 0L0 480" stroke="#c8102e" strokeWidth="30" />
          <path d="M320 0v480M0 240h640" stroke="#ffffff" strokeWidth="100" />
          <path d="M320 0v480M0 240h640" stroke="#c8102e" strokeWidth="60" />
        </svg>
      );
    case "kr":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="South Korea">
          <rect width="640" height="480" fill="#ffffff" stroke="#e2e8f0" strokeWidth="4" />
          <circle cx="320" cy="240" r="110" fill="#cd2e3a" />
          <path d="M320 240a55 55 0 0 0 0 110 110 110 0 0 1 0-220 55 55 0 0 1 0 110z" fill="#0047a0" />
        </svg>
      );
    case "ca":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Canada">
          <rect width="640" height="480" fill="#ffffff" />
          <rect width="160" height="480" fill="#d80621" />
          <rect x="480" width="160" height="480" fill="#d80621" />
          <path d="M320 140l20 50 40-10-20 40 40 20-50 20v30h-20v-30l-50-20 40-20-20-40 40 10z" fill="#d80621" />
        </svg>
      );
    case "cn":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="China">
          <rect width="640" height="480" fill="#de2910" />
          <polygon points="100,50 110,80 140,80 115,100 125,130 100,110 75,130 85,100 60,80 90,80" fill="#ffde00" />
        </svg>
      );
    case "tw":
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Taiwan">
          <rect width="640" height="480" fill="#fe0000" />
          <rect width="320" height="240" fill="#000095" />
          <circle cx="160" cy="120" r="45" fill="#ffffff" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 640 480" className={className} aria-label="Global">
          <rect width="640" height="480" fill="#3b82f6" />
          <circle cx="320" cy="240" r="140" fill="#60a5fa" />
        </svg>
      );
  }
}
