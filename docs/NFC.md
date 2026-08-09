# NFC production and handoff guide

This collection is designed around a round, peel-and-stick 25 mm NFC tag on a
flat printed landing. The tag, printed TAP overlay, and clear overlaminate are
separate layers. None of the printed models contains an NFC chip by itself.

The production URL for every current design is:

`https://raddadband.com/tap/`

Use a Rad Dad-controlled HTTPS redirect rather than encoding a streaming-service
URL directly. A redirect can be updated later without replacing a locked tag.
Do not encode a route that is planned but not yet deployed and tested.

## 1. Select the 25 mm tag

Use a genuine 25 mm round NFC Forum Type 2 sticker based on NXP NTAG213 or an
equivalent standards-compliant chip. NTAG213 has ample capacity for one short
HTTPS URI and is the preferred starting point for this project.

| Requirement | Production requirement |
| --- | --- |
| Form | Round peel-and-stick sticker, nominally 25 mm diameter |
| Chip | NTAG213 preferred; NTAG215 or NTAG216 is acceptable but unnecessary for one URI |
| Radio type | NFC Forum Type 2 / ISO/IEC 14443 Type A |
| Surface | Intended for plastic or another nonmetal surface |
| Backing | Plain adhesive, not an on-metal or ferrite-backed construction |
| Face material | Paper, PET, or nonmetal vinyl |
| Encoding | User-writable NDEF and optionally permanent read-only lockable |
| Documentation | Manufacturer, seller, SKU, lot, stated chip, dimensions, and thickness recorded |

The sticker diameter alone does not describe its RF performance. Ask for the
antenna or inlay diameter when the vendor provides it, and qualify a small lot
before buying production quantities. Reject tags that arrive with inconsistent
UID reads, cannot retain an NDEF record, or scan substantially worse than the
qualified sample.

Do not use metal-backed tags, foil labels, metallic ink, conductive laminate,
magnets behind the tag, or an overlay marketed as chrome, holographic, or
metalized. Metal close to the antenna can detune or block the tag.

An NFC UID is an identifier, not a secure credential. These products must not
be used as access badges, payment devices, identity documents, emergency
records, or storage for passwords or private information.

## 2. Program before installation

Never install an untested blank tag. Program and test each tag while it is still
on its carrier sheet, where replacement is easy.

1. Create one NDEF URI record containing exactly `https://raddadband.com/tap/`.
2. Read the tag back in the programming application and inspect the complete URI.
3. Tap the tag with an unlocked iPhone and confirm that the expected HTTPS URL is offered.
4. Tap the tag with an unlocked Android phone and confirm the same behavior.
5. Repeat ten consecutive reads on each phone before installation.
6. Reject a tag that misses, reports an unexpected record, changes its value, or opens the wrong destination.
7. Record the tag lot, programming date, operator, URL, phone models, operating-system versions, and results.
8. Decide whether to leave the tag writable or make it permanently read-only.
9. If locking, perform one final read-back immediately before the irreversible lock command.
10. Read the locked tag again on both phone families and record the result.

### Lock decision

| Choice | Advantage | Risk | Recommended use |
| --- | --- | --- | --- |
| Leave writable | The physical tag can be reprogrammed | Anyone with a writer could change it | Prototypes, internal samples, or URLs that are not final |
| Permanently lock read-only | Prevents ordinary rewriting or casual tampering | A wrong or obsolete encoded URL requires replacing the tag | Production units only after the redirect and tag have passed testing |

The preferred production strategy is to encode the stable Rad Dad redirect and
then lock the tag only after final read-back. The redirect destination can be
changed server-side while the physical NDEF record remains correct. A password
feature is not a substitute for a documented read-only decision, and forgotten
passwords can create an unnecessary service problem.

Locking is irreversible. Never lock a batch based only on what the programming
screen says; verify the record by reading it from at least two phones first.

## 3. Install on the printed landing

Use the flat 25 mm landing assigned to each product:

