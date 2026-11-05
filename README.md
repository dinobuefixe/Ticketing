# Project A: Ticketing

Read [README.md](README.md) first. It has the rules, requirements, documentation, Git rules and grading that apply to this project. This file describes the business.

## Context

A ticketing company sells tickets for concerts, theatre, comedy and sport events in venues across Portugal. Organisers publish events, the company sells the tickets online, and venue staff scan them at the door.

The big problem of the business is the on-sale moment. When tickets for a popular concert go on sale at 10:00, thousands of customers try to buy the same seats in the same second. A seat sold twice means two people at the door with valid tickets for the same chair, a refund, a complaint and bad press. Your project must make that impossible.

## Actors

- **Customer**: browses events, holds seats, pays, cancels, receives tickets.
- **Organiser**: a company that publishes events and receives the revenue.
- **Venue staff**: scan tickets at the gates.
- **Back office**: the company's staff, who create venues, cancel performances and read reports.

## Requirements

Everything below must be representable in your design. Names in this section are business names, not table or column names: the schema is yours to design.

### Venues and seating

- A venue has a name (unique), a city, a full address and a maximum capacity.
- A venue is divided into sections (for example "Plateia", "Balcão 1", "Pista"). A section name is unique within its venue.
- A section is either **seated** or **standing**.
  - A seated section has rows, and each row has numbered seats. A seat is identified by its section, row label ("A", "B", ..., "AA") and number. Some seats are marked as wheelchair accessible, and some as restricted view.
  - A standing section has no seats, only a capacity (the number of people it can hold).
- The sum of the capacities of all the sections of a venue (seats plus standing capacity) cannot exceed the venue's maximum capacity.
- A venue has named gates ("Porta 1", "Porta Norte"), unique within the venue.

### Organisers and events

- An organiser has a company name, a Portuguese tax number (NIF, 9 digits, unique), a contact email (unique) and a phone number.
- An event belongs to one organiser and has a title, a category (concert, theatre, comedy, sport, other), a minimum age (0, 6, 12, 16 or 18), and a description.
- Events have details that depend on the category, and the company wants to add new ones without changing the database. For example:
  - concert: line-up (artists in order, with the headliner marked), genres;
  - theatre: director, cast (actor and role), duration, language, whether it has surtitles;
  - sport: competition, home team, away team, round;
  - comedy: comedians, whether it is recorded for TV.
- An event has one or more **performances**. A performance is a date and time at one venue, with an expected end time. The same event can have performances at different venues (a tour).
- Two performances at the same venue cannot overlap in time.
- A performance has a sales opening date and time. Sales close when the performance starts.
- A performance is `scheduled` before sales open, `on_sale` from the sales opening until it starts, `sold_out` when no seat or place is left, `finished` after its end time, and `cancelled` when the back office cancels it. Only `cancelled` is set by a person; the others follow from the time and the tickets sold (see "State that changes with time" in the README).

### Prices

- For each performance, each section of the venue has a price. Different performances of the same event can have different prices.
- A price is in euros, with two decimal places, and cannot be negative. A price of zero is allowed (free events, invitations).
- If a price changes after tickets were sold, tickets already sold keep the price they were sold for.

### Customers

- A customer has a name, an email (unique), a password hash, a date of birth, a phone number and the date they registered.
- A customer can only buy tickets for a performance if they are at least the event's minimum age on the day of the performance.

### Seat holds

- Before paying, a customer chooses seats (in a seated section) or a number of places (in a standing section) for one performance with status `on_sale`. Those seats or places are **held** for that customer for **10 minutes**.
- While a seat is held, no other customer can hold it or buy it.
- If the customer does not pay within 10 minutes, the hold expires and the seats become available again, without any action by the customer or by a person.
- A customer can hold at most **6 tickets per performance**, counting the tickets they already bought for that performance. This limit must hold for requests made one after another; simultaneous requests by the same customer are not tested.
- A customer can make at most **10 hold attempts per minute**. Further attempts in that minute are rejected. This stops bots.

### Orders, tickets and payments

