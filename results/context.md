| Test | Setup | Effort | Prompt tokens | All 16 (per run) | 13 clean (per run) | Empty | Time |
|---|---|---|---|---|---|---|---|
| rag | bm25 top-50 | low | 4,818 per question | 15 · 15 · 15 | 13 · 13 · 13 | 0 of 3 | 19 s |
| rag | dense top-100 | low | 9,486 per question | 15 · 14 · 15 | 13 · 13 · 13 | 0 of 3 | 20 s |
| rag | dense top-20 | low | 2,017 per question | 11 · 11 · 11 | 10 · 10 · 10 | 0 of 3 | 19 s |
| rag-retro | bm25 top-100 | low | 9,746 | 2/6 · 1/6 · 2/6 loops | – | – | 8 s |
| rag-retro | bm25 top-300 | low | 29,193 | 2/6 · 2/6 · 2/6 loops | – | – | 14 s |
| rag-retro | dense top-100 | low | 9,819 | 1/6 · 2/6 · 2/6 loops | – | – | 9 s |
| rag-retro | dense top-300 | low | 28,285 | 2/6 · 2/6 · 2/6 loops | – | – | 8 s |
| size | 314 capsules | low | 29,683 | 16 · 16 · 16 | 13 · 13 · 13 | 0 of 3 | 6 s |
| size | 314 capsules | medium | 29,684 | 16 · 16 · 16 | 13 · 13 · 13 | 0 of 3 | 8 s |
| size | 634 capsules | low | 59,338 | 16 · 16 · 16 | 13 · 13 · 13 | 0 of 3 | 9 s |
| size | 634 capsules | medium | 59,339 | 16 · 16 · 16 | 13 · 13 · 13 | 0 of 3 | 7 s |
| size | 1274 capsules | low | 119,213 | 15 · 16 · 15 | 13 · 13 · 13 | 0 of 3 | 16 s |
| size | 1274 capsules | medium | 119,214 | 15 · 15 · 15 | 13 · 13 · 13 | 0 of 3 | 19 s |
| size | 2554 capsules | low | 239,305 | – · 13 · 15 | – · 11 · 13 | 1 of 3 | 46 s |
| size | 2554 capsules | medium | 239,306 | 15 · 15 · 15 | 13 · 13 · 13 | 0 of 3 | 35 s |

Wrong answers:

- `driving_tests`: 1274 capsules/low: '4'; 1274 capsules/low: '4'; 1274 capsules/medium: '4'; 1274 capsules/medium: '4'; 1274 capsules/medium: '4'; 2554 capsules/low: '5'; 2554 capsules/low: '6'; 2554 capsules/medium: '5'; 2554 capsules/medium: '6'; 2554 capsules/medium: '6'; dense top-20/low: '6'; dense top-20/low: '6'; dense top-20/low: '6'; dense top-100/low: '9'; dense top-100/low: '9'; dense top-100/low: '9'; bm25 top-50/low: '11'; bm25 top-50/low: '10'; bm25 top-50/low: '12'
- `asa_branca_year`: 2554 capsules/low: '2026'; dense top-20/low: '2026'; dense top-20/low: '2026'; dense top-20/low: '2026'
- `asa_branca_late`: 2554 capsules/low: '12'
- `parrot_man_name`: dense top-20/low: 'unknown'; dense top-20/low: 'unknown'; dense top-20/low: 'unknown'
- `parrot_man_age`: dense top-20/low: 'unknown'; dense top-20/low: 'unknown'; dense top-20/low: 'unknown'
- `first_lemon_date`: dense top-20/low: 'unknown'; dense top-20/low: 'unknown'; dense top-20/low: 'unknown'
- `lemon_years`: dense top-100/low: '11'
