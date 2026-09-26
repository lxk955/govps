"use client";

import React, { useState } from "react";

interface OsLogoProps {
  os?: string;
  className?: string;
  size?: number;
}

export function OsLogo({ os = "debian", className = "w-4 h-4", size = 16 }: OsLogoProps) {
  const norm = (os || "").toLowerCase().trim();
  const [imgError, setImgError] = useState(false);

  let iconName = "os-unknown.svg";
  if (norm.includes("debian") || norm.includes("deb")) iconName = "os-debian.svg";
  else if (norm.includes("ubuntu")) iconName = "os-ubuntu.svg";
  else if (norm.includes("centos")) iconName = "os-centos.svg";
  else if (norm.includes("alma")) iconName = "os-alma.svg";
  else if (norm.includes("rocky")) iconName = "os-rocky.svg";
  else if (norm.includes("alpine")) iconName = "os-alpine.webp";
  else if (norm.includes("arch")) iconName = "os-arch.svg";
  else if (norm.includes("fedora")) iconName = "os-fedora.svg";
  else if (norm.includes("redhat") || norm.includes("rhel")) iconName = "os-redhat.svg";
  else if (norm.includes("openwrt")) iconName = "os-openwrt.svg";
  else if (norm.includes("windows") || norm.includes("win")) iconName = "os-windows.svg";
  else if (norm.includes("macos") || norm.includes("darwin")) iconName = "os-macos.svg";
  else if (norm.includes("armbian")) iconName = "os-armbian.png";
  else if (norm.includes("synology") || norm.includes("dsm")) iconName = "os-synology.ico";

  if (!imgError) {
    return (
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={`/os-icons/${iconName}`}
        alt={os}
        width={size}
        height={size}
        className={className}
        onError={() => setImgError(true)}
      />
    );
  }

  // 兜底 SVG
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-label={os}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
