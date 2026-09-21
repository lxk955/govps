import React from "react";

interface OsLogoProps {
  os?: string;
  className?: string;
}

export function OsLogo({ os = "debian", className = "w-4 h-4" }: OsLogoProps) {
  const norm = os.toLowerCase();

  if (norm.includes("ubuntu")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Ubuntu">
        <circle cx="12" cy="12" r="10" fill="#E95420" />
        <circle cx="12" cy="12" r="6" stroke="#ffffff" strokeWidth="1.8" />
        <circle cx="12" cy="4.5" r="1.5" fill="#ffffff" />
        <circle cx="5.5" cy="16" r="1.5" fill="#ffffff" />
        <circle cx="18.5" cy="16" r="1.5" fill="#ffffff" />
      </svg>
    );
  }

  if (norm.includes("debian")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Debian">
        <path
          d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.2 16.5c-3.2.3-5.7-1.8-5.9-4.5-.2-2.5 1.5-4.6 3.8-5.1 1.9-.4 3.7.5 4.3 2.1.5 1.3.1 2.8-1 3.5-.8.5-1.9.3-2.3-.5-.4-.7-.2-1.5.4-1.9.4-.3.9-.2 1.1.2"
          stroke="#D70A53"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    );
  }

  if (norm.includes("centos")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="CentOS">
        <path d="M12 2L12 12L2 12" fill="#E88224" />
        <path d="M12 2L22 12L12 12" fill="#262577" />
        <path d="M12 22L12 12L2 12" fill="#A1C73A" />
        <path d="M12 22L22 12L12 12" fill="#932279" />
      </svg>
    );
  }

  if (norm.includes("alpine")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Alpine Linux">
        <path d="M12 3L2 20h20L12 3zm0 4.5l6.5 10.5h-13L12 7.5z" fill="#0D597F" />
        <path d="M10 14l2-3 2 3H10z" fill="#ffffff" />
      </svg>
    );
  }

  if (norm.includes("arch")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Arch Linux">
        <path
          d="M12 2L3 21l6-2 3-5 3 5 6 2L12 2z"
          fill="#1793D1"
          stroke="#1793D1"
          strokeWidth="1"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  if (norm.includes("windows")) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Windows">
        <path d="M3 5.5L10.5 4.5V11H3V5.5zm8.5-1.2L21 3V11H11.5V4.3zM3 13h7.5v6.5L3 18.5V13zm8.5 0H21v8l-9.5-1.3V13z" fill="#00ADEF" />
      </svg>
    );
  }

  // 默认通用 Linux 企鹅 / 终端图标
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-label="Linux">
      <path
        d="M12 3c-2.5 0-4 2-4 4.5 0 1.2.3 2.5.8 3.5C7.3 12 6 14 6 16.5 6 19.5 8.7 21 12 21s6-1.5 6-4.5c0-2.5-1.3-4.5-2.8-5.5.5-1 .8-2.3.8-3.5C16 5 14.5 3 12 3z"
        fill="#333333"
      />
      <circle cx="10.5" cy="7" r="1" fill="#ffffff" />
      <circle cx="13.5" cy="7" r="1" fill="#ffffff" />
      <path d="M11 9h2l-1 2-1-2z" fill="#F5A623" />
      <ellipse cx="8" cy="18" rx="2" ry="1" fill="#F5A623" />
      <ellipse cx="16" cy="18" rx="2" ry="1" fill="#F5A623" />
    </svg>
  );
}
