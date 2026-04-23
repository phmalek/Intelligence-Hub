# Note: Upper Funnel / Lower Funnel Logic and Improvement Option

## 1. What the workbook is currently doing

From the workbook logic, upper funnel is not calculated as the full paid-media budget.

It is calculated as a separate impression-based budget block:

- required sessions
- multiplied by impressions per session
- multiplied by cost per impression

In the workbook this is visible as:

- `AN41` = required sessions
- `AN44` = required impressions per session
- `AN46 = AN41 * AN44` = required impressions
- `AN45` = cost per impression
- `AN47 = AN46 * AN45` = upper-funnel budget

So the upper-funnel budget is:

`upper funnel budget = required sessions × impressions per session × cost per impression`

Lower funnel is calculated separately as a session/CPS budget block:

- `Y26` = required DCFS
- `Y28` = session to DCFS rate
- `Y29 = Y26 / Y28` = required paid sessions
- `Y17` = cost per paid session
- `Y31 = Y29 * Y17` = lower-funnel budget

So the lower-funnel budget is:

`lower funnel budget = required paid sessions × cost per paid session`

The important point is that the workbook does not explicitly model a handoff where upper-funnel impressions generate a defined share of sessions and lower funnel only picks up the remainder.

Instead, the upper- and lower-funnel budgets are calculated in parallel and then added together.

## 2. Is the handoff between upper and lower funnel explicit?

No.

The workbook does not clearly show:

- how many sessions are created by upper funnel
- how many sessions are still required from lower funnel

That is why the handoff is unclear.

In practical terms, the model appears to:

- cost lower funnel as if it must fund the session requirement
- and separately cost upper funnel through an impressions-based route

This is what creates the risk of overlap or double counting.

## 3. Is it sensible to improve the model by adding an explicit parameter?

Yes.

A sensible modelling improvement would be to introduce an explicit parameter such as:

`upper_funnel_session_share`

This would state how much of the required session burden is assumed to come from upper funnel.

For example:

- if `upper_funnel_session_share = 20%`
- then upper funnel is assumed to generate `20%` of required sessions
- and lower funnel should only be asked to generate the remaining `80%`

This would make the handoff explicit and reduce the risk of double counting.

## 4. What happens if we assume 20% comes from upper funnel?

If we use the existing workbook outputs and make a simple illustrative adjustment:

- current required DCFS = `101,806.9`
- current required paid sessions = `92,527,054.8`
- current lower-funnel budget = `48.60m`

Then assuming upper funnel is responsible for `20%` of that burden would reduce the lower-funnel burden to `80%`:

- adjusted lower-funnel DCFS = `81,445.5`
- adjusted lower-funnel paid sessions = `74,021,643.8`
- adjusted lower-funnel budget = `38.88m`

So lower funnel would fall by:

- `9.72m`
- or `20%`

If we apply the same principle to the later always-on block:

- current always-on budget `AN43 = 104.19m`
- adjusted always-on budget at `80%` = `83.36m`

## 5. Should that freed budget simply be removed?

No, not if the intention is to recognise upper funnel properly.

The better interpretation is:

- lower-funnel budget should come down because it no longer owns 100% of session delivery
- upper-funnel budget should go up because it is now explicitly credited with delivering part of the session burden

So the improvement should be a reallocation, not just a reduction.

That means the key output should be:

- a lower share for lower funnel
- a higher share for upper funnel
- with total budget then depending on the efficiency assumptions applied to each block

## 6. What about the 50% non-trackable assumption?

The idea of allowing for a non-trackable paid-media contribution is rational.

However, the flat `50%` assumption is very material and should not be treated as fact unless it is evidenced.

If the intended meaning is:

`50% of paid impact is not trackable`

then the measurable share is `50%`, so total paid impact is:

`measurable paid impact / 0.5`

If that assumption were reduced to `20% non-trackable`, then the measurable share would be `80%`, and total paid impact should be:

`measurable paid impact / 0.8`

That would reduce the implied total paid contribution and therefore reduce the budget requirement coming from that chain.

The key challenge point is that the workbook label and the formula should be checked carefully to ensure they mean the same thing.

## 7. Objective conclusion

From the workbook logic:

- upper funnel is calculated as an impression-based derived budget block
- lower funnel is calculated as a session/CPS-based derived budget block
- the handoff between them is not explicitly modeled

That means the current model is not clearly stating:

- what share of sessions comes from upper funnel
- what share remains for lower funnel

The most practical improvement would be to add an explicit parameter for upper-funnel session contribution, and use it to rebalance the split between upper and lower funnel rather than treating the two blocks as parallel budgets with an unclear overlap.
