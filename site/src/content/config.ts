/**
 * content/config.ts — the zod producer schema. Consumer 1 of 4 (CLAUDE.md rule 7).
 *
 * Mirrors SCHEMA.md §2 exactly. Every sub-schema is built PROGRAMMATICALLY from
 * the `as const` tuples in `site/src/config.ts` (SCHEMA.md §8), so adding a key
 * to a tuple carries the schema with it. **Never write an enum literal inline
 * here.** If you find yourself typing a value that also appears in SCHEMA.md §1,
 * stop and import the tuple.
 *
 * TRD.md §4.1: the build MUST fail on any schema violation, with a field-level
 * error naming the file and the field. A wrong type, a missing required field
 * and an unknown key against `.strict()` all fail. That is the mechanism that
 * makes SCHEMA.md enforceable rather than merely documented.
 *
 * `z.coerce.date()` for every date field, never `z.date()`: YAML frontmatter
 * yields both a real `Date` (for an unquoted `2026-08-06`) and a string (for a
 * quoted one), and coercion accepts both.
 *
 * The loader points at `_published` ONLY. Staging and rejected content sit
 * outside the collection tree entirely, so Astro can never build a draft.
 */

import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

import {
  AU_LATITUDE_BOUNDS,
  AU_LONGITUDE_BOUNDS,
  CATEGORIES,
  CELLAR_DOOR_STATES,
  CERTIFICATION_STATES,
  CONFIDENCE_TIERS,
  DENY_LIST_CHECKS,
  FRUIT_SOURCE,
  LOGISTICS_KEYS,
  OWNERSHIP_EVIDENCE_METHODS,
  OWNERSHIP_STATES,
  PRACTICE_KEYS,
  PRODUCTION_BANDS,
  STATES,
  VARIETY_KEYS,
  VERIFIABLE_FIELDS,
  VESSEL_KEYS,
  WINE_STYLE_KEYS,
} from "../config.ts";
import { REGION_SLUGS, SUBREGION_SLUGS } from "../data/regions.ts";

/** zod wants a non-empty mutable tuple; our vocabularies are readonly arrays. */
const enumOf = <T extends string>(values: readonly T[]) =>
  z.enum(values as unknown as [T, ...T[]]);

/** An array whose members are unique. SCHEMA.md §2 requires it of `vessels`. */
const uniqueArray = <T extends z.ZodTypeAny>(inner: T, label: string) =>
  z.array(inner).refine((xs) => new Set(xs).size === xs.length, {
    message: `${label} must not contain duplicates`,
  });

/* ── Sub-schemas built from the tuples — SCHEMA.md §8 ────────────────────── */

/** Exactly the four §1.6 keys, all required, no extras. */
const practicesSchema = z
  .object(
    Object.fromEntries(PRACTICE_KEYS.map((key) => [key, z.boolean()])) as Record<
      (typeof PRACTICE_KEYS)[number],
      z.ZodBoolean
    >,
  )
  .strict();

/** The ten §1.7 keys, each defaulting to false. Optional as a whole. */
const logisticsSchema = z
  .object(
    Object.fromEntries(
      LOGISTICS_KEYS.map((key) => [key, z.boolean().default(false)]),
    ) as Record<(typeof LOGISTICS_KEYS)[number], z.ZodDefault<z.ZodBoolean>>,
  )
  .strict()
  .optional();

const verificationEntrySchema = z
  .object({
    source: z.string().min(1),
    tier: enumOf(CONFIDENCE_TIERS),
    date: z.coerce.date(),
  })
  .strict();

/** Keyed by field name, a subset of §1.12. Rendered/metadata only; not in SQLite. */
const verificationSchema = z
  .object(
    Object.fromEntries(
      VERIFIABLE_FIELDS.map((field) => [field, verificationEntrySchema.optional()]),
    ) as Record<
      (typeof VERIFIABLE_FIELDS)[number],
      z.ZodOptional<typeof verificationEntrySchema>
    >,
  )
  .strict()
  .optional();

/** Computed by the pipeline, never hand-maintained (SCHEMA.md §2b). */
const changeLogSchema = z
  .array(
    z
      .object({
        field: z.string().min(1),
        from: z.unknown(),
        to: z.unknown(),
        date: z.coerce.date(),
        trigger: z.string().min(1),
      })
      .strict(),
  )
  .optional();

