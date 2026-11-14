import { afterEach, describe, expect, it } from "vitest";
import "../src/index";
import { configFromForm, editorSchema, formData } from "../src/editor";
import type { MagisterHomeworkCardEditor } from "../src/editor";
import { textsFor } from "../src/translations";

describe("editor schema", () => {
  it("restricts the entity to Magister to-do lists and offers the card options", () => {
    const schema = editorSchema();
    expect(schema.map((field) => field.name)).toEqual([
      "entity",
      "title",
      "language",
      "show_completed",
      "show_past",
      "days_ahead",
      "show_progress_tomorrow",
      "show_progress_week",
      "show_progress_next_week",
    ]);
    expect(schema[0]).toMatchObject({
      required: true,
      selector: { entity: { filter: { domain: "todo", integration: "magister" } } },
    });
    expect(schema[1]?.selector).toHaveProperty("text");
    expect(schema[2]?.selector).toEqual({
      select: {
        mode: "dropdown",
        options: [
          { value: "auto", label: "Automatic (Home Assistant language)" },
          { value: "nl", label: "Nederlands" },
          { value: "en", label: "English" },
        ],
      },
    });
    const nlSelect = editorSchema(textsFor("nl"))[2]?.selector as {
      select: { options: { value: string; label: string }[] };
    };
    expect(nlSelect.select.options[0]).toEqual({
      value: "auto",
      label: "Automatisch (taal van Home Assistant)",
    });
    expect(schema[3]?.selector).toHaveProperty("boolean");
    expect(schema[4]?.selector).toHaveProperty("boolean");
    expect(schema[5]?.selector).toHaveProperty("number");
    for (const field of schema.slice(6)) expect(field.selector).toHaveProperty("boolean");
  });
});

describe("form <-> config", () => {
  it("shows the defaults for a bare config", () => {
    expect(formData({ entity: "todo.a" })).toEqual({
      entity: "todo.a",
      title: "",
      language: "auto",
      show_completed: false,
      show_past: false,
      days_ahead: 7,
      show_progress_tomorrow: false,
      show_progress_week: false,
      show_progress_next_week: false,
    });
  });

  it("maps the three progress toggles and keeps unknown keys", () => {
    const previous = { type: "custom:x", entity: "todo.a", card_mod: { style: "x" }, show_progress_week: true };
    expect(
      configFromForm(previous, {
        entity: "todo.a",
        show_progress_tomorrow: true,
        show_progress_week: false,
        show_progress_next_week: true,
      }),
    ).toEqual({
      type: "custom:x",
      entity: "todo.a",
      card_mod: { style: "x" },
      show_progress_tomorrow: true,
      show_progress_next_week: true,
    });
    expect(formData(previous)).toMatchObject({
      show_progress_tomorrow: false,
      show_progress_week: true,
    });
  });

  it("keeps the YAML short: defaults and empty values are left out", () => {
    const previous = { type: "custom:magister-homework-card", entity: "todo.a" };
    expect(
      configFromForm(previous, {
        entity: "todo.a",
        title: " ",
        show_completed: false,
        show_past: false,
        days_ahead: 7,
      }),
    ).toEqual({ type: "custom:magister-homework-card", entity: "todo.a" });
  });

  it("keeps the keys it does not manage and removes defaults from the managed ones", () => {
    const previous = {
      type: "custom:magister-homework-card",
      entity: "todo.a",
      show_past: true,
      title: "Oud",
      days_ahead: 3,
      grid_options: { columns: 12 },
      visibility: [{ condition: "user", users: ["x"] }],
      view_layout: { column: 2 },
      card_mod: { style: "ha-card { color: red; }" },
    };
    const config = configFromForm(previous, {
      entity: "todo.a",
      title: "",
      show_completed: true,
      show_past: false,
      days_ahead: 7,
    });
    expect(config).toEqual({
      type: "custom:magister-homework-card",
      entity: "todo.a",
      show_completed: true,
      grid_options: { columns: 12 },
      visibility: [{ condition: "user", users: ["x"] }],
      view_layout: { column: 2 },
      card_mod: { style: "ha-card { color: red; }" },
    });
  });

  it("stores the language, drops auto, and keeps card_id and unknown keys", () => {
    const previous = {
      type: "custom:magister-homework-card",
      entity: "todo.a",
      card_id: "abc123",
      card_mod: { style: "x" },
      future_option: 5,
    };
    const nl = configFromForm(previous, { entity: "todo.a", language: "nl" });
    expect(nl).toEqual({ ...previous, language: "nl" });
    expect(configFromForm(nl, { entity: "todo.a", language: "en" }).language).toBe("en");
    const auto = configFromForm(nl, { entity: "todo.a", language: "auto" });
    expect(auto).toEqual(previous);
    expect(formData(nl).language).toBe("nl");
  });

  it("stores changed options", () => {
    const config = configFromForm(
      { type: "custom:magister-homework-card", entity: "todo.a" },
      { entity: "todo.b", title: "Anna", show_completed: true, show_past: true, days_ahead: 14 },
    );
    expect(config).toEqual({
      type: "custom:magister-homework-card",
      entity: "todo.b",
      title: "Anna",
      show_completed: true,
      show_past: true,
      days_ahead: 14,
    });
  });

  it("ignores an empty or invalid days_ahead and caps a huge one", () => {
    const base = { type: "custom:magister-homework-card", entity: "todo.a" };
    expect(configFromForm(base, { entity: "todo.a", days_ahead: "" }).days_ahead).toBeUndefined();
    expect(configFromForm(base, { entity: "todo.a", days_ahead: -2 }).days_ahead).toBeUndefined();
    expect(configFromForm(base, { entity: "todo.a", days_ahead: 0 }).days_ahead).toBe(0);
    expect(configFromForm(base, { entity: "todo.a", days_ahead: 9999 }).days_ahead).toBe(365);
  });
});

