# All 40 questions: original max4 vs five independent results

Automated equality audit plus focused qualitative analysis; not a blind semantic-accuracy benchmark.
Unchanged plans are shown once. Invalid attempts and rejected target patches remain in the raw result archives.

## 1. 5ab3cecd5542992ade7c6eae

How do the Peter Laufer books Forbidden Creatures and No Animals Were Harmed differ in their focus on animals?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the focus of Forbidden Creatures on animals?",
      "dependencies": {},
      "answer_type": "other"
    },
    {
      "id": "q2",
      "question": "What is the focus of No Animals Were Harmed on animals?",
      "dependencies": {},
      "answer_type": "other"
    },
    {
      "id": "q3",
      "question": "How do the Peter Laufer books Forbidden Creatures (focus on animals: {{q1}}) and No Animals Were Harmed (focus on animals: {{q2}}) differ in their focus on animals?",
      "dependencies": {
        "q1": "other",
        "q2": "other"
      },
      "answer_type": "other"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1202; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1202; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1202; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1202; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1202; patch=not_enabled; diagnostic=unknown.

## 2. 5ab42a2b5542996a3a969f5a

What is the name of the historic figure whom participated in surveying the borders of the District of Columbia and had a premier African American recreation center named after him?

Original max4 plan:
```json
null
```

Variant 01: invalid; plan equal=True; raw structure equal=True; tokens=1637; patch=not_enabled; diagnostic=not_enabled.

Variant 02: invalid; plan equal=True; raw structure equal=True; tokens=1598; patch=not_enabled; diagnostic=unknown.

Variant 03: invalid; plan equal=True; raw structure equal=True; tokens=1598; patch=not_enabled; diagnostic=not_enabled.

Variant 04: invalid; plan equal=True; raw structure equal=True; tokens=1598; patch=not_enabled; diagnostic=unknown.

Variant 05: invalid; plan equal=True; raw structure equal=True; tokens=1598; patch=not_enabled; diagnostic=unknown.

## 3. 5a7d3f895542995f4f402248

Pandora- The World of Avatar includes a ride that allows guest to take flight on what animal?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What animal does the ride in Pandora- The World of Avatar allow guests to take flight on?",
      "dependencies": {},
      "answer_type": "work"
    }
  ],
  "final": "q1"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1037; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1037; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1037; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1037; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1037; patch=not_enabled; diagnostic=unknown.

## 4. 5a778b345542992a6e59decf

Who was born first, Susan Oliver or W. S. Van Dyke?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "When was Susan Oliver born?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "When was W. S. Van Dyke born?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Who was born first: Susan Oliver (born {{q1}}) or W. S. Van Dyke (born {{q2}})?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "person"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1135; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1135; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1135; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1135; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1135; patch=not_enabled; diagnostic=unknown.

## 5. 5a8ceddb554299441c6b9f85

What profession does Nora Roberts and Elizabeth Hardwick have in common?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the profession of Nora Roberts?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q2",
      "question": "What is the profession of Elizabeth Hardwick?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q3",
      "question": "What profession do Nora Roberts ({{q1}}) and Elizabeth Hardwick ({{q2}}) have in common?",
      "dependencies": {
        "q1": "work",
        "q2": "work"
      },
      "answer_type": "work"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1136; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1136; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1136; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1136; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1136; patch=not_enabled; diagnostic=unknown.

## 6. 5a7e05f75542995f4f402394

Which was released first, Hot Girls Wanted or China Blue?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What was the release date of Hot Girls Wanted?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "What was the release date of China Blue?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Which was released first: Hot Girls Wanted (released {{q1}}) or China Blue (released {{q2}})?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "work"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1128; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1128; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1128; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1128; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1128; patch=not_enabled; diagnostic=unknown.

## 7. 5ab3306a55429969a97a80fd

The movies The Boatniks and The Great Locomotive Chase were both made by which production company?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What production company made The Boatniks?",
      "dependencies": {},
      "answer_type": "organization"
    },
    {
      "id": "q2",
      "question": "What production company made The Great Locomotive Chase?",
      "dependencies": {},
      "answer_type": "organization"
    },
    {
      "id": "q3",
      "question": "The movies The Boatniks and The Great Locomotive Chase were both made by which production company: {{q1}} or {{q2}}?",
      "dependencies": {
        "q1": "organization",
        "q2": "organization"
      },
      "answer_type": "organization"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

## 8. 5a7cfb2755429907fabef084

What year did the director of The Quiet American die?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who directed The Quiet American?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "In what year did {{q1}} die?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "date"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1051; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1051; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1051; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1051; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1051; patch=not_enabled; diagnostic=unknown.

## 9. 5ab201765542993be8fa98a4

Hobart Paving is a single by a band formed in which year ?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the formation year of the band that released Hobart Paving?",
      "dependencies": {},
      "answer_type": "date"
    }
  ],
  "final": "q1"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1025; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1025; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1025; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1025; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1025; patch=not_enabled; diagnostic=unknown.

