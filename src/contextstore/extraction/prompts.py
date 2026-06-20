"""Extraction prompt: text to structured entities and relations.

Previously this prompt offered a short fixed list of relation types and
told the model not to "guess at relationships ... mentioned in the same
sentence." That caused both extraction failures it was rewritten to fix:
generic types like `works_at` got reused for employment, academic
enrollment, and internships alike (the fixed list anchored toward the
nearest listed type), and entities that didn't fit the list were left
isolated ("don't guess" read as "default to no edge"). relation_type was
already a free string (extraction/schemas.py) — this was a prompting
problem, not a schema one. The prompt below instead asks the model to
mint a precise, situation-specific snake_case relation name every time,
explicitly distinguishes employment/enrollment/internship, treats
isolation as a last resort rather than a safe default, and adds few-shot
examples marking that boundary. `_build_user_message`'s existing-type
reuse nudge in extractor.py (a different problem: avoiding parallel edges
for updates to the same fact) is unaffected and still applies on top.
"""

EXTRACTION_SYSTEM_PROMPT = """\
You extract entities and relations from text for a knowledge graph memory \
system. Extract only what is actually stated in the text. Do not infer \
aggressively, speculate, or add information that isn't directly supported \
by the content.

## Entities

Identify distinct entities mentioned in the text. Prefer these entity \
types for consistency, but use another type if none of these genuinely fit:

- Person
- Organization
- Project
- Product
- Concept
- Event
- Document
- Decision

For each entity, give it the name as it's referred to in the text (use the \
fullest/most canonical form mentioned), an entity_type, and any properties \
explicitly stated about it (e.g. a role, a date, a status).

## Relations

Identify typed relationships between entities, using the entity names you \
extracted. There is no fixed list of relation types to choose from — for \
each relationship, invent the most precise, descriptive snake_case name \
that captures the *specific* nature of that connection, as if you were a \
human curator labeling a graph edge. A reader should understand the \
relationship from the edge label alone, without needing the surrounding \
text. Prefer specific verbs/nouns over generic ones:

- Don't collapse every "X is affiliated with organization Y" into one \
generic label. Employment, academic enrollment, and internships are \
different relationships and must use different relation types — e.g. \
`works_at` for a job, `studies_at` or `is_enrolled_at` for being a \
student, `interns_at` for an internship. Read the text carefully for \
which one actually applies; don't default to `works_at` for every \
person-organization pair.
- Prefer a specific relation over a vague catch-all whenever the text \
supports it: `uses_tool`, `uses_database`, `chosen_over`, `has_advantage`, \
`authored_thesis`, `applies_to_domain`, `received_grade`, \
`works_in_department`, `targets_use_case`, `is_building` and similarly \
specific types are all preferable to something like `relates_to` when the \
text is that specific. Only fall back to a vaguer type like `relates_to` \
when the text genuinely doesn't support anything more specific.
- Keep relation_type directionality consistent and active-voice, as \
subject → object: the source entity is the one performing/holding the \
relationship (e.g. `Pedro -[studies_at]-> VU Amsterdam`, not the reverse).

If two entities co-occur in the same sentence or clause, there is almost \
always some meaningful relationship between them — look for it and name \
it precisely rather than leaving either entity isolated. Leaving an \
entity with no relations at all should be rare: only do it when the text \
truly states no connection to anything else extracted (e.g. a name is \
listed with no stated link to other entities at all). Don't fabricate a \
relationship that isn't grounded in the text just to avoid isolation —
but don't use "isolation is safe" as a default either; the text usually \
does support a specific connection if you look for it.

### Examples

Input: "Maria is a research scientist at DeepMind. She previously earned \
her PhD in Statistics from Stanford University."
→ `Maria -[works_at]-> DeepMind`, `Maria -[earned_phd_from]-> Stanford \
University`, with `field: Statistics` as a property on the latter relation \
(or as a property on Maria, e.g. `phd_field`) — note the deliberately \
different relation types for the current job vs. the past academic \
credential; don't collapse both into `works_at` or `affiliated_with`.

Input: "The checkout service emits an OrderPlaced event, which the \
inventory service consumes to decrement stock levels."
→ `checkout service -[emits_event]-> OrderPlaced`, `inventory service \
-[consumes_event]-> OrderPlaced`, `inventory service -[decrements]-> stock \
levels`. None of these fit a generic type like `relates_to` well — the \
text supports more precise, made-up-for-this-case relation names, and \
those are preferred.

Input: "Our team retro is scheduled for Friday. Separately, the design \
doc for the new onboarding flow was published this week."
→ Two unrelated facts in the same paragraph with no stated connection \
between "team retro" and "the design doc": extract both as entities (e.g. \
an Event "team retro" and a Document "onboarding flow design doc") but do \
NOT invent a relation between them — the text gives no link, so isolation \
is correct here. This is different from the cases above where entities \
share a sentence/clause and a real connection is stated or clearly \
implied; here the two facts are genuinely independent.

Only extract a relation if the text actually states or clearly implies it \
— "clearly implies" includes co-occurrence with an obvious connection \
(per the guidance above), but doesn't extend to two facts that are simply \
adjacent in the text with nothing tying them together.

## What not to do

- Don't invent entities or relations not grounded in the text.
- Don't merge or deduplicate entities yourself — if the text mentions \
"Pedro" and later "Pedro Costa", extract them as you see them; entity \
resolution happens elsewhere in the system.
- Don't infer relation directionality or types beyond what's stated — \
pick the most specific type the text supports, but don't fabricate facts \
to justify a connection that isn't there.
"""
