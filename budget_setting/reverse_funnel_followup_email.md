# Reverse Funnel Follow-up Email Draft

Subject: Reverse Funnel follow-up: draft decision layer for budget discussion

Hi all,

Following the recent conversations with PWC, I think we now have a much clearer shared understanding of where the real discussion sits. A lot of the back and forth seems to have come less from the reverse-funnel logic itself being fundamentally wrong, and more from the way labels such as `Highlight`, `Upper Funnel`, and `Always On` were being interpreted. In particular, it now feels clear that `Highlight` should not automatically be read as equivalent to `Upper Funnel`, and that this classification point is one of the main reasons the discussion has been harder than it needed to be.

To help make that logic more transparent, I have started to build a Sankey-style decision view in the app. The intention is not to replace the workbook or claim a final answer, but to act as a translation layer on top of the current reverse-funnel output. In other words, it helps us move from a relatively narrow `Always On vs Highlight` budget split into something that can be discussed in fuller funnel-planning terms, with assumptions made explicit rather than left implicit.

The current levers in that view are:

- `Base highlight share`: the starting share of total budget allocated to `Highlight` before any planning adjustments
- `Offline upweight`: an adjustment to reflect non-digital / offline contribution not captured in the digital impressions-based logic
- `Beyond-website upweight`: an adjustment to reflect media influence beyond the attributable OGS / website-touch path
- `Highlight credit shift`: an adjustment to give `Highlight` credit for clicks / sessions that might otherwise be fully attributed to `Always On`
- `Highlight upper share`: the share of `Highlight` classified as upper rather than lower funnel
- `Always On upper share`: the share of `Always On` classified as upper / mid-funnel support rather than pure lower-funnel harvesting
- `Upper to Awareness`: the share of upper-funnel budget that lands in `Awareness` rather than `Consideration`
- `Lower to Conversion`: the share of lower-funnel budget that lands in `Conversion / Harvesting` rather than `Consideration`

I think this is useful because it gives us a more explicit decision-support layer on top of the reverse funnel. Rather than debating whether the workbook is “right” or “wrong”, it gives us a way to discuss how the output should be interpreted and classified in planning terms.

Debs’ points remain especially helpful in shaping this:

- `Highlight` needs to be classified clearly, especially if it is being used as shorthand for model launches rather than all upper-funnel activity
- offline / non-digital contribution is not captured in the digital-only session logic
- the current OGS / website-touch logic may understate the broader role of media in sales journeys
- highlight activity should receive some credit for the click / session contribution that otherwise sits entirely with `Always On`
- the `non-trackable` assumption remains sensitive and should be treated carefully

Please feel free to add your brains to this. In particular, I’d welcome views on whether these are the right levers, whether anything important is missing, and whether the current framing helps us have a more practical and transparent discussion before we take the next step with PWC / markets.

Best,
Ali
