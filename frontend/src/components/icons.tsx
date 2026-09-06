/** Small hand-authored inline SVG icons (no icon library dependency) -
 * consistent 20x20 outline style, `currentColor` stroke so they inherit
 * text color/size from their container. */

type IconProps = { className?: string };

const base = "h-4 w-4";

export function IconHome({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="m3 9 7-6 7 6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4.5 8v8a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 17v-4.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V17" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconCalendar({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="3" y="4" width="14" height="13" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 8h14M7 2.5v3M13 2.5v3" strokeLinecap="round" />
    </svg>
  );
}

export function IconAlertTriangle({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M10 3.2 2.5 16h15L10 3.2Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 8.3v3.4" strokeLinecap="round" />
      <circle cx="10" cy="13.6" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconLayers({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="m10 2.5 7.5 4L10 10.5 2.5 6.5 10 2.5Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m2.5 10 7.5 4 7.5-4M2.5 13.5 10 17.5l7.5-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconGitBranch({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="6" cy="4.5" r="2" />
      <circle cx="6" cy="15.5" r="2" />
      <circle cx="14" cy="9" r="2" />
      <path d="M6 6.5v7M6 8c0 3 3 3 6.3 3" strokeLinecap="round" />
    </svg>
  );
}

export function IconClipboardList({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="4" y="3.5" width="12" height="14" rx="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7.5 2.5h5a.5.5 0 0 1 .5.5v1.5a.5.5 0 0 1-.5.5h-5a.5.5 0 0 1-.5-.5V3a.5.5 0 0 1 .5-.5Z" />
      <path d="M7 9h6M7 12h6M7 15h3.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconUpload({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M10 12.5V3M6.5 6.5 10 3l3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 13v2.5a1.5 1.5 0 0 0 1.5 1.5h9a1.5 1.5 0 0 0 1.5-1.5V13" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconCheckCircle({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="10" cy="10" r="7.25" />
      <path d="M7 10.2 9.1 12.3 13.2 8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconInbox({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M3 11.5 5 4h10l2 7.5" strokeLinecap="round" strokeLinejoin="round" />
      <path
        d="M3 11.5h4.2a.5.5 0 0 1 .45.28l.7 1.44a.5.5 0 0 0 .45.28h2.4a.5.5 0 0 0 .45-.28l.7-1.44a.5.5 0 0 1 .45-.28H17V16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4.5Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconUsers({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="7.5" cy="6.5" r="2.5" />
      <path d="M2.5 17v-1.5A3.5 3.5 0 0 1 6 12h3a3.5 3.5 0 0 1 3.5 3.5V17" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 6.7a2.5 2.5 0 0 1 0 4.9M15.5 17v-1.5a3.5 3.5 0 0 0-2.2-3.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconDoor({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="5" y="2.5" width="10" height="15" rx="1" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 10h.01" strokeLinecap="round" />
    </svg>
  );
}

export function IconColumns({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="2.5" y="3" width="15" height="14" rx="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 3v14M12.5 3v14" strokeLinecap="round" />
    </svg>
  );
}

export function IconWand({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M4 16 14 6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15.5 2.5v2M18.5 5.5h-2M13.2 4.3l1.1 1.1M16.6 7.7l1.1 1.1" strokeLinecap="round" />
      <path d="M4.5 12v2M3.5 13h2" strokeLinecap="round" />
    </svg>
  );
}

export function IconSearch({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="8.75" cy="8.75" r="5.25" />
      <path d="m17 17-4.35-4.35" strokeLinecap="round" />
    </svg>
  );
}

export function IconBeaker({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M8 2.5h4M8.5 2.5v5.2L4.3 15a1.5 1.5 0 0 0 1.3 2.5h8.8a1.5 1.5 0 0 0 1.3-2.5L11.5 7.7V2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6.2 12.5h7.6" strokeLinecap="round" />
    </svg>
  );
}

export function IconBuilding({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <rect x="4" y="2.5" width="9" height="15" rx="1" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 8.5h2.5a1 1 0 0 1 1 1v7.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6.5 5.5h1M9.5 5.5h1M6.5 8.5h1M9.5 8.5h1M6.5 11.5h1M9.5 11.5h1" strokeLinecap="round" />
    </svg>
  );
}

export function IconSpinner({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className} animate-spin`}>
      <circle cx="10" cy="10" r="7.25" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.25" />
      <path d="M17.25 10a7.25 7.25 0 0 0-7.25-7.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconPrinter({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M6 7V3.5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1V7" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="3" y="7" width="14" height="7.5" rx="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 12h8v4.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V12Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6.5 9.75h.01" strokeLinecap="round" />
    </svg>
  );
}
