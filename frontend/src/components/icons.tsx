/** Small hand-authored inline SVG icons (no icon library dependency) -
 * consistent 20x20 outline style, `currentColor` stroke so they inherit
 * text color/size from their container. */

type IconProps = { className?: string };

const base = "h-4 w-4";

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

export function IconSpinner({ className = base }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className} animate-spin`}>
      <circle cx="10" cy="10" r="7.25" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.25" />
      <path d="M17.25 10a7.25 7.25 0 0 0-7.25-7.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
