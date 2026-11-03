# Synthetic documents for the 2026-10-02 pipeline run (BLK-5)

Invented people, employer, lab and clinic. The ID cards are plain data cards:
no emblem, issuer branding or security features. Nothing is stamped "ficticio",
because the extraction agent treats a stamp like that as tampering and blocks
scoring (the 2026-09-13 run). Regenerate with `python make_fixtures.py`.

Each PDF is signed and carries its invented issuer's round stamp. Until
2026-11-03 the signature lines were blank, and Sonnet 5.5 flagged the
constancia for it ("no se observa firma ni sello de la empresa"), so it no
longer counted as a required document.

Upload one file at a time: a multi-file drop gives every file the same type.

## seguros — Seguro de Vida, Plan Estándar

| Client | Karla Beatriz Hernández Quintanilla, DUI 05392718-8, born 1989-07-23 |
| --- | --- |
| Form | `date_of_birth` 1989-07-23 · `monthly_income` 2400 · `coverage_amount` 30000 |
| `national_id` | `seguros/dui-karla-hernandez.png` |
| `proof_of_income` | `seguros/constancia-salario-karla-hernandez.pdf`, issued 2026-09-28; meets the 90-day limit until 2026-12-27 |

Expected: every rule passes. `base_income_score` = min(2400/3000, 1) × 100 = 80,
and the final score is 0.7 × 80 + 0.3 × the AI score, so tier B ("Estándar")
unless the AI score is very high. For demo beat 6, changing 3000 to 2500 moves
the rule to 96 and the case toward tier A.

## medico — Afiliación Médica, Plan Individual

| Client | José Alberto Menjívar Portillo, DUI 03871264-9, born 1984-11-02 |
| --- | --- |
| Form | `date_of_birth` 1984-11-02 · `bmi` 27.4 · `smoker` "No" (as staff would type it) · `dependents` 2 |
| `national_id` | `medico/dui-jose-menjivar.png` |
| `lab_results` | `medico/resultados-laboratorio-jose-menjivar.pdf`, issued 2026-09-23, fasting glucose 98 mg/dL |
| `medical_report` | `medico/informe-medico-jose-menjivar.pdf`, dated 2026-08-30, one chronic condition, non-smoker |

Expected if the form were typed correctly: every rule passes; rules score
41.25 + 29.63 = 70.9. The form stores `smoker` as text, so
`applicant.smoker == false` probably flags him as a smoker (-10). This run is
meant to confirm or refute that.
