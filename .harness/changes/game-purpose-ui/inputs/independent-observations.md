# Independent screen observations before design inspection

Reviewer context: `/root/ui_review`. Original request and discovery/source-review/README were read first. Final receipt screenshots were inspected before design expectations. Independent Chromium CDP run used `http://127.0.0.1:4173/`; browser actions and states are in `independent-browser.json`. No product file was changed.

The screen communicates one spending group, with total, editable target, difference, reroll and two purchase groups. The separate research area has two independent counts and remaining limits. Prices and discount badges align with their count, and labels remain visible. Reset reads 「回数をリセット」, which fits the observed target preservation. The brief research constraint 「研究・4 / 難易度8以上」 reads as a compact applicability datum on the research object, not an explanatory sentence.

The 1280px screen is compact without enlarged decorative controls. The 320px layout uses rows instead of shrinking the entire interface. A small plus/minus mark remains centered within a larger real button. The normal 320px receipt is shorter than the prior 1249px screen described in discovery. The observed price units, badges, and research remainder text are small but individually readable at their normal screenshots. The study count inputs are wider than purchase count inputs, which makes independent count entry discoverable.

Independent real mouse hits incremented then decremented all nine counters and direct keyboard entry wrote 3 to each. Input target −1 was rejected. Target clear produced 「目標未設定」. Target 1 with all spending counts at 3 showed a negative difference rather than a balance. Reset cleared all nine counts, retained target 500, and the same state survived reload.

At 320×400 and 1280×400 there is no sticky summary. Bottom research inputs are reachable by scroll. At 390×720 a sticky summary remains within the spending container and exits before research, so the bottom research input and focus are visible. The independent 640×400 / DSF2 check edits the target and reflows within width; this is a reflow equivalent, not real browser UI zoom.

Error and storage receipt screenshots show short state/error labels without recovery prose. There is no Q&A or tooltip in the independent DOM inspection. Accessible wording names exact count, price/discount, and increase/decrease action. There is no hidden relocated explanatory sentence in those observed surfaces. This observation precedes the full per-state inventory and source review.

Initial concern to verify against code and metrics: very long count values must scroll inside the input rather than widen mobile rows; sticky behavior must release above research. Final review must not infer full WCAG, Windows, or native zoom coverage from these observations.

## Final comparison and review resolution

The final rerun is `ae7aa0d8a70e41da9cd9c9ec06d58be2`. Its 320px and 1280px screenshots were re-observed. Both metric files are byte-identical to the original successful receipt. The three research constraint source references now point to the saved source-review sentence that actually contains research 4 and difficulty 8. This fixes the one concrete review finding without changing the product or observed UI.

A 390px Tab sweep with simulated storage failure at heights 600 and 720 exercised 33 focus steps per viewport and found no input/button center obstructed by the sticky summary. The separate `independent-focus-sweep.json` contains each actual focus/hit record.

Independent `npm test` passed all 10 model tests; `npm run test:site` passed all 10 public-boundary tests; `npm run check:pages` confirmed the four approved public assets and empty marker. The full harness receipt has all 305 UI cases passing. The provider was read and records browser measurements and real input results, not values copied from design expectations.

Comment-scan subagent `/root/ui_review/comment_scan` reviewed the three changed provider comment blocks and found no misleading or unsafe comments, with zero file changes. The substantive source/flow review was performed by this reviewer.

`git ls-remote origin HEAD refs/heads/main` returned `273e4a38abc85db90c0c3065746f98f211d3f07a`. That commit is the direct parent of the change base `cdbe786f654fd00a6e4c0124aa8286165c183abf`, which contains the already-saved harness update. The remote did not advance past the reviewed work.