## 10. 5adbe27c55429947ff173854

Which university has more campuses, Dalhousie University or California State Polytechnic University, Pomona?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "How many campuses does Dalhousie University have?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q2",
      "question": "How many campuses does California State Polytechnic University, Pomona have?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q3",
      "question": "Which university has more campuses, Dalhousie University (with {{q1}} campuses) or California State Polytechnic University, Pomona (with {{q2}} campuses)?",
      "dependencies": {
        "q1": "number",
        "q2": "number"
      },
      "answer_type": "organization"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1181; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1181; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1181; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1181; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1181; patch=not_enabled; diagnostic=unknown.

## 11. 5a8fa4d95542995b4424207b

Which airport is busier, Palm Springs International Airport or Trenton–Mercer Airport?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the passenger throughput of Palm Springs International Airport?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q2",
      "question": "What is the passenger throughput of Trenton–Mercer Airport?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q3",
      "question": "Which airport is busier, Palm Springs International Airport (with throughput {{q1}}) or Trenton–Mercer Airport (with throughput {{q2}})?",
      "dependencies": {
        "q1": "number",
        "q2": "number"
      },
      "answer_type": "place"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1161; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1161; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1161; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1161; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1161; patch=not_enabled; diagnostic=unknown.

## 12. 5ac19ff35542991316484b61

Which was published or broadcast first, The Graveyard Book of Phineas and Ferb?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "When was The Graveyard Book published?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "When was Phineas and Ferb broadcasted?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Which was published or broadcasted first, The Graveyard Book (published {{q1}}) or Phineas and Ferb (broadcasted {{q2}})?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "work"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1160; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1160; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1160; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1160; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1160; patch=not_enabled; diagnostic=unknown.

## 13. 5ab484415542990594ba9c44

Which facility was founded in Missouri, Discovery Zone or Valentino's?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "When was Discovery Zone founded?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "When was Valentino's founded?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Which facility was founded in Missouri: Discovery Zone (founded {{q1}}) or Valentino's (founded {{q2}})?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "work"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1149; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1149; patch=not_enabled; diagnostic=suspicious.

[{"code": "location_replaced_by_time", "nodes": ["q1"], "reason": "A founding date alone does not supply the requested founding location.", "evidence": {"place": "Missouri"}}, {"code": "location_replaced_by_time", "nodes": ["q2"], "reason": "A founding date alone does not supply the requested founding location.", "evidence": {"place": "Missouri"}}]

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1149; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1149; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1149; patch=not_enabled; diagnostic=unknown.

## 14. 5abbd34d5542993f40c73bc6

