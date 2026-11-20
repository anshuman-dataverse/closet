// Pieces spotted in the owner's own photos, offered as one-tap starters in Add clothes.
import type { Category } from "@/lib/closet/types";
import type { Occasion } from "@/lib/occasions";

export type Starter = { name: string; category: Category; type: string; color_name: string; occasions: Occasion[] };

export const STARTERS: readonly Starter[] = [
  {
    name: "Black quarter-zip pullover",
    category: "Layers",
    type: "Quarter-zip sweater",
    color_name: "Black",
    occasions: ["college", "home"],
  },
  {
    name: "Black short-sleeve shirt",
    category: "Tops",
    type: "Short-sleeve shirt",
    color_name: "Black",
    occasions: ["college", "party"],
  },
  { name: "Black shirt", category: "Tops", type: "Dress shirt", color_name: "Black", occasions: ["office", "party"] },
  {
    name: "Red plaid shirt",
    category: "Tops",
    type: "Flannel shirt",
    color_name: "Red",
    occasions: ["college", "home"],
  },
  { name: "Red shirt", category: "Tops", type: "Casual shirt", color_name: "Red", occasions: ["college", "party"] },
  { name: "Rust shirt", category: "Tops", type: "Casual shirt", color_name: "Rust", occasions: ["college", "party"] },
  {
    name: "Black and white print shirt",
    category: "Tops",
    type: "Printed shirt",
    color_name: "Black",
    occasions: ["party"],
  },
  {
    name: "Navy striped shirt",
    category: "Tops",
    type: "Striped shirt",
    color_name: "Navy",
    occasions: ["college", "party"],
  },
  { name: "White printed shirt", category: "Tops", type: "Printed shirt", color_name: "White", occasions: ["college"] },
  {
    name: "Brown knit polo",
    category: "Tops",
    type: "Polo shirt",
    color_name: "Brown",
    occasions: ["college", "party"],
  },
  { name: "Brown ombré shirt", category: "Tops", type: "Printed shirt", color_name: "Brown", occasions: ["party"] },
  { name: "Yellow polo", category: "Tops", type: "Polo shirt", color_name: "Mustard", occasions: ["college", "home"] },
  {
    name: "White and mustard striped polo",
    category: "Tops",
    type: "Polo shirt",
    color_name: "White",
    occasions: ["college"],
  },
  { name: "Navy kurta", category: "Sets & suits", type: "Kurta", color_name: "Navy", occasions: ["party"] },
  { name: "Red kurta", category: "Sets & suits", type: "Kurta", color_name: "Red", occasions: ["party"] },
  {
    name: "Varsity jacket",
    category: "Layers",
    type: "Bomber jacket",
    color_name: "Black",
    occasions: ["college", "party"],
  },
  {
    name: "Black jacket",
    category: "Layers",
    type: "Suit jacket",
    color_name: "Black",
    occasions: ["office", "party"],
  },
  {
    name: "Light blue jeans",
    category: "Bottoms",
    type: "Jeans",
    color_name: "Light blue",
    occasions: ["college", "party", "home"],
  },
  { name: "Khaki chinos", category: "Bottoms", type: "Chinos", color_name: "Khaki", occasions: ["office", "college"] },
  {
    name: "Cream cargo trousers",
    category: "Bottoms",
    type: "Cargo trousers",
    color_name: "Cream",
    occasions: ["college", "party"],
  },
];