- An order belongs to one customer and contains one or more tickets, all for the same performance.
- An order has a status: `pending`, `paid`, `cancelled` or `refunded`, the date and time it was created and, when it applies, paid.
- The order lifecycle:
  1. The customer's first checkout attempt for a hold creates the order as `pending`, with the held seats or places.
  2. An approved payment makes the order `paid`, issues its tickets and releases the hold. This happens in one PostgreSQL transaction.
  3. A declined payment is recorded with status `declined`. The order stays `pending` and the hold keeps running, so the customer can try again before it expires.
  4. If the hold expires before an approved payment, the order becomes `cancelled`. A payment attempt for an order whose hold has expired is refused.
  5. A paid order can later become `refunded` (see [Cancellations and refunds](#cancellations-and-refunds)).
- A ticket is for one performance and either one specific seat (seated section) or one place in a standing section. It records the price it was sold for, a unique code printed on it (12 random characters) and a status: `valid`, `used` or `cancelled`.
- **A seat can never have two tickets with status `valid` or `used` for the same performance.**
- **The number of `valid` or `used` tickets in a standing section for a performance can never exceed the section's capacity.**
- A promo code has a code (unique), a discount (a percentage between 1 and 100, or a fixed amount in euros, never both), a validity period, an optional event it is restricted to, and a maximum number of uses. One order uses at most one promo code. A use counts when the order becomes `paid`, and is not given back if the order is later refunded. **A promo code can never be used more times than its maximum.**
- The total of an order is the sum of its tickets minus the discount. It can never be negative.
- A payment belongs to one order and has an amount, a method (`card`, `mbway` or `multibanco`), a status (`approved`, `declined` or `refunded`), the date and time, and a provider reference (unique).
- Payments are simulated. The request to pay carries a field `simulate` with the value `approved` or `declined`, and the app records the payment with that outcome and a generated provider reference.

### Cancellations and refunds

- A customer can cancel a paid order up to 48 hours before the performance. Its tickets become `cancelled`, the seats become available again, the order becomes `refunded`, and a payment with status `refunded` and the same amount is recorded.
- When the back office cancels a performance, every paid order for it is refunded in the same way, and the performance becomes `cancelled`.

### Check-in

- At the door, staff scan the ticket code at a gate of the venue.
- A ticket can be checked in only on the day of its performance (Lisbon time), only if it is `valid`, and only once. After check-in it becomes `used`.
- Every scan is recorded with the ticket code read, the gate, the staff member, the date and time and the result (`accepted`, `already_used`, `cancelled`, `wrong_day`, `unknown_code`), including the scans that were rejected.

## Where the rules are enforced

Must be enforced by PostgreSQL:

- A seat never has two `valid` or `used` tickets for the same performance.
- A standing section never has more `valid` or `used` tickets for a performance than its capacity.
- Two performances at the same venue never overlap in time.
- A promo code is never used more times than its maximum, and has a percentage or a fixed amount, never both.
- Prices, ticket prices and order totals are never negative; a percentage discount is between 1 and 100.
- Unique values: venue name, section name within a venue, seat within its section, gate name within a venue, organiser NIF and email, customer email, ticket code, provider reference.
- A NIF has exactly 9 digits; statuses, categories and minimum ages only take the values listed above.
- The scan records are never updated or deleted by the app role.

May be enforced in PostgreSQL or in the app (say which in `docs/postgres.md`):

- The sum of the section capacities does not exceed the venue capacity.
- The customer's minimum age.
- The limit of 6 tickets per customer per performance.
- Holds only for performances `on_sale`; cancellation only up to 48 hours before; check-in only on the day.
- The limit of 10 hold attempts per minute.

## Flows the app must implement

All flows are mandatory. F2 and F3 are the concurrent flows.

| Flow | Description |
|------|-------------|
| F1. Seat map | For a performance, list every section with its price and, for each seat, whether it is free, held or sold; for standing sections, the places left. This is the most requested page during an on-sale. **Read from Redis**: a repeated request must not query PostgreSQL. |
| F2. Hold | A customer holds seats or standing places for a performance, with every rule in [Seat holds](#seat-holds). |
| F3. Checkout | A customer pays for their held seats, optionally with a promo code, following the [order lifecycle](#orders-tickets-and-payments). |
| F4. Cancel | A customer cancels a paid order, with the rules in [Cancellations and refunds](#cancellations-and-refunds). |
| F5. Check-in | Staff scan a ticket code at a gate. |
| F6. Cancel performance | The back office cancels a performance and every order is refunded. |
| F7. Reports | The back office reads the reports of [Reports](#reports-mongodb). |

## The concurrent flow

The rules under test are:

1. A seat is never sold or held twice for the same performance.
2. A standing section never sells more places than its capacity.
3. A promo code is never used more times than its maximum.

Project must cover at least these two scenarios:

- **Same seat** (F2, then F3). The fixture creates a performance `on_sale` and 50 customers. All 50 send a hold request for the same seat at the same moment. Exactly one hold succeeds and 49 are refused. The winner then pays with `simulate=approved`. At the end, PostgreSQL has exactly one `valid` ticket for that seat.
- **Last places** (F2 and F3 together). The fixture creates a standing section with 10 places left and 100 customers. Each customer holds 1 place and immediately pays, all 100 at the same moment. At the end, exactly 10 have a `paid` order and PostgreSQL has exactly as many `valid` tickets in the section as its capacity.

Covering the promo code rule too is a good extension.

## MongoDB collections

Mandatory:

- **Hold-attempt log**: one document per hold attempt (customer, performance, the seats or number of places asked for, the result and the reason if refused, the time). Written by the app on every attempt, refused ones included. Kept for 90 days, with a TTL index.
- **Report collections**: the derived collections written by the report export (see the README), with the data your pipelines need: for example one document per performance with its sales, or one per paid order with its tickets. The shape is yours to design.

You decide:

- Where the event details that depend on the category (see [Organisers and events](#organisers-and-events)) are stored: in MongoDB, in a `jsonb` column, or in tables. Justify the choice in `docs/mongodb.md`.

## Reports (MongoDB)

The back office reads these reports often and does not want them computed from PostgreSQL on every request. Your pipelines must answer at least 3 of them:

1. For each performance: tickets sold and revenue per section, revenue per payment method, promo codes used and the discount they gave, and the check-in rate (checked-in tickets over sold tickets).
2. Revenue per organiser per month, for the last 12 months.
3. The 10 events that sold most tickets in each city in the last 30 days.
4. Occupancy per venue: for each venue, the average percentage of capacity sold across its performances in the last 90 days, seated and standing sections separately.
5. Promo code effectiveness: for each code, the number of orders, the total discount and the average order value with and without a code for the same event.
6. The hours of the day with most hold attempts that did not end in a sale (from the hold-attempt log).

## Real-time features (Redis)

- The seat map (F1) during an on-sale, without hitting PostgreSQL on every request.
- The holds, with their 10-minute expiry.
- The limit of 10 hold attempts per customer per minute.
- A "trending now" list: the 20 events with most tickets sold in the last hour, updated with every sale.
- Live counters per performance: tickets sold, places left per section.

## Data that expires

| Data | How long it lives | Where |
|------|-------------------|-------|
| A seat hold | 10 minutes after it is made, unless the order is paid first | you decide |
| The hold-attempt counter of a customer | 1 minute | you decide |
| The "trending now" window | sales of the last hour | you decide |
| The hold-attempt log | 90 days | MongoDB, with a TTL index |

Document each decision in `docs/architecture.md`.

## Frequent queries (PostgreSQL)

Use at least 3 of these for the `EXPLAIN` evidence required in the README:

1. The sold seats of a performance (for the seat map and for the Redis rebuild).
2. The orders of a customer, newest first, 20 per page.
3. The tickets of a performance with status `valid` or `used`, counted per section.
4. The check-ins of a performance per gate in the last hour.
5. Performances on sale in a city in the next 30 days, ordered by date.
6. The revenue of a performance (paid orders minus refunds).

## Seed volumes

| Data | Volume |
|------|--------|
| Venues | 30, in at least 8 cities |
| Seats | about 150,000 in total, plus standing sections |
| Organisers | 200 |
| Events | 1,500 |
| Performances | 4,000, between 12 months ago and 6 months from now |
| Customers | 100,000 |
| Orders | about 450,000 |
| Tickets | at least 1,000,000 |
| Payments | one per paid order, plus declined attempts and refunds |
| Check-ins | for most tickets of past performances |
| Hold-attempt log (MongoDB) | at least 50,000 documents, within the last 90 days |
| Report collections (MongoDB) | written by the report export from the seeded data |

Past performances are `finished` and most of their tickets are `used`. Some performances are `cancelled`, with their orders refunded. Some performances are sold out. Some events sell far more than others.

## Ideas to go further

- A waiting list per performance: when a ticket is cancelled, the first customer on the list gets a hold on it.
- A queue for on-sales: customers who arrive before sales open get a random position and are let in by batches.
- Ticket transfer from one customer to another, with a new code and the old one cancelled.
- Dynamic pricing: the price of a section rises as it fills, without changing the price of tickets already sold.
- Season tickets valid for every performance of an event.