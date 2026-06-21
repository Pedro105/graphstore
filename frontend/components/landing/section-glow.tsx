import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

type GlowPlacement =
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right"
  | "center-left"
  | "center-right";

type GlowVariant = "on-light" | "on-soft";

export interface SectionGlowProps {
  placement: GlowPlacement;
  variant?: GlowVariant;
  size?: "sm" | "md" | "lg";
}

/** Anchor point for each blob — kept inside the section so nothing gets clipped */
const PLACEMENT_AT: Record<GlowPlacement, string> = {
  "top-left": "10% 12%",
  "top-right": "90% 8%",
  "bottom-left": "8% 88%",
  "bottom-right": "92% 85%",
  "center-left": "8% 62%",
  "center-right": "88% 48%",
};

const BLOB_SIZE: Record<NonNullable<SectionGlowProps["size"]>, string> = {
  sm: "40% 34%",
  md: "52% 44%",
  lg: "62% 52%",
};

/** [center, mid-stop] — visible but still soft against #f9f8f6 / #efe9e3 */
const BLOB_COLOR: Record<GlowVariant, [string, string]> = {
  "on-light": [
    "rgba(217, 207, 199, 0.42)",
    "rgba(239, 233, 227, 0.16)",
  ],
  "on-soft": [
    "rgba(201, 181, 156, 0.34)",
    "rgba(217, 207, 199, 0.11)",
  ],
};

function glowLayer({
  placement,
  variant = "on-light",
  size = "md",
}: SectionGlowProps): string {
  const [center, mid] = BLOB_COLOR[variant];
  return `radial-gradient(ellipse ${BLOB_SIZE[size]} at ${PLACEMENT_AT[placement]}, ${center} 0%, ${mid} 40%, transparent 76%)`;
}

/** Paint blobs as background-image layers on the section itself (reliable, no clipping) */
export function sectionGlowStyle(
  glows?: SectionGlowProps[],
): CSSProperties | undefined {
  if (!glows?.length) return undefined;
  return {
    ["--section-glow-layers" as string]: glows.map(glowLayer).join(", "),
  };
}

interface GlowSectionProps {
  children: ReactNode;
  className?: string;
  glows?: SectionGlowProps[];
  id?: string;
}

export function GlowSection({
  children,
  className,
  glows,
  id,
}: GlowSectionProps) {
  const glowStyle = sectionGlowStyle(glows);

  return (
    <section
      id={id}
      data-section-glow={glows?.length ? "" : undefined}
      className={cn("relative isolate", className)}
      style={glowStyle}
    >
      <div className="relative z-[1]">{children}</div>
    </section>
  );
}

/** Shared pill styling for landing tags and meta chips */
export const landingPillClassName =
  "inline-flex items-center gap-1.5 rounded-full border border-border/45 bg-card px-3 py-1.5 shadow-[0_1px_2px_rgba(26,26,26,0.05),0_3px_10px_rgba(26,26,26,0.04)]";

/** Subtle elevation for demo cards and entity rows */
export const landingSurfaceClassName =
  "shadow-[0_1px_2px_rgba(26,26,26,0.04),0_6px_20px_rgba(26,26,26,0.05)]";

export const landingRowClassName =
  "shadow-[0_1px_2px_rgba(26,26,26,0.04),0_2px_8px_rgba(26,26,26,0.03)]";
