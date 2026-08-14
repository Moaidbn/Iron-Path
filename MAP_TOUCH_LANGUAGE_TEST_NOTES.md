# Map touch and language test notes

## Browser test
- Environment: local Flask game at http://127.0.0.1:5011/
- Map overlay opened successfully with all 56 atlas locations rendered.
- Synthetic touch pointer sequence (`pointerType: touch`) on `#atlas-stage` moved the map from `translate(0px, 0px) scale(1)` to `translate(118px, 64px) scale(1)`.
- Computed `touch-action` for `#atlas-stage` is `none`.
- Zoom-in changed the transform to `scale(1.2)` and reset returned it to `translate(0px, 0px) scale(1)`.
- English language state: `dir=ltr`, title `Atlas of Aldenmere`, filters `All/Cities/Fortresses/Ports/Known/New`, count `56 of 56 locations in the atlas`.
- Arabic language state: `dir=rtl`, title `أطلس قارة ألدينمير`, filters `الكل/مدن/قلاع/مرافئ/المعروف/مستجد`, count `56 من 56 موضعًا في الأطلس`.
- Switching language while the map overlay remained open reloaded the atlas data and preserved the open state.
- No browser-console errors were observed in these interaction runs.

## Scope note
The current touch handler supports one-finger pan and native touch scrolling is disabled on the map stage. Multi-touch pinch zoom has not yet been added or certified; it is a candidate enhancement if required by the touch test plan.

## Reload finding

The first pinch attempt after editing was served by an old Flask process: the browser HTML did not contain `atlasPointDistance` or `atlasPointers` and still contained the old `e.isPrimary === false` guard. The server was restarted on port 5011, and the atlas was reopened from the fresh process before continuing validation.

## Multi-touch result after server reload

The fresh HTML contained the new multi-touch code, did not contain the old primary-pointer guard, and retained `touch-action: none`. A two-pointer touch simulation changed the map from `translate(0px, 0px) scale(1)` to `translate(75px, 0px) scale(1.75)`. After lifting one pointer, the remaining pointer continued to pan the map to `translate(135px, 40px) scale(1.75)`. The pan state released cleanly and the reset control returned the map to `translate(0px, 0px) scale(1)`.

## Character directory UI verification — 2026-08-13

- The new **Characters** tab loaded successfully from `/characters-data?lang=en` with 34 records; the filter showed 34 all characters, 15 lords, and 9 companions.
- English cards displayed localized names, titles, biographies, agendas, current locations, availability badges, and existing portrait assets without broken image paths.
- The language toggle returned the Hall to its main page state in this browser run, so the Arabic character view will be verified after reopening the Hall; this did not affect the API or the English character load.

## Character directory Arabic verification — 2026-08-13
- `/characters-data?lang=ar` and `/characters-data?lang=en` both returned HTTP 200 with 34 records; unsupported `lang=fr` returned HTTP 400.
- The Arabic character directory rendered localized names, locations, roles, reasons, statuses, and responsive cards with available portrait assets.
- The Lords filter was present with the expected 15-lord count; the full directory showed 34 records.
- Added Arabic/English labels for Morale, Trust, and Respect so raw metric keys do not appear in the Arabic interface.
- The records hall remained scrollable and usable in the tested viewport.

## Character directory DOM audit — 2026-08-13
The actual `.character-directory-grid` container contains 34 rendered cards. The Arabic filter options are `كل الشخصيات (34)`, `اللوردات (15)`, and `المرافقون (9)`, and the character-directory toolbar and grid are present in the DOM. The earlier zero-card query used an incorrect ID selector; the grid intentionally has a class without that ID. This was a selector issue in the audit, not a UI rendering failure.

## Final morale localization diagnosis and fix — 2026-08-13
A direct DOM audit of `.character-directory-grid` found 34 cards, with 10 companion cards showing raw `morale`; the live `t('morale')` value was also `morale`, while `t('loyalty')` was `الولاء`. The root cause was confirmed: the server-side `UI` dictionary returned by `/localization-data` lacked `morale`, and the template translation lookup allowed an incomplete API dictionary to take precedence over static strings. Fixed by adding `loyalty`, `morale`, `trust`, and `respect` to both server language dictionaries and making `t()` accept API values only when defined and non-empty, then fall back safely to the current static language. After restart, `/localization-data?lang=ar` returns `morale: المعنويات`; `/localization-data?lang=en` returns `morale: Morale`; `/characters-data?lang=ar` returns 34 characters and 10 retainers.

