import { describe, expect, it } from "vitest";
import { TRANSLATIONS, format, languageOf, textsFor, typeLabel } from "../src/translations";

describe("translations", () => {
  it("picks Dutch for any nl locale and English otherwise (default)", () => {
    expect(languageOf("nl")).toBe("nl");
    expect(languageOf("nl-BE")).toBe("nl");
    expect(languageOf("NL")).toBe("nl");
    expect(languageOf("en")).toBe("en");
    expect(languageOf("de")).toBe("en");
    expect(languageOf(undefined)).toBe("en");
  });

  it("has the same keys in both languages", () => {
    expect(Object.keys(TRANSLATIONS.nl).sort()).toEqual(Object.keys(TRANSLATIONS.en).sort());
    expect(Object.keys(TRANSLATIONS.nl.type)).toEqual(Object.keys(TRANSLATIONS.en.type));
    expect(Object.keys(TRANSLATIONS.nl.editor)).toEqual(Object.keys(TRANSLATIONS.en.editor));
  });

  it("has the empty state texts of the PM", () => {
    expect(textsFor("nl").no_homework).toBe("Geen huiswerk 🎉");
    expect(textsFor("en").no_homework).toBe("No homework");
  });

  it("translates the label from info_type, not from the Dutch label", () => {
    expect(typeLabel(textsFor("nl"), 2, "x")).toBe("Proefwerk");
    expect(typeLabel(textsFor("en"), 2, "Proefwerk")).toBe("Test");
    expect(typeLabel(textsFor("en"), 3, "Tentamen")).toBe("Exam");
    expect(typeLabel(textsFor("en"), 1, "Huiswerk")).toBe("Homework");
    expect(typeLabel(textsFor("en"), 9, "Overig")).toBe("Overig");
  });

  it("fills placeholders and leaves unknown ones alone", () => {
    expect(format("Uur {n} {x}", { n: 3 })).toBe("Uur 3 {x}");
    expect(format(textsFor("nl").mark_done, { subject: "Wiskunde" })).toBe(
      "Markeer Wiskunde als klaar",
    );
  });
});
