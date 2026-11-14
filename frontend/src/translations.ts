export type Language = "nl" | "en";

const nl = {
  today: "Vandaag",
  tomorrow: "Morgen",
  earlier: "Eerder",
  no_homework: "Geen huiswerk 🎉",
  loading: "Laden…",
  unavailable:
    "Magister is niet beschikbaar. Je ziet het laatst bekende huiswerk; wijzigen kan nu niet.",
  offline: "Verbinding met Home Assistant verbroken. Opnieuw verbinden…",
  choose_entity: "Kies een Magister-huiswerklijst in de kaartinstellingen.",
  not_found: "Deze huiswerklijst is niet gevonden.",
  unauthorized: "Je hebt geen toegang tot deze huiswerklijst.",
  load_failed: "Het huiswerk kon niet worden geladen.",
  save_failed: "Opslaan mislukt. De wijziging is teruggedraaid.",
  save_unauthorized: "Geen rechten om voortgang te wijzigen.",
  dismiss: "Sluiten",
  cancelled: "Les vervallen",
  attachments: "Bijlagen in Magister",
  lesson_hour: "Uur {n}",
  mark_done: "Markeer {subject} als klaar",
  mark_open: "Markeer {subject} als niet klaar",
  progress_of: "Voortgang van {subject}",
  percent: "{n} %",
  expand: "Toon de volledige tekst",
  collapse: "Toon minder",
  progress_label: {
    next_day: "Volgende schooldag",
    week: "Deze week",
    next_week: "Volgende week",
  },
  progress_done: "{completed} van {items} klaar",
  progress_empty: "geen huiswerk",
  progress_unavailable: "niet beschikbaar",
  switches_label: "Weergave",
  show_completed_switch: "Afgerond",
  show_completed_tip: "Toon afgerond huiswerk",
  show_past_switch: "Eerder",
  show_past_tip: "Toon eerdere dagen",
  add_label: "Label toevoegen",
  remove_label: "Label verwijderen",
  confirm_remove: "Label {name} verwijderen?",
  confirm_yes: "Verwijderen",
  confirm_no: "Annuleren",
  kind: { homework: "huiswerk", test: "toets" },
  all_day: "Hele dag",
  dialog: {
    title: "Label toevoegen",
    date: "Dag",
    lessons: "Les",
    lessons_loading: "Lessen laden…",
    no_lessons: "Geen lessen op deze dag.",
    label: "Label",
    choose_label: "Kies een label",
    note: "Notitie (optioneel)",
    note_count: "{n} van 200 tekens",
    save: "Opslaan",
    saving: "Opslaan…",
    cancel: "Annuleren",
    close: "Sluiten",
  },
  label_errors: {
    unauthorized: "Je hebt geen rechten om labels te wijzigen.",
    not_found: "Deze huiswerklijst is niet gevonden.",
    invalid_format: "Ongeldige invoer.",
    invalid_date: "Deze dag valt buiten de opgehaalde periode.",
    appointment_not_found: "Deze les is niet meer gevonden. Kies de dag opnieuw.",
    label_not_found: "Dit label bestaat niet meer. Kies een ander label.",
    label_exists: "Deze les heeft dit label al.",
    label_not_on_appointment: "Dit label staat niet meer op de les.",
    default: "Opslaan mislukt.",
    load_default: "De lessen konden niet worden geladen.",
  } as Record<string, string>,
  type: {
    1: "Huiswerk",
    2: "Proefwerk",
    3: "Tentamen",
    4: "SO",
    5: "MO",
  },
  editor: {
    entity: "Huiswerklijst (to-do van een kind)",
    title: "Titel (optioneel)",
    language: "Taal van de kaart",
    language_auto: "Automatisch (taal van Home Assistant)",
    show_completed: "Toon afgerond huiswerk",
    show_past: "Toon eerdere dagen",
    days_ahead: "Dagen vooruit",
    show_progress_tomorrow: "Toon voortgang volgende schooldag",
    show_progress_week: "Toon voortgang van deze week",
    show_progress_next_week: "Toon voortgang van volgende week",
  },
};

export type Texts = typeof nl;

