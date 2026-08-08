/**
 * glossary-icons.ts — which glossary entries get a glyph, and which one.
 *
 * DESIGN.md §6 namespaces the icon keys by vocabulary (`practice_unfined`,
 * `style_red`) because the raw enum values collide across vocabularies. This is
 * the join from a glossary entry back to its glyph.
 *
 * MOST ENTRIES GET NOTHING, AND THAT IS CORRECT. A grape variety, a state, a
 * confidence tier and an ownership-evidence method have no glyph in the §6 set,
 * and none is invented for them: DESIGN.md §6 says an icon is never the only
 * carrier of meaning and never a decoration, so a term with no glyph renders as
 * a term with no glyph rather than getting a stand-in. `hasIcon` is what keeps
 * a missing key from reaching `Icon.astro`, which would throw.
 */

import {
  cellarDoorIcon,
  hasIcon,
  logisticsIcon,
  practiceIcon,
  styleIcon,
  vesselIcon,
  type IconKey,
} from "../icons/paths.ts";
import type { GlossaryEntry } from "./glossary.ts";

export function glossaryIcon(entry: GlossaryEntry): IconKey | null {
  let key: string | null = null;

  switch (entry.vocabulary) {
    case "practice":
      key = practiceIcon(entry.value);
      break;
    case "wine-style":
      key = styleIcon(entry.value);
      break;
    case "vessel":
      key = vesselIcon(entry.value);
      break;
    case "logistics":
      key = logisticsIcon(entry.value);
      break;
    case "cellar-door":
      // `none` renders nothing anywhere on the site: there is no glyph for the
      // absence of a cellar door, and config.ts excludes it from the icon
      // coverage assertion for the same reason.
      key = entry.value === "none" ? null : cellarDoorIcon(entry.value);
      break;
    case "variety":
      // One bunch glyph for every grape. It marks the varieties line and the
      // /variety/ pages (DESIGN.md §6); it does not depict the grape.
      key = "variety";
      break;
    case "fruit-source":
      key = "fruit_source";
      break;
    case "production-band":
      key = "production";
      break;
    default:
      key = null;
  }

  return key !== null && hasIcon(key) ? key : null;
}