## Post-restart UI reload — 2026-08-13
The refreshed Flask page loaded successfully from port 5011 in Arabic, and the Hall of Records opened normally. The Hall exposes the localized `الشخصيات` tab alongside the existing tabs; no startup or navigation failure was observed.

## Final Arabic character-directory verification — 2026-08-13
The refreshed Arabic directory rendered 34 cards, with filter options `كل الشخصيات (34)`, `اللوردات (15)`, and `المرافقون (9)`. All 10 retainer cards rendered `المعنويات` and no card contained raw `morale`, `trust`, `respect`, `status`, `currentLocation`, or `assignment` keys. The page direction remained RTL, and `t('morale')` returned `المعنويات`.

## English switch verification — 2026-08-13
The language transition completed with `document.documentElement.lang = en`, `dir = ltr`, and `t('morale') = Morale`. The Hall content was temporarily cleared during the asynchronous refresh, so the Hall was reopened for the final English card audit.

## Final English character-directory verification — 2026-08-13
The English directory rendered 34 cards with `All characters (34)`, `Lords (15)`, and `Companions (9)`. All 10 retainer cards rendered `Loyalty` and `Morale`, with `lang=en` and `dir=ltr`; `t('morale')` returned `Morale`. The raw-key scan was interpreted against the English vocabulary: the visible words `Morale`, `Trust`, and `Status` are the intended translated labels, while no camelCase implementation keys were displayed.

## New mouse interaction report — 2026-08-13
A fresh live page load on port 5011 opened the English atlas with the SVG map, zoom controls, 56 locations, and the navigation hint visible. The issue was reproduced by the user report but had not yet been reproduced by a controlled event probe; the next step is to verify the actual pointer and wheel event path on `#atlas-stage`.

## Live event-path diagnosis — 2026-08-13
On the live atlas, `#atlas-stage` computed as `pointer-events:auto`, `overflow:hidden`, and `touch-action:none`. A controlled mouse pointer sequence changed the SVG transform from `translate(0px, 0px) scale(1)` to `translate(96px, 54px) scale(1)`, and a wheel event was prevented and changed the scale to `1.14`. No JavaScript errors were present in the console. This proves the existing handler path is active; an additional browser-compatible fallback and clearer interaction affordances will be added to protect against environments where native pointer delivery is inconsistent.

## Mouse interaction patch deployed — 2026-08-13
The live server was restarted successfully after the patch. The atlas reopened with 56 locations, visible zoom controls, and the updated instruction `Drag anywhere to pan · Use the mouse wheel to zoom`. Map pins now participate in drag-start rather than being excluded, while the control strip remains excluded so its buttons stay clickable. A legacy mouse-event fallback was added for browsers without Pointer Events.

## Live sandbox reproduction — 2026-08-13
The atlas was reopened in the sandbox browser at `http://127.0.0.1:5011/`. The live DOM confirms that the map is currently a large JPG (`/static/assets/aldenmere_world_map.jpg`, native size `2560×1440`) embedded inside an SVG, with location markers in a separate `#map-pins` layer. The stage is `1262×710`, has `overflow:hidden`, `touch-action:none`, and `pointer-events:auto`; the SVG transform is initially the identity matrix. This confirms the current experience is still image-centric and explains why visual dragging can feel unreliable even though the event layer exists.

## Post-patch interaction verification — 2026-08-13
A controlled drag beginning on a `.map-pin` moved the map to `translate(84px, 47px) scale(1)` and entered the `is-panning` state, then released cleanly. The wheel handler prevented the default page scroll and changed the readout to `114%`; the zoom-in button reached `134%`, zoom-out returned to `114%`, and reset returned to `translate(0px, 0px) scale(1)` with a `100%` readout. The navigation hint displayed the updated wording. No console errors were emitted.