| Product | Landing |
| --- | --- |
| Cassette | Flat rear face, centered on the intended NFC area |
| Floppy disk | Broad flat rear landing, centered clear of the shallow control outlines |
| VHS tape | Flat 25.4 mm rear land inside the locator ring |
| Trailer Swift | Flat underside of the circular base inside the placement guide |

Install only on a finished print that has cooled completely and passed visual
inspection. A loose layer, warped landing, sharp burr, or oily surface is not an
acceptable adhesive substrate.

1. Confirm that the landing is flat, dry, nonmetal, and free of strings or raised debris.
2. Wipe the landing lightly with 70 percent isopropyl alcohol on a lint-free cloth.
3. Allow all alcohol to evaporate. Do not trap moisture under the tag.
4. Keep the antenna flat. Do not crease, fold, puncture, or sharply bend the sticker.
5. Peel the liner without touching the adhesive or chip area.
6. Center the tag on the landing before allowing the adhesive to make full contact.
7. Press from the center outward for 20 to 30 seconds using clean, even finger pressure.
8. Do not use a metal roller, sharp scraper, or concentrated pressure over the chip.
9. Test ten reads on iPhone and ten on Android immediately after installation.
10. Allow the adhesive to cure undisturbed for 24 hours before pocket, key, drop, or abrasion testing.

Do not use acetone, aggressive adhesive promoter, open flame, or high heat on
PLA or the NFC inlay. If a particular adhesive requires a primer, qualify that
complete material stack on sacrificial prints before production.

## 4. Optional TAP overlay and required clear overlaminate

The release includes printable 25 mm TAP artwork for each product plus generic
and 20-up sheets. The printed circle is an interaction cue; it does not replace
the programmed NFC sticker.

| Product | Suggested overlay copy |
| --- | --- |
| Cassette | `C-69 // SIDE A` and a prominent `TAP` cue |
| Floppy disk | Faux drive-hub treatment, `3.69 MB`, and `TAP` |
| VHS tape | `T-369 // RAD DAD VIDEO` and `TAP` |
| Trailer Swift | `TRAILER SWIFT // TAP THE BASE` |

Use nonmetal paper or nonmetal matte vinyl printed with nonconductive ink. Apply
a clear, nonmetal PET or polypropylene overlaminate to protect the ink and edge
from keys, tables, skin oils, and pocket abrasion. The preferred workflow is to
laminate the printed sheet first and then cut the finished 25 mm circles, which
keeps the stack aligned and avoids an overhanging clear edge.

The physical stack from the printed model outward is:

1. Flat printed NFC landing.
2. Programmed and tested 25 mm NFC sticker.
3. Optional printed 25 mm TAP overlay.
4. Clear nonmetal overlaminate covering the printed overlay.

Keep the stack as thin as practical. Every added adhesive and film layer moves
the phone farther from the antenna. Retest after the TAP overlay and retest
again after the clear overlaminate. The production unit is not qualified if the
bare tag works but the completed stack is unreliable.

The landing itself must stay flat. The clear overlaminate provides abrasion
protection; do not add a metal guard, deep NFC pocket, or conductive protective
ring.

## 5. What the customer should experience

Most current phones can read a standard NDEF URI without a separate app, but
the phone must support NFC and may need NFC enabled.

1. Unlock the phone and wake the screen.
2. Touch the phone to the marked TAP circle.
3. On an iPhone, begin with the top edge of the phone over the circle.
4. On Android, begin near the upper or central rear area; antenna position varies by model.
5. Hold still for one to two seconds instead of sweeping rapidly across the tag.
6. When the notification appears, tap it to open the Rad Dad page.
7. If nothing happens, remove a thick or metal-containing case and try the marked area again.

A successful RF read and a successful website load are different events. A
phone notification proves the tag was detected. A browser error after that may
be a network or redirect problem rather than a failed NFC sticker.

## 6. Handoff card

Give each product with the supplied handoff card. The card should use this
plain-language instruction:

> FIND THE MARKED CIRCLE. UNLOCK YOUR PHONE, TOUCH IT TO THE CIRCLE, HOLD FOR A MOMENT, THEN TAP THE NOTIFICATION.

