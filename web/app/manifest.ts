import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Closet",
    short_name: "Closet",
    description: "Your wardrobe, outfits and spend.",
    start_url: "/today",
    scope: "/",
    display: "standalone",
    background_color: "#E6EBF1",
    theme_color: "#E6EBF1",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