describe("editor element", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders an ha-form with the schema and fires config-changed", async () => {
    const editor = document.createElement("magister-homework-card-editor") as MagisterHomeworkCardEditor;
    document.body.append(editor);
    editor.hass = { language: "nl", connection: {} as never, callWS: () => Promise.resolve({} as never) };
    editor.setConfig({ type: "custom:magister-homework-card", entity: "todo.a" });
    await editor.updateComplete;

    const form = editor.shadowRoot?.querySelector("ha-form") as
      | (HTMLElement & { schema: unknown; data: unknown; computeLabel: (s: { name: string }) => string })
      | null;
    expect(form).not.toBeNull();
    expect(form?.schema).toEqual(editorSchema(textsFor("nl")));
    expect(form?.data).toMatchObject({ entity: "todo.a", days_ahead: 7 });
    expect(form?.computeLabel({ name: "show_past" })).toBe("Toon eerdere dagen");
    expect(form?.computeLabel({ name: "show_progress_next_week" })).toBe(
      "Toon voortgang van volgende week",
    );
    expect(form?.computeLabel({ name: "show_progress_tomorrow" })).toBe(
      "Toon voortgang volgende schooldag",
    );
    expect(form?.computeLabel({ name: "language" })).toBe("Taal van de kaart");

    const changes: unknown[] = [];
    editor.addEventListener("config-changed", (event) => {
      changes.push((event as CustomEvent).detail);
    });
    form?.dispatchEvent(
      new CustomEvent("value-changed", { detail: { value: { entity: "todo.a", show_past: true } } }),
    );
    expect(changes).toEqual([
      {
        config: {
          type: "custom:magister-homework-card",
          entity: "todo.a",
          show_past: true,
          card_id: expect.stringMatching(/^[0-9a-z]{8,}$/) as unknown,
        },
      },
    ]);
    // the id is made once and then kept
    const first = (changes[0] as { config: { card_id: string } }).config.card_id;
    form?.dispatchEvent(
      new CustomEvent("value-changed", { detail: { value: { entity: "todo.a", show_past: false } } }),
    );
    expect((changes[1] as { config: { card_id: string } }).config.card_id).toBe(first);
  });

  it("the editor in English labels the language option in English", async () => {
    const editor = document.createElement("magister-homework-card-editor") as MagisterHomeworkCardEditor;
    document.body.append(editor);
    editor.hass = { language: "en", connection: {} as never, callWS: () => Promise.resolve({} as never) };
    editor.setConfig({ type: "custom:magister-homework-card", entity: "todo.a" });
    await editor.updateComplete;
    const form = editor.shadowRoot?.querySelector("ha-form") as
      | (HTMLElement & { computeLabel: (s: { name: string }) => string })
      | null;
    expect(form?.computeLabel({ name: "language" })).toBe("Card language");
    expect(form?.computeLabel({ name: "show_progress_tomorrow" })).toBe(
      "Show next school day progress",
    );
  });

  it("renders nothing until it has a config", async () => {
    const editor = document.createElement("magister-homework-card-editor") as MagisterHomeworkCardEditor;
    document.body.append(editor);
    await editor.updateComplete;
    expect(editor.shadowRoot?.querySelector("ha-form")).toBeNull();
  });
});