const en: Texts = {
  today: "Today",
  tomorrow: "Tomorrow",
  earlier: "Earlier",
  no_homework: "No homework",
  loading: "Loading…",
  unavailable:
    "Magister is not available. You see the last known homework; changes are not possible now.",
  offline: "Connection to Home Assistant lost. Reconnecting…",
  choose_entity: "Choose a Magister homework list in the card settings.",
  not_found: "This homework list was not found.",
  unauthorized: "You have no access to this homework list.",
  load_failed: "The homework could not be loaded.",
  save_failed: "Saving failed. The change was rolled back.",
  save_unauthorized: "No permission to change progress.",
  dismiss: "Dismiss",
  cancelled: "Lesson cancelled",
  attachments: "Attachments in Magister",
  lesson_hour: "Period {n}",
  mark_done: "Mark {subject} as done",
  mark_open: "Mark {subject} as not done",
  progress_of: "Progress of {subject}",
  percent: "{n}%",
  expand: "Show the full text",
  collapse: "Show less",
  progress_label: {
    next_day: "Next school day",
    week: "This week",
    next_week: "Next week",
  },
  progress_done: "{completed} of {items} done",
  progress_empty: "no homework",
  progress_unavailable: "not available",
  switches_label: "View",
  show_completed_switch: "Done",
  show_completed_tip: "Show completed homework",
  show_past_switch: "Earlier",
  show_past_tip: "Show earlier days",
  add_label: "Add label",
  remove_label: "Remove label",
  confirm_remove: "Remove label {name}?",
  confirm_yes: "Remove",
  confirm_no: "Cancel",
  kind: { homework: "homework", test: "test" },
  all_day: "All day",
  dialog: {
    title: "Add label",
    date: "Day",
    lessons: "Lesson",
    lessons_loading: "Loading lessons…",
    no_lessons: "No lessons on this day.",
    label: "Label",
    choose_label: "Choose a label",
    note: "Note (optional)",
    note_count: "{n} of 200 characters",
    save: "Save",
    saving: "Saving…",
    cancel: "Cancel",
    close: "Close",
  },
  label_errors: {
    unauthorized: "You have no permission to change labels.",
    not_found: "This homework list was not found.",
    invalid_format: "Invalid input.",
    invalid_date: "This day is outside the fetched period.",
    appointment_not_found: "This lesson was not found any more. Choose the day again.",
    label_not_found: "This label no longer exists. Choose another label.",
    label_exists: "This lesson already has this label.",
    label_not_on_appointment: "This label is no longer on the lesson.",
    default: "Saving failed.",
    load_default: "The lessons could not be loaded.",
  },
  type: {
    1: "Homework",
    2: "Test",
    3: "Exam",
    4: "Short test",
    5: "Oral test",
  },
  editor: {
    entity: "Homework list (a child's to-do)",
    title: "Title (optional)",
    language: "Card language",
    language_auto: "Automatic (Home Assistant language)",
    show_completed: "Show completed homework",
    show_past: "Show earlier days",
    days_ahead: "Days ahead",
    show_progress_tomorrow: "Show next school day progress",
    show_progress_week: "Show progress for this week",
    show_progress_next_week: "Show progress for next week",
  },
};

export const TRANSLATIONS: Record<Language, Texts> = { nl, en };

/** Dutch for any Dutch locale (nl, nl-BE, ...), English otherwise (the default). */
/** The card's language: the config override, or the Home Assistant language when "auto". */
export function effectiveLanguage(
  setting: "auto" | Language | undefined,
  hassLanguage: string | undefined,
): Language {
  return setting === "nl" || setting === "en" ? setting : languageOf(hassLanguage);
}

export function languageOf(language: string | undefined): Language {
  return language?.toLowerCase().startsWith("nl") ? "nl" : "en";
}

export function textsFor(language: string | undefined): Texts {
  return TRANSLATIONS[languageOf(language)];
}

/** Replace `{name}` placeholders. */
export function format(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

/** The translated label of an info type; the item's own (Dutch) label for unknown types. */
export function typeLabel(
  texts: Texts,
  infoType: number,
  fallback: string,
): string {
  return (texts.type as Record<number, string>)[infoType] ?? fallback;
}
