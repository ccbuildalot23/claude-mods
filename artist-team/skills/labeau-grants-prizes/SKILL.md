---
name: labeau-grants-prizes
description: LaBeau lane. Keeps Chris's poetry submissions tracker (journals, prizes, grants) with each call's rules, fees and deadlines, sorts which never-posted poems could fit, and formats files, stopping before any submission or fee. Use for "what's due", "grants", "prizes", "submissions", "where can I send poems".
---

# Grants and prizes (LaBeau lane)

Read `../../RULES.md` first. You keep the tracker and the checklists. Chris writes every word that goes out under his name, and he does every submission himself.

## The tracker (Airtable is the one source of truth)

Every chat and agent that touches submissions reads and writes **one table**: Airtable base `LaBeau` (`app9ouvv8NofAWOjg`), table `Submission Log` (`tblRMGQ83jZMSyqT6`). Use the Airtable connector. Read the table before you suggest any poem for any call, so nothing is sent twice and nothing under review gets posted.

One row per poem per call. Poems sent together share the same `Entry` value (for example `Hearst 2026`). The fee goes on one row of the entry only.

| Field | What goes in it |
|---|---|
| Poem title | his title, exactly |
| Venue | the call's name |
| Kind | Journal, Contest, Grant, Live reading or slam, Anthology, Other |
| Entry | groups the poems sent together |
| Status | Planned, Sent, Accepted, Declined, Withdrawn, No response |
| Deadline | when the call closes, Eastern time |
| Date sent | the day he submitted (only he submits) |
| Winners announced | the decision date the venue gives; leave blank if none is posted and say so in Notes |
| Expected response | your follow-up date if the venue gives no decision date |
| Prize / Pay / Fee | top prize, pay on acceptance, his fee |
| Must stay unposted | ticked while the poem is out; it stays off every surface |
| Simultaneous OK | does the venue allow it |
| Feedback | Not offered, Paid add-on, Free on request, Unknown |
| AI policy | Bans AI-guided work, Bans AI-generated text, Not stated |
| Link | the call's page |
| Logged by | which chat or agent wrote the row |
| Notes | holds, dated facts with sources |

- **Unpublished rule:** most journals count anything posted on Substack or social media as published. Say exactly what each call says in Notes.
- **AI rule:** if a call bans AI help (for example The Offing, "including editing", or Ninth Letter, "created, guided, or revised"), set `AI policy` and write `HANDS OFF` in Notes. After that you track only its deadline and status. You do no formatting, sorting or checklist work for that call, and you never touch his statement or cover note.
- **Pen name:** if the call is silent, the next step is "ask about the LaBeau byline in the cover note or after acceptance".
- **Holds:** when a poem goes out, tell the posting plan to hold the poem and any gem lines cut from it until the result. When a result comes in, update `Status` and untick `Must stay unposted` only if it was declined.
- **Calendar:** each Planned row's deadline goes on his Google Calendar as an all-day "Due:" event, with the venue, fee and link in the description. Adding a calendar event is fine; inviting anyone is not.
- The vault note `Professional Knowledge/Artist Support Team/LaBeau Lane/Submissions Tracker.md` is a readable mirror only. If the two disagree, Airtable wins.

## Each run

1. Read the Submission Log. Re-check every open call's page for deadline and rule changes. Note the date you checked, and give the source link for every fact.
2. List what's due in the next 14 days, soonest first, with one small next step for him for each.
3. For a call he's working on, ask him to pick from his never-posted poems by title. Never judge a poem's quality or change a line. You can say "this one is 31 lines and the limit is 30".
4. When he says so, format the file to the call's spec (font, margins, page breaks, whether his name appears). Read it back to him before he uploads it.
5. After he says he sent it, set `Status` to Sent and fill `Date sent`.
6. Stop. Submitting, creating accounts and paying fees are his hand, with his yes for each one.

## Sources

The Grok plan `grok-bridge/research/poetry-submissions-plan-2026-10-26.md` and the tracker note. For new calls, use the `labeau-research` subagent (parallel search) and dated public pages. Never use a list without a date.
