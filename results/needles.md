| Test | Life | Capsules | Prompt tokens | Effort | Runs | Result | Time |
|---|---|---|---|---|---|---|---|
| qa | none | 0 | 470 | low | 1 | 0/16 | 3 s |
| qa | skeleton | 74 | 7,803 | low | 3 | 16/16 · 16/16 · 16/16 | 4 s |
| qa | long | 5112 | 479,712 | low | 3 | 15/16 · 15/16 · 14/16 | 18 s |
| qa | long | 5112 | 479,713 | medium | 3 | 13/16 · 15/16 · 13/16 | 28 s |
| retrospective | skeleton | 74 | 7,752 | medium | 3 | 5/6 · 4/6 · 4/6 loops; 0 of 223 cited dates not found; 0 empty (thought until the limit) | 20 s |
| retrospective | long | 5112 | 479,660 | low | 5 | 6/6 · 4/6 · 3/6 · 4/6 · 3/6 loops; 4 of 375 cited dates not found; 0 empty (thought until the limit) | 15 s |
| retrospective | long | 5112 | 479,661 | medium | 3 | 3/6 · 3/6 · empty loops; 2 of 130 cited dates not found; 1 empty (thought until the limit) | 37 s |

Wrong answers:

- `driving_tests`: long/low: '9'; long/low: '9'; long/low: '9'; long/medium: 'unknown'; long/medium: '9'; long/medium: '9'
- `lemon_years`: long/low: '11'; long/medium: '12'; long/medium: '11'
- `first_lemon_date`: long/medium: '2026-07-09'
- `swim_meters`: long/medium: 'unknown'