The Innviertel is a traditional Austrian region southeast of a river that is how many km long?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Which river is southeast of the Innviertel?",
      "dependencies": {},
      "answer_type": "other"
    },
    {
      "id": "q2",
      "question": "How long is the river southeast of the Innviertel? ({{q1}}) in kilometers?",
      "dependencies": {
        "q1": "other"
      },
      "answer_type": "number"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=suspicious.

[{"code": "direction_role_mismatch", "nodes": ["q1"], "reason": "Compass direction does not match the ordered entity pair.", "evidence": {"known_entity": "innviertel", "original_direction": "southeast", "observed_direction": "southeast", "expected_direction": "northwest", "endpoints_reversed": true}}]

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

## 15. 5abce1fa5542993a06baf993

What nationality was the lover of Lord Alfred Douglas ? 

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who was the lover of Lord Alfred Douglas?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What nationality was {{q1}}?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "place"
    }
  ],
  "final": "q2"
}
```

Variant 01: invalid; plan equal=False; raw structure equal=False; tokens=1543; patch=not_enabled; diagnostic=not_enabled.

```json
null
```

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1869; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1869; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1869; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1869; patch=not_enabled; diagnostic=unknown.

## 16. 5a77a7db5542995d8318124d

Which author was born first, Josephine Tey or Julia Peterkin?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "When was Josephine Tey born?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "When was Julia Peterkin born?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Who was born first: Josephine Tey (born {{q1}}) or Julia Peterkin (born {{q2}})?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "person"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1125; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1125; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1125; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1125; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1125; patch=not_enabled; diagnostic=unknown.

## 17. 5abe94fd55429965af743f37

Were both Sinclair Research and the Wave Mate Bullet founded in the 1970s?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "When was Sinclair Research founded?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q2",
      "question": "When was the Wave Mate Bullet founded?",
      "dependencies": {},
      "answer_type": "date"
    },
    {
      "id": "q3",
      "question": "Were both Sinclair Research (founded {{q1}}) and the Wave Mate Bullet (founded {{q2}}) founded in the 1970s?",
      "dependencies": {
        "q1": "date",
        "q2": "date"
      },
      "answer_type": "boolean"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1146; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1146; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1146; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1146; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1146; patch=not_enabled; diagnostic=unknown.

## 18. 5a7d598d5542995f4f402262

Which director was also a film editor, Burton L. King or Maheen Zia?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Did Burton L. King edit films?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q2",
      "question": "Did Maheen Zia edit films?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q3",
      "question": "Which director was also a film editor, Burton L. King ({{q1}}) or Maheen Zia ({{q2}})?",
      "dependencies": {
        "q1": "boolean",
        "q2": "boolean"
      },
      "answer_type": "person"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=False; raw structure equal=False; tokens=2181; patch=not_enabled; diagnostic=not_enabled.

```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Was Burton L. King a film editor?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q2",
      "question": "Was Maheen Zia a film editor?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q3",
      "question": "Which director was also a film editor, Burton L. King ({{q1}}) or Maheen Zia ({{q2}})?",
      "dependencies": {
        "q1": "boolean",
        "q2": "boolean"
      },
      "answer_type": "person"
    }
  ],
  "final": "q3"
}
```

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=2163; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=2163; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=2163; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=2163; patch=not_enabled; diagnostic=suspicious.

[{"code": "question_repeated_after_slot_removal", "nodes": ["q3"], "reason": "Removing the input slots leaves the original/child question unchanged; actual use of the intermediate value is unproven.", "evidence": {}}]

## 19. 5ae73ddb554299572ea5478d

Hoy Es Manana is by what Mexican Actress and singer, who is the current First Lady of Chiapas State, Mexico?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the current First Lady of Chiapas State, Mexico?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What Mexican Actress and singer is {{q1}}?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "work"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=689; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=689; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=False; raw structure equal=True; tokens=1497; patch=accepted; diagnostic=not_enabled.

```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the current First Lady of Chiapas State, Mexico?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What Mexican Actress and singer is {{q1}}?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "person"
    }
  ],
  "final": "q2"
}
```

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=689; patch=not_enabled; diagnostic=suspicious.

[{"code": "title_not_found_literally", "nodes": [], "reason": "The source title has no literal normalized occurrence in any node; aliases need manual review.", "evidence": {"title": "Hoy Es Manana"}}]

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=689; patch=not_enabled; diagnostic=unknown.

## 20. 5ade5a645542997c77adee0d

Which city is at coastal county-level, Wenling or Ruili?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Is Wenling at coastal county-level?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q2",
      "question": "Is Ruili at coastal county-level?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q3",
      "question": "Which city is at coastal county-level, Wenling (at {{q1}}) or Ruili (at {{q2}})?",
      "dependencies": {
        "q1": "boolean",
        "q2": "boolean"
      },
      "answer_type": "place"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1996; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1996; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1996; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1996; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1996; patch=not_enabled; diagnostic=unknown.

## 21. 5a87bc3f5542996432c57275

Which is located farther West, the Cascade Locks and Canal or Lake Worth Lagoon?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the longitude of Cascade Locks and Canal?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q2",
      "question": "What is the longitude of Lake Worth Lagoon?",
      "dependencies": {},
      "answer_type": "number"
    },
    {
      "id": "q3",
      "question": "Which location is farther West: Cascade Locks and Canal (longitude {{q1}}) or Lake Worth Lagoon (longitude {{q2}})?",
      "dependencies": {
        "q1": "number",
        "q2": "number"
      },
      "answer_type": "place"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=735; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=735; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=735; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=735; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=735; patch=not_enabled; diagnostic=unknown.

## 22. 5ae38b115542990afbd1e183

Who played a more important role in the church George Albert Smith or Wong Jing?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What role did George Albert Smith play in the church?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q2",
      "question": "What role did Wong Jing play in the church?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q3",
      "question": "Who played a more important role in the church: George Albert Smith (played {{q1}}) or Wong Jing (played {{q2}})?",
      "dependencies": {
        "q1": "work",
        "q2": "work"
      },
      "answer_type": "person"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1168; patch=not_enabled; diagnostic=unknown.

## 23. 5a89bf18554299669944a591

Do writers John O'Hara and Bobbie Ann Mason share the same nationality?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the nationality of John O'Hara?",
      "dependencies": {},
      "answer_type": "other"
    },
    {
      "id": "q2",
      "question": "What is the nationality of Bobbie Ann Mason?",
      "dependencies": {},
      "answer_type": "other"
    },
    {
      "id": "q3",
      "question": "Do writers John O'Hara (nationality {{q1}}) and Bobbie Ann Mason (nationality {{q2}}) share the same nationality?",
      "dependencies": {
        "q1": "other",
        "q2": "other"
      },
      "answer_type": "boolean"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1169; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1169; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1169; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1169; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1169; patch=not_enabled; diagnostic=unknown.

## 24. 5ae0a5825542993d6555ebdf

Are George Stevens and Luc Besson American cinematographers?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Is George Stevens American?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q2",
      "question": "Is Luc Besson American?",
      "dependencies": {},
      "answer_type": "boolean"
    },
    {
      "id": "q3",
      "question": "Are George Stevens and Luc Besson American cinematographers? ({{q1}} and {{q2}})",
      "dependencies": {
        "q1": "boolean",
        "q2": "boolean"
      },
      "answer_type": "boolean"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=suspicious.

[{"code": "entity_qualifier_not_established", "nodes": ["q1"], "reason": "This subject-specific branch omits part of the joint property. A negative conjunct may still suffice for no; inspect evidence.", "evidence": {"entity": "George Stevens", "required": ["American", "cinematographer"], "missing": ["cinematographer"]}}, {"code": "entity_qualifier_not_established", "nodes": ["q2"], "reason": "This subject-specific branch omits part of the joint property. A negative conjunct may still suffice for no; inspect evidence.", "evidence": {"entity": "Luc Besson", "required": ["American", "cinematographer"], "missing": ["cinematographer"]}}]

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=suspicious.

[{"code": "question_repeated_after_slot_removal", "nodes": ["q3"], "reason": "Removing the input slots leaves the original/child question unchanged; actual use of the intermediate value is unproven.", "evidence": {}}]

## 25. 5add9bfa5542990dbb2f7e85

What type of product is the sponsor of the Premiership Rugby Sevens SeriesSeries ? 

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the sponsor of the Premiership Rugby Sevens Series?",
      "dependencies": {},
      "answer_type": "organization"
    },
    {
      "id": "q2",
      "question": "What type of product does {{q1}} produce?",
      "dependencies": {
        "q1": "organization"
      },
      "answer_type": "work"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1083; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1083; patch=not_enabled; diagnostic=suspicious.

[{"code": "identity_replaced_by_production", "nodes": ["q2"], "reason": "An organizational input is asked what it produces instead of what type of product it is.", "evidence": {"original_relation": "is", "observed": "What type of product does {{q1}} produce?"}}]

Variant 03: valid; plan equal=False; raw structure equal=False; tokens=1080; patch=not_needed; diagnostic=not_enabled.

```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the sponsor of the Premiership Rugby Sevens Series?",
      "dependencies": {},
      "answer_type": "organization"
    },
    {
      "id": "q2",
      "question": "What type of product does {{q1}} produce?",
      "dependencies": {
        "q1": "organization"
      },
      "answer_type": "other"
    }
  ],
  "final": "q2"
}
```

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1083; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1083; patch=not_enabled; diagnostic=unknown.

## 26. 5a75a0725542992d0ec05fc9

Disorganized Crime included what cast member best known for playing Al Bundy on the Fox Network sitcom "Married... with Children"?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What cast member of Disorganized Crime is best known for playing Al Bundy on the Fox Network sitcom 'Married... with Children'?",
      "dependencies": {},
      "answer_type": "person"
    }
  ],
  "final": "q1"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1061; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1061; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1061; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1061; patch=not_enabled; diagnostic=no_violation_found.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1061; patch=not_enabled; diagnostic=unknown.

## 27. 5ac43e0f554299076e296d8e

What country are both Dafeng District and Jixi in?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What country is Dafeng District in?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q2",
      "question": "What country is Jixi in?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q3",
      "question": "What country are both Dafeng District (in {{q1}}) and Jixi (in {{q2}}) in?",
      "dependencies": {
        "q1": "place",
        "q2": "place"
      },
      "answer_type": "place"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=unknown.

## 28. 5a8ea7f25542995085b37468

Are The Limousines and Faith No More from the same state?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What state is The Limousines from?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q2",
      "question": "What state is Faith No More from?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q3",
      "question": "Are The Limousines and Faith No More from the same state: {{q1}} = {{q2}}?",
      "dependencies": {
        "q1": "place",
        "q2": "place"
      },
      "answer_type": "boolean"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1123; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1123; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1123; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1123; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1123; patch=not_enabled; diagnostic=suspicious.

[{"code": "question_repeated_after_slot_removal", "nodes": ["q3"], "reason": "Removing the input slots leaves the original/child question unchanged; actual use of the intermediate value is unproven.", "evidence": {}}]

## 29. 5a8701b3554299211dda2b9a

Werner Christie served under the politician who was also Director-General of what other organization?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who was the politician that Werner Christie served under?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What organization was the politician ({{q1}}) also the Director-General of?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "organization"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1085; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1085; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1085; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1085; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1085; patch=not_enabled; diagnostic=unknown.

## 30. 5ac3dfee554299204fd21eab

The man known as the voice of "Elgar" voices the English character in what Manga inspired by Keitaro Arima?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the voice actor of Elgar?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What manga is inspired by Keitaro Arima and features the English character voiced by {{q1}}?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "work"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1113; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1113; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1113; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1113; patch=not_enabled; diagnostic=no_violation_found.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1113; patch=not_enabled; diagnostic=unknown.

## 31. 5a7f7b3b5542992097ad2f81

Which restaurant chain's headquarters is further north, Pizza Inn or Papa Gino's?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the headquarters location of Pizza Inn?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q2",
      "question": "What is the headquarters location of Papa Gino's?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q3",
      "question": "Which restaurant chain's headquarters is further north, Pizza Inn (located at {{q1}}) or Papa Gino's (located at {{q2}})?",
      "dependencies": {
        "q1": "place",
        "q2": "place"
      },
      "answer_type": "work"
    }
  ],
  "final": "q3"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1167; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1167; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1167; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1167; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1167; patch=not_enabled; diagnostic=unknown.

## 32. 5ae3d2715542990afbd1e1e9

Are Control Room and Meeting Resistance both documentary films that involve Iraq?

Original max4 plan:
```json
null
```

Variant 01: invalid; plan equal=True; raw structure equal=False; tokens=1663; patch=not_enabled; diagnostic=not_enabled.

Variant 02: invalid; plan equal=True; raw structure equal=True; tokens=1673; patch=not_enabled; diagnostic=unknown.

Variant 03: invalid; plan equal=True; raw structure equal=True; tokens=1673; patch=not_enabled; diagnostic=not_enabled.

Variant 04: invalid; plan equal=True; raw structure equal=True; tokens=1673; patch=not_enabled; diagnostic=unknown.

Variant 05: invalid; plan equal=True; raw structure equal=True; tokens=1673; patch=not_enabled; diagnostic=unknown.

## 33. 5ae077735542993d6555eb6d

What type of sprite did Milada Šubrtová portray in Antonín Dvořák's reknowned opera?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What type of sprite did Milada Šubrtová portray?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q2",
      "question": "In which opera did {{q1}} appear?",
      "dependencies": {
        "q1": "work"
      },
      "answer_type": "work"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=False; raw structure equal=False; tokens=1141; patch=not_needed; diagnostic=not_enabled.

```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "In which opera by Antonín Dvořák did Milada Šubrtová portray a sprite?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q2",
      "question": "What type of sprite did Milada Šubrtová portray in {{q1}}?",
      "dependencies": {
        "q1": "work"
      },
      "answer_type": "other"
    }
  ],
  "final": "q2"
}
```

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1107; patch=not_enabled; diagnostic=unknown.

## 34. 5adf4b335542993a75d264a5

Paul DeBoy is known for an appearance in the Western action-adventure game developed by which company?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What is the name of the Western action-adventure game Paul DeBoy appeared in?",
      "dependencies": {},
      "answer_type": "work"
    },
    {
      "id": "q2",
      "question": "Which company developed {{q1}}?",
      "dependencies": {
        "q1": "work"
      },
      "answer_type": "organization"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1089; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1089; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1089; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1089; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1089; patch=not_enabled; diagnostic=unknown.

## 35. 5a776b82554299373536026f

What is the official currency in the country that hosts the Asahi-Ryokuken Yomiuri Memorial tournament?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Which country hosts the Asahi-Ryokuken Yomiuri Memorial tournament?",
      "dependencies": {},
      "answer_type": "place"
    },
    {
      "id": "q2",
      "question": "What is the official currency in {{q1}}?",
      "dependencies": {
        "q1": "place"
      },
      "answer_type": "other"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1916; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1916; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1916; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1916; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1916; patch=not_enabled; diagnostic=unknown.

## 36. 5ac0b1835542992a796ded65

Bordan Tkachuk was the former CEO of which company, which provides IT products?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "What company was Bordan Tkachuk the former CEO of?",
      "dependencies": {},
      "answer_type": "organization"
    },
    {
      "id": "q2",
      "question": "Does {{q1}} provide IT products?",
      "dependencies": {
        "q1": "organization"
      },
      "answer_type": "boolean"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=679; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=679; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=rejected; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=679; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=679; patch=not_enabled; diagnostic=unknown.

## 37. 5a80afcf554299485f5986b9

Who else beside the  American university administrator and politician from the state of Oklahoma was part of the  Boren-McCurdy proposals?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who were the American university administrators and politicians from Oklahoma involved in the Boren-Mcurdy proposals?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "Who else besides {{q1}} was part of the Boren-Mcurdy proposals?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "person"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=suspicious.

[{"code": "excluded_single_person_became_group", "nodes": ["q1"], "reason": "A singular excluded-person description became a plural lookup.", "evidence": {"descriptor": "american university administrator and politician from the state of oklahoma"}}]

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1130; patch=not_enabled; diagnostic=unknown.

## 38. 5ae254565542992decbdccbb

In what year was the writer of the drama "Ingenious" born?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who wrote the drama \"Ingenious\"?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "In what year was {{q1}} born?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "date"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=not_needed; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=not_enabled; diagnostic=no_violation_found.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=1069; patch=not_enabled; diagnostic=unknown.

## 39. 5ae14b0655429920d52343a6

Bangalore Naatkal starred which actor and photographer?

Original max4 plan:
```json
null
```

Variant 01: invalid; plan equal=True; raw structure equal=True; tokens=1418; patch=not_enabled; diagnostic=not_enabled.

Variant 02: invalid; plan equal=True; raw structure equal=True; tokens=1418; patch=not_enabled; diagnostic=unknown.

Variant 03: invalid; plan equal=True; raw structure equal=True; tokens=1418; patch=not_enabled; diagnostic=not_enabled.

Variant 04: invalid; plan equal=True; raw structure equal=True; tokens=1418; patch=not_enabled; diagnostic=unknown.

Variant 05: invalid; plan equal=True; raw structure equal=True; tokens=1418; patch=not_enabled; diagnostic=unknown.

## 40. 5ae409d955429970de88d89d

Greetings! We're The Monitors was the debut album by the band who had what soul and R&B singer as their lead?

Original max4 plan:
```json
{
  "nodes": [
    {
      "id": "q1",
      "question": "Who is the lead singer of the band that released 'Greetings! We're The Monitors'?",
      "dependencies": {},
      "answer_type": "person"
    },
    {
      "id": "q2",
      "question": "What soul and R&B singer is {{q1}}?",
      "dependencies": {
        "q1": "person"
      },
      "answer_type": "work"
    }
  ],
  "final": "q2"
}
```

Variant 01: valid; plan equal=True; raw structure equal=True; tokens=696; patch=not_enabled; diagnostic=not_enabled.

Variant 02: valid; plan equal=True; raw structure equal=True; tokens=696; patch=not_enabled; diagnostic=unknown.

Variant 03: valid; plan equal=True; raw structure equal=True; tokens=1115; patch=rejected; diagnostic=not_enabled.

Variant 04: valid; plan equal=True; raw structure equal=True; tokens=696; patch=not_enabled; diagnostic=unknown.

Variant 05: valid; plan equal=True; raw structure equal=True; tokens=696; patch=not_enabled; diagnostic=unknown.