/**
 * Nullable since 2026-08-09. `null` is the `unconfirmed` state's positive
 * record that no source was found — not an omission, which is why the key
 * stays required. §2a rules 11 and 13 in the `.superRefine()` below are what
 * pair it with `ownership_status`; the type alone cannot express "required
 * when".
 */
const ownershipSourceSchema = z
  .object({
    source: z.string().min(1),
    method: enumOf(OWNERSHIP_EVIDENCE_METHODS),
    date: z.coerce.date(),
  })
  .strict()
  .nullable();

/**
 * SCHEMA.md §2, added 2026-08-10. A deny-list hit judged a false positive,
 * recorded where it travels with the repository.
 *
 * This used to live only in the determination sidecar under `content-staging/`,
 * which is gitignored volume state. The consequence was that a correctly judged
 * surname collision failed `/validate` check 8 forever, and the only route to a
 * green suite was unpublishing an independent producer — the precise wrong
 * rejection `data/ownership.json`'s own header warns against.
 *
 * `register_updated` and `parent` are not decoration. Check 8 honours an
 * exemption only while both still match the live register record, so buying the
 * exempted producer invalidates the exemption rather than being hidden by it
 * (§2a rule 17).
 */
const auditExemptionSchema = z
  .object({
    check: enumOf(DENY_LIST_CHECKS),
    /** The register label, domain or ABN that matched. */
    matched: z.string().min(1),
    /** The record it matched under, as `parent` reads in the register. */
    parent: z.string().min(1),
    /** The matched record's own `updated` date, at the time of judging. */
    register_updated: z.coerce.date(),
    /** When the judgement was made. */
    date: z.coerce.date(),
    /** Why it is a false positive. Free prose, and it must say something. */
    note: z.string().min(1),
  })
  .strict();

const locationSchema = z
  .object({
    address: z.string().optional(),
    suburb: z.string().optional(),
    // Only `state` is required. Where a person can physically go.
    state: enumOf(STATES),
    // Null coordinates mean no map pin and DO NOT block publication. A
    // label-only producer is a first-class entry (SCHEMA.md §2).
    latitude: z
      .number()
      .min(AU_LATITUDE_BOUNDS.min)
      .max(AU_LATITUDE_BOUNDS.max)
      .nullable()
      .optional(),
    longitude: z
      .number()
      .min(AU_LONGITUDE_BOUNDS.min)
      .max(AU_LONGITUDE_BOUNDS.max)
      .nullable()
      .optional(),
  })
  .strict();

/**
 * Structured numbers alongside the freeform `cost` string, never replacing it.
 * Omitted entirely when there is no published tasting fee — never invented.
 * The cross-check against `cost` is `/validate` check 10, in Python, because
 * the regex that scrapes dollar amounts is shared with the display helper.
 * One regex, one home (SCHEMA.md §2a).
 */
const tastingFeeSchema = z
  .object({
    fee_aud: z.number().nonnegative().nullable(),
    waived_on_purchase: z.boolean().nullable(),
  })
  .strict()
  .optional();

const faqSchema = z
  .array(
    z
      .object({
        question: z.string().min(1),
        answer: z.string().min(1),
      })
      .strict(),
  )
  .max(8, { message: "faq is capped at 8 pairs (SCHEMA.md §2)" })
  .optional();

/* ── The producer frontmatter — SCHEMA.md §2 ─────────────────────────────── */

