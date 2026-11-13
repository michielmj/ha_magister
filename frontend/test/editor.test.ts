import { afterEach, describe, expect, it } from "vitest";
import "../src/index";
import { configFromForm, editorSchema, formData } from "../src/editor";
import type { MagisterHomeworkCardEditor } from "../src/editor";

describe("editor schema", () => {
  it("restricts the entity to Magister to-do lists and offers the card options", () => {
    const schema = editorSchema();
    expect(schema.map((field) => field.name)).toEqual([
      "entity",
      "title",
      "show_completed",
      "show_past",
      "days_ahead",
    ]);
    expect(schema[0]).toMatchObject({
      required: true,
      selector: { entity: { domain: "todo", integration: "magister" } },
    });
    expect(schema[1]?.selector).toHaveProperty("text");
    expect(schema[2]?.selector).toHaveProperty("boolean");
    expect(schema[3]?.selector).toHaveProperty("boolean");
    expect(schema[4]?.selector).toHaveProperty("number");
  });
});

describe("form <-> config", () => {
  it("shows the defaults for a bare config", () => {
    expect(formData({ entity: "todo.a" })).toEqual({
      entity: "todo.a",
      title: "",
      show_completed: false,
      show_past: false,
      days_ahead: 7,
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
    expect(form?.schema).toEqual(editorSchema());
    expect(form?.data).toMatchObject({ entity: "todo.a", days_ahead: 7 });
    expect(form?.computeLabel({ name: "show_past" })).toBe("Toon eerdere dagen");

    const changes: unknown[] = [];
    editor.addEventListener("config-changed", (event) => {
      changes.push((event as CustomEvent).detail);
    });
    form?.dispatchEvent(
      new CustomEvent("value-changed", { detail: { value: { entity: "todo.a", show_past: true } } }),
    );
    expect(changes).toEqual([
      { config: { type: "custom:magister-homework-card", entity: "todo.a", show_past: true } },
    ]);
  });

  it("renders nothing until it has a config", async () => {
    const editor = document.createElement("magister-homework-card-editor") as MagisterHomeworkCardEditor;
    document.body.append(editor);
    await editor.updateComplete;
    expect(editor.shadowRoot?.querySelector("ha-form")).toBeNull();
  });
});
