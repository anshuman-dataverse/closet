// Line icons from the prototype (design-reference/closet-demo.html). Decorative: aria-hidden.
import type { ReactElement } from "react";

const Svg = ({ children }: { children: React.ReactNode }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {children}
  </svg>
);

export const ICONS: Record<"today" | "closet" | "outfits" | "shop" | "spend" | "profile", ReactElement> = {
  today: (
    <Svg>
      <path d="M9 3.5 12 5l3-1.5 5 2.8-1.8 4.2-2.2-.9V20H8V9.6l-2.2.9L4 6.3z" />
    </Svg>
  ),
  closet: (
    <Svg>
      <path d="M10 6.2a2 2 0 1 1 3 1.7c-.6.4-1 .9-1 1.6v.7" />
      <path d="M12 10.2 3.6 16a1 1 0 0 0 .6 1.8h15.6a1 1 0 0 0 .6-1.8z" />
    </Svg>
  ),
  outfits: (
    <Svg>
      <rect x="3.5" y="8" width="10.5" height="12" rx="1.6" />
      <path d="M8 4.5h10.9a1.6 1.6 0 0 1 1.6 1.6V16" />
    </Svg>
  ),
  shop: (
    <Svg>
      <path d="M3.5 12.3V4.5a1 1 0 0 1 1-1h7.8l8.2 8.2a1.4 1.4 0 0 1 0 2l-6.8 6.8a1.4 1.4 0 0 1-2 0z" />
      <circle cx="8" cy="8" r="1.5" />
    </Svg>
  ),
  spend: (
    <Svg>
      <path d="M6 3.5h12v17l-3-1.8-3 1.8-3-1.8-3 1.8z" />
      <path d="M9 8.5h6M9 12h6M9 15.5h3.5" />
    </Svg>
  ),
  profile: (
    <Svg>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M4.5 20.5c1.4-3.9 4.2-5.9 7.5-5.9s6.1 2 7.5 5.9" />
    </Svg>
  ),
};
