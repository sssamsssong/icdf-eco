# Demo screen screenshots (English, 1920x1080)

For presentation slides. Same data as the actual demo (`icdf 1/2/3`), captured at the chosen moment.
Numbers include the change cost of 4.5 g per plan change.

| File | Scene | Key point |
|---|---|---|
| `1_시나리오1_시작전_하루전계획.png` | Scenario 1, before start | Day-ahead forecast (dashed line) and the day-ahead plan for both racks. Both start from the same 12 jobs |
| `2_시나리오1_구름중_YAX가_미룸.png` | Scenario 1, 05:30 under cloud | Forecast error +176 → AI predicts +145 even 4 hours later → **Defer** (19 g > 10 g). Google runs in the cloud, YAX leaves the slot empty and moves it to evening |
| `3_시나리오1_하루끝_결과.png` | Scenario 1, end of day | Google 1,521 g vs **YAX 1,285 g (−15.5%)**. Slots run in cloud: 9 vs 3, YAX changed 6 times |
| `4_시나리오2_짧은구름_유지.png` | Scenario 2, 10:30 short cloud | Error +176 but gain is 7.4 g ≤ 10 g → **Keep**. Doesn't flip the plan for every cloud |
| `5_시나리오2_하루끝_결과.png` | Scenario 2, end of day | 5 clouds, **only 1 change**, Google 1,326 g vs YAX 1,293 g (−2.5%) |
| `6_시나리오3_3일째_구름판_예시.png` | Scenario 3, 10:00 on day 3 | 5 days in a row, judges place the cloud board themselves. The cloud in this image is an example (05:00–10:30). Cumulative is the total through day 3 |

How it was made: the GUI (`gui/index.html`) was rendered as a static frame with the scheduler state at that moment and captured in headless Firefox.