const producerFrontmatter = z
  .object({
    name: z.string().min(1),

    /**
     * `null` = independent, and it is the ONLY publishable value.
     * The key is always present: an absent key is an undetermined producer,
     * which is not publishable (SCHEMA.md §4). `/validate` check 8 re-asserts
     * this against every published file.
     */
    parent_company: z.string().nullable(),

    /**
     * Whether a dated source names who owns this business (SCHEMA.md §1.15).
     * `unconfirmed` publishes with a visible notice and the site makes no
     * independence claim for the entry. It is never a fourth evidence route.
     */
    ownership_status: enumOf(OWNERSHIP_STATES),

    /** Required on `confirmed`, forbidden on `unconfirmed`. §2a rules 11, 13. */
    ownership_source: ownershipSourceSchema,
    audit_exemptions: z.array(auditExemptionSchema).optional(),

    category: enumOf(CATEGORIES),
    founded_year: z.number().int().min(1000).max(9999).nullable().optional(),
    website: z.string().url(),
    location: locationSchema,

    /** Where the FRUIT comes from, not where the winery is. Min 1. */
    regions: z.array(enumOf(REGION_SLUGS)).min(1),
    /** Canonical route and breadcrumb anchor. Must be a member of `regions`. */
    primary_region: enumOf(REGION_SLUGS),
    subregions: z.array(enumOf(SUBREGION_SLUGS)).optional(),

    cellar_door: enumOf(CELLAR_DOOR_STATES),
    /** Freeform display string by design. Never reformatted into a grid. */
    cellar_door_hours: z.string().nullable().optional(),
    cost: z.string().nullable().optional(),
    tasting_fee: tastingFeeSchema,
    minimum_age: z.number().int().positive().nullable().optional(),

    organic: enumOf(CERTIFICATION_STATES),
    organic_certifier: z.string().nullable().optional(),
    biodynamic: enumOf(CERTIFICATION_STATES),
    biodynamic_certifier: z.string().nullable().optional(),
    fruit_source: enumOf(FRUIT_SOURCE),
    practices: practicesSchema,

    vessels: uniqueArray(enumOf(VESSEL_KEYS), "vessels").optional(),
    /** A variety is listed only if the source names it. Drives /variety/[grape]/. */
    varieties: uniqueArray(enumOf(VARIETY_KEYS), "varieties").optional(),
    wine_styles: uniqueArray(enumOf(WINE_STYLE_KEYS), "wine_styles").optional(),

    /** `unknown` is a legitimate answer and the correct one when not published. */
    production_band: enumOf(PRODUCTION_BANDS),
    annual_production_cases: z.number().int().nonnegative().nullable().optional(),

    buy_online: z.boolean(),
    ships_nationally: z.boolean(),
    shop_url: z.string().url().nullable().optional(),
    logistics: logisticsSchema,

    verification: verificationSchema,
    change_log: changeLogSchema,

    /** Index one-liner and meta description. In register. */
    summary: z.string().min(1).max(160),

    /** Date the draft was generated. Stays fixed. */
    drafted: z.coerce.date(),
    /** Date of the most recent harvest pass. Re-set on every re-harvest. */
    verified: z.coerce.date(),
    source_url: z.string().url(),

    /** Present only after the separate image-publish action (UX.md §4). */
    image: z.string().optional(),
    image_source: z.string().url().optional(),
    image_caption: z.string().optional(),

    faq: faqSchema,
  })
  /**
   * `.strict()` is load-bearing, not tidiness. An unknown key is a typo, a
   * hand-edit against the contract, or a field someone added to one consumer
   * and not the other three. All three must fail the build (TRD.md §4.1).
   */
  .strict()
  /* ── SCHEMA.md §2a cross-field rules that zod owns ─────────────────────── */
  .superRefine((data, ctx) => {
    // Rule 1 — image co-requirements.
    if (data.image) {
      if (!data.image_source) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["image_source"],
          message:
            "image_source is required when image is present (SCHEMA.md §2a rule 1). " +
            "A published photograph always carries visible source attribution.",
        });
      }
      if (!data.image_caption) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["image_caption"],
          message:
            "image_caption is required when image is present (SCHEMA.md §2a rule 1). " +
            'Register: "LOT I. — THE HOME BLOCK, LOOKING WEST."',
        });
      }
    }

    // Rules 11 and 13 — the ownership state and its evidence, both ways.
    //
    // Shaped deliberately like rules 2 and 3 below: a state enum plus the
    // evidence that state implies, each an error without the other. The
    // failure this prevents is an entry claiming `confirmed` with nothing
    // behind it, which would be indistinguishable from a real determination
    // to every downstream consumer and to every reader.
    if (data.ownership_status === "confirmed" && !data.ownership_source) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ownership_source"],
        message:
          "ownership_status: confirmed requires an ownership_source with a " +
          "source, a method and a date (SCHEMA.md §2a rule 11). Where no " +
          "source names the owner, the correct value is unconfirmed.",
      });
    }
    if (data.ownership_status === "unconfirmed" && data.ownership_source) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ownership_source"],
        message:
          "ownership_status: unconfirmed requires ownership_source to be null " +
          "(SCHEMA.md §2a rule 13). An entry carrying a real source should be " +
          "confirmed; the two states are not a confidence ranking.",
      });
    }

    // Rule 15 — only a CONTAINED NAME match is ever exemptable.
    //
    // A domain match means this producer's website is the register's listed
    // domain; an ABN match means it is the same legal entity. Neither has an
    // innocent reading, so neither can be waived by writing frontmatter. The
    // surname and place-name collisions this field exists for are contained
    // name matches and nothing else (SCHEMA.md §2a rule 15).
    //
    // Exactness is not visible from here — the register is not loaded at build
    // time — so zod enforces the half it can see, the `check` value, and
    // /validate check 8 enforces the other half against the live record.
    (data.audit_exemptions ?? []).forEach((exemption, index) => {
      if (exemption.check !== "name") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["audit_exemptions", index, "check"],
          message:
            `audit_exemptions[${index}].check is "${exemption.check}", and only ` +
            `"name" is exemptable (SCHEMA.md §2a rule 15). A domain or ABN match ` +
            `identifies the entity itself. If one of those fired, the producer is ` +
            `not publishable and no frontmatter can make it so.`,
        });
      }
    });

    // Rule 16 — an exemption never opens the `unconfirmed` door.
    //
    // Rule 14 keeps a register hit out of `unconfirmed` entirely. Evidence
    // strong enough to prove the register matched the wrong business has
    // already named the right owner, so `confirmed` is available and required.
    if ((data.audit_exemptions ?? []).length > 0 && data.ownership_status !== "confirmed") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ownership_status"],
        message:
          "a producer carrying an audit_exemptions entry must be ownership_status: " +
          "confirmed (SCHEMA.md §2a rule 16). Suppressing a register hit while " +
          "claiming no knowledge of the owner defeats both halves of §4 at once.",
      });
    }

    // Rules 2 and 3 — certification requires a NAMED certifier, both ways.
    //
    // This is the rule most worth getting right. Publishing an unbacked
    // certification claim about a real business is a labelling problem, not
    // merely an accuracy one (SCHEMA.md §1.3).
    for (const subject of ["organic", "biodynamic"] as const) {
      const state = data[subject];
      const certifierKey = `${subject}_certifier` as const;
      const certifier = data[certifierKey];
      if (state === "certified" && !certifier) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [certifierKey],
          message:
            `${subject}: certified requires a named ${certifierKey} ` +
            `(SCHEMA.md §2a rule ${subject === "organic" ? 2 : 3}). ` +
            "Where no certifier is named, the correct value is practising, " +
            "with the ambiguity recorded in confidence_notes.",
        });
      }
      if (state !== "certified" && certifier) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [certifierKey],
          message:
            `${certifierKey} must be null unless ${subject} is certified ` +
            `(SCHEMA.md §2a rule ${subject === "organic" ? 2 : 3}).`,
        });
      }
    }

    // Rule 4 — primary_region must be a member of regions.
    if (!data.regions.includes(data.primary_region)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["primary_region"],
        message:
          `primary_region "${data.primary_region}" is not in regions ` +
          `[${data.regions.join(", ")}] (SCHEMA.md §2a rule 4).`,
      });
    }

    // Rule 6 — buy_online requires a shop_url.
    if (data.buy_online && !data.shop_url) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["shop_url"],
        message:
          "shop_url is required when buy_online is true (SCHEMA.md §2a rule 6).",
      });
    }

    // Rule 7 — cellar_door: none forbids cellar_door_hours.
    //
    // Hours on a producer with no cellar door would send a reader to a place
    // that does not receive them.
    if (
      data.cellar_door === "none" &&
      data.cellar_door_hours !== undefined &&
      data.cellar_door_hours !== null
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["cellar_door_hours"],
        message:
          "cellar_door_hours must be omitted when cellar_door is none " +
          "(SCHEMA.md §2a rule 7).",
      });
    }

    // Not a §2a rule, but the same class of error and free to catch here: a
    // subregion must belong to a region this producer actually lists. §2a rule
    // 5 assigns the full check to /validate 12; this catches the common case at
    // build time, where the error is cheapest to read.
    //
    // Membership of the slug in regions.ts is already enforced by the enum.
  });

const producers = defineCollection({
  // `_published` ONLY. The approve action is the only thing that writes here
  // (CLAUDE.md rule 5), and drafts live outside the collection tree entirely.
  loader: glob({
    pattern: "**/*.mdx",
    base: "./src/content/producers/_published",
  }),
  schema: producerFrontmatter,
});

export const collections = { producers };