A two-pointer pinch probe expanded the scale to `195%` and preserved translation, then reset returned the view to `100%`. A pointer event originating in the control strip did not start a pan, confirming that `+`, `−`, and `Reset` remain independently usable.

## Vector atlas prototype — 2026-08-13
A vector-first atlas prototype is now live in the sandbox browser. The default layer is `#map-vector-art`, while the existing JPG is retained as an optional fallback behind the `Illustrated`/`Vector` style button. A controlled browser test confirmed: vector mode renders with the raster layer hidden; clicking the style button switches to raster mode with the raster layer visible and vector layer hidden, then switches back; a wheel event changes the view to `114%`; pointer drag changes the transform to `translate(96px, 52px) scale(1.14)`; Reset returns to `translate(0px, 0px) scale(1)` and `100%`. No JavaScript errors were reported in the probe.

A two-pointer touch probe on the vector-first atlas reached the configured maximum `280%` scale and then Reset returned the map to `100%` with identity translation. This confirms the new rendering layer does not interfere with the existing pointer/pinch interaction path.

## Original raster map restored — 2026-08-13
The vector prototype was visually rejected because it did not preserve the supplied map artwork. The atlas now defaults to the original `/static/assets/aldenmere_world_map.jpg` inside the same transformed SVG interaction surface; the vector layer is hidden by default and remains only as an optional style fallback. Browser verification reported raster display `block`, vector display `none`, asset HEAD status `200`, wheel zoom to `114%`, pointer drag to `translate(120px, 64px) scale(1.14)`, and Reset to `translate(0px, 0px) scale(1)`. Toggling to the optional vector mode and back restored raster mode successfully, with the final button label `Vector` indicating the available alternate style.

## Final original-image interaction check — 2026-08-13
After removing the experimental style toggle, the live atlas exposes only zoom-in, zoom-out, and reset controls. The original `/static/assets/aldenmere_world_map.jpg` is displayed (`rasterDisplay: block`), the vector artwork is hidden (`vectorDisplay: none`), and the style toggle is absent. Wheel zoom reached `114%`; pointer drag reached `translate(140px, 70px) scale(1.14)`; Reset returned to `translate(0px, 0px) scale(1)` and `100%`. No campaign database was touched.

## Narrative language pass-through verification — 2026-08-13
The live English page reported `currentLanguage: en`, and the `submitAction` source includes `language: currentLanguage` in the JSON body sent to `/play`. This confirms the selected UI language reaches the local narrative engine.

A server-side language matrix then passed for Arabic plus English explore, diplomacy, combat, trade, rest, intrigue, default action, and recap; the campaign database was restored after the test.

## Live English narrative verification — 2026-08-13
From the live English page, `submitAction` sent `language: en` to `/play`. A live `explore the harbor` request returned fully English narrative text. A second live `negotiate with the captain` request returned English narrative with `hasArabic: false`; the response named Captain Nader in English. These test turns were temporary and the campaign database was restored afterward by the isolated language-matrix test procedure.

## NVIDIA Nemotron Game Master verification — 2026-08-13

A new `nvidia_gm.py` layer integrates the NVIDIA NIM chat endpoint with the model `nvidia/nemotron-3-super-120b-a12b` while retaining `offline_engine.py` as the sole authority for state, economy, locations, attendance, and time. A local mock NIM server verified model selection, trusted-context system messaging, and `chat_template_kwargs.enable_thinking=false`.

The mock accepted Arabic and English engine turns and returned valid language-matched narrative. A deliberate Arabic response to an English request was rejected by the language guard and replaced with local English narration. A simulated unavailable endpoint also retained playable local narration and set the narrator state to `unavailable`. The campaign database was backed up before hybrid-engine testing and restored after it completed.

Configuration was verified without any real key: an ephemeral environment key exposed `/health` as `engine=nvidia-nemotron` and `narration_status=ready`; restarting without it returned `engine=local` and `narration_status=not-configured`. No NVIDIA key was written to the project, campaign database, or test record.