The card must also include a QR fallback to
`https://raddadband.com/tap/`. Test the printed QR from the final card size.
Do not put a QR code on the 25 mm overlay; it would be too small, visually busy,
and less reliable than the full-size card fallback.

The handoff card should identify the object as an NFC item, state that no app is
required on a compatible phone, show the likely iPhone and Android antenna
areas, and provide the plain URL in readable text in case both NFC and QR are
unavailable.

## 7. Failure diagnosis

| Symptom | Likely cause | Corrective action |
| --- | --- | --- |
| No phone reads the loose tag | Blank, defective, counterfeit, damaged, or incorrectly encoded tag | Try a known-good phone and reader; reject or replace the tag |
| One phone reads and another does not | NFC disabled, antenna-position difference, incompatible case, or phone limitation | Enable NFC where applicable, remove the case, and locate the phone antenna |
| Tag worked loose but fails after installation | Metal or conductive layer, damaged antenna, poor centering, excessive stack thickness, or nearby keys | Remove metal materials, isolate keys, inspect the tag, and replace if damaged |
| Bare installed tag works but overlay stack does not | Metallic overlay, conductive ink, thick laminate, or air gap | Replace the overlay with qualified nonmetal stock and retest each layer |
| Read is intermittent | Marginal tag, off-center phone placement, thick case, key bundle detuning, or weak antenna coupling | Test contact position systematically and replace any tag below the qualified baseline |
| Notification appears but the page fails | Network outage, DNS, TLS, redirect, or website failure | Test the encoded URL directly in a browser and repair the web route |
| Wrong page opens | Incorrect NDEF record, stale redirect, or wrong batch programming | Verify the URI and redirect; replace a locked tag or rewrite an unlocked tag |
| Tag reports read-only before approval | Vendor pre-lock, accidental lock, or reused tag | Reject and replace it; do not attempt production with unknown lock state |
| Overlay lifts or bubbles | Contamination, insufficient pressure, incompatible adhesive, uncured stack, or edge abrasion | Remove the overlay, clean the surface, apply qualified material, cure, and retest |
| Tag works until keys are attached | Metal key bundle is detuning or physically covering the antenna | Reorient the product during use, test with the production ring, and improve the handoff cue |

## 8. Replacement procedure

A locked tag with the wrong URL cannot be repaired by rewriting. Replace it.

1. Record the failed unit, symptom, tag lot, and encoded URL before removal.
2. Remove the clear overlaminate and printed overlay without gouging the landing.
3. Lift the NFC sticker slowly with a plastic pick or dental floss at room temperature.
4. Do not use a knife, open flame, or high heat that can deform the print or cut the antenna.
5. Remove adhesive residue with a small amount of isopropyl alcohol and a lint-free cloth.
6. Inspect the landing for warping, torn layers, or raised residue.
7. Program and fully pre-test the replacement tag before installing it.
8. Install the replacement, overlay, and overlaminate in the normal sequence.
9. Repeat all post-install, completed-stack, case, ring, key-bundle, and 24-hour tests.
10. Quarantine other units from the same tag or adhesive lot if the failure may be systemic.

## 9. Safety and care

- These are small accessories and collectibles, not toys. Keep loose tags, split rings, broken prints, and small parts away from young children and pets.
- Inspect keychain eyelets and split rings periodically. Stop using a unit that is cracked, sharp, delaminated, or partially detached.
- Do not bend, puncture, sand through, melt, or burn the NFC tag. A damaged antenna can develop sharp edges.
- Keep the completed item away from high heat, vehicle dashboards, dishwashers, solvents, and prolonged water exposure unless the exact print and adhesive stack has been qualified for that environment.
- Do not place metallic stickers, foil tape, magnetic plates, or metal-backed phone accessories directly over the NFC area.
- Do not encode passwords, payment data, medical information, access credentials, or other sensitive information.
- Use HTTPS and maintain the redirect. A physical tag remains in circulation even when website ownership or hosting changes.
- People with implanted or wearable medical devices should follow the device manufacturer's handling guidance and should not hold accessories directly over the device.
- A QR and readable URL on the handoff card are required fallbacks; NFC must not be the only way to reach important information.
