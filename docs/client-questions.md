# Questions for the client

Business decisions that are **not ours to make**. Defaults are built so the demo works.
We go through this list with the client at the end of the project. Claude Code: add new
questions here, never decide them in code.

| # | Topic | What the demo does now | Decide |
|---|---|---|---|
| 1 | Revenue shares | Staff set the platform fee in the console: a default for new instructors (kept on approval) and a custom fee per instructor, for marketplace sales. Instructor-coupon sales (97%) and the subscription pool (25%) are fixed. Seeded default: 63% fee (37% to the instructor) | Final default fee; whether coupon and pool rates should also be per instructor |
| 2 | Instructor payouts | £25 minimum, monthly, 30-day hold | Minimum, frequency, hold |
| 3 | Refunds | 30-day window, instant self-service (the approved mockup said admin-reviewed) | Instant or reviewed |
| 4 | Tax | Prices shown tax-inclusive | Turn on Stripe Tax / VAT? |
| 5 | Currencies | Several currencies; some Stripe can't take | Which to offer |
| 6 | Plan prices | Personal £19.99/month with 7-day trial; Team £360/seat/year, min 5 seats | Prices, trial, minimum |
| 7 | Content protection (DRM) add-on | £49/month | Price |
| 8 | Team Plan sales contact | Placeholder email | Real contact |
| 9 | Notification wording, starter badges | Our wording; 5 badges | Wording, badge set |
| 10 | Microsoft sign-in audience | Any work/school + personal accounts | Or company tenants only |
| 11 | Production domain and hosting | None yet | Domain, hosting; needed for live Stripe/Bunny webhooks and Azure CORS |
| 12 | Commission rules | Rules by course > instructor > category > price band > default; discounts reduce the instructor share proportionally | Which rules, and how discounts affect commission |
| 13 | Payout methods | Stripe Connect paid automatically; PayPal, Wise and bank recorded and paid by staff by hand | Which methods to offer |
| 14 | Payout requests | Instructors can request their available balance (past the hold, above the minimum) | On request, automatic monthly, or both |
| 15 | Regional pricing | Staff can set a price per country; otherwise the currency price | Use it? Which countries? |
| 16 | Promotions | One promotion per order; instructor coupons still work; no stacking | Stacking rules, first-purchase offer |
| 17 | Plans and included courses | Each plan can list its courses; empty = every course marked "in subscription" | Which courses per plan |
| 18 | Certificate expiry | No expiry by default; staff can set one per certificate | Should some courses expire (e.g. compliance)? |
| 19 | 2-step sign-in | Optional for users; staff can be required to use it | Require for staff / company admins? |
| 20 | Maintenance mode, guest browsing, registration | All on (maintenance off) | Defaults for launch |
