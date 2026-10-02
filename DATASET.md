# Private pilot dataset contract
Pilot: 30-50 permission-cleared photos. Next: 200-400 stills from 20-30 sessions, ideally >=3 machines and >=2 venues. Hold out >=50 photos from unseen machine/session; split 70/15/15 by whole session with venue/machine/augmentation siblings isolated. Never infer hidden cards. Double-label 10-20%. Target gates (not current results): >=95% screen detection, >=98% occupancy, >=90% visible-card identity, >=80% whole-frame exact extraction; abstention reported separately.

## Prototype labels (current five owner photos)
- Per image: image_sha256, 28 tableau slot states (covered/face_up/empty/unknown), face-up rank (suit not yet labelled), waste rank, HUD stock number as displayed, ui_state. Hidden cards are never labelled.
- Keep HUD stock and engine stock as separate fields; HUD-minus-one is an unverified hypothesis.
- Glyph templates built from these photos stay private (not committed). Evaluate leave-one-image-out only, never on training images; report abstentions separately from errors.
- 33 labelled face-up cards cover all 13 ranks but most only once or twice; more frames needed before any accuracy claim. Current gate (score>=0.6, margin>=0.2) was tuned on the same 33 samples, so treat it as optimistic.
