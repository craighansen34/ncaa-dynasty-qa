# Feature: Coach XP Progression, Archetype Trees, and Level Cap State Machine
# Path: features/coach_progression_and_perks.feature

Feature: Coach XP Progression, Archetype Trees, and Level Cap State Machine
  As the dynasty progression engine
  I want exact XP scaling, skill point invariants, and tier unlock enforcement
  So that progression remains mathematically consistent over 50-year careers.

  Background:
    Given coach is initialized at Level 1 with 0 XP
    And unspent SP evaluates to 15
    And total earned SP evaluates to 15

  Scenario: TR-22 Base XP threshold calculation follows exact linear progression curve
    Then threshold for Level 1 evaluates to 1000
    And threshold for Level 2 evaluates to 1200
    And threshold for Level 3 evaluates to 1400

  Scenario: TR-23 Single-level XP gain crossing threshold triggers level up and awards exactly 10 SP
    When coach earns 1000 XP
    Then coach advances to Level 2
    And current XP evaluates to 0
    And unspent SP evaluates to 25

  Scenario: TR-24 Multi-level XP overflow preserves correct remaining XP and awards cumulative SP
    Given coach is Level 4 with 950 XP
    When coach earns 3000 XP
    Then coach advances to Level 6
    And current XP evaluates to 550 toward next threshold of 2000
    And unspent SP evaluates to 65

  Scenario: TR-25 Total earned SP invariant strictly equals 15 plus 10 per level above 1
    When coach advances to Level 10
    Then total earned SP evaluates to 105
    When coach advances to Level 25
    Then total earned SP evaluates to 255
    When coach advances to Level 50
    Then total earned SP evaluates to 505

  Scenario: TR-26 Spent plus unspent SP balance must strictly equal total earned SP
    Given coach is Level 5 with 55 total earned SP
    When coach spends 30 SP in perks
    Then spent SP evaluates to 30
    And unspent SP evaluates to 25
    And spent plus unspent SP strictly equals 55

  Scenario: TR-27 Primary archetype selection applies 20 percent discount to perk costs
    Given primary archetype is Recruiter
    Then base 10 SP perk in Recruiter costs 8 SP
    And base 10 SP perk in Tactician costs 10 SP

  Scenario: TR-28 Tier 2 perk unlock requires minimum 20 SP invested in specific tree
    Given coach has 19 SP invested in Recruiter tree
    Then Tier 2 perk purchase is blocked
    When coach invests 1 additional SP in Recruiter tree
    Then Tier 2 perk purchase is unlocked

  Scenario: TR-29 Tier 3 perk unlock requires minimum 50 SP invested in specific tree
    Given coach has 49 SP invested in Recruiter tree
    Then Tier 3 perk purchase is blocked
    When coach invests 1 additional SP in Recruiter tree
    Then Tier 3 perk purchase is unlocked

  Scenario: TR-30 Coordinator synergy activates when primary schemes match
    Given head coach offensive scheme is Spread Option
    When offensive coordinator has matching scheme Spread Option
    Then coordinator scheme synergy activates with full bonus

  Scenario: TR-31 Poached coordinator causes immediate forfeiture of coordinator perk tree buffs
    Given offensive coordinator provides active passing buff
    When offensive coordinator is poached by rival program
    Then coordinator buffs are immediately revoked

  Scenario: TR-32 Mandatory retirement occurs after reaching age 70 or 50 years coached
    Given coach reaches age 70
    When dynasty offseason evaluation executes
    Then coach mandatory retirement triggers

  Scenario: TR-33 Unspent SP triggers non-blocking advisory notification before week advance
    Given coach has unspent SP balance of 10
    When user advances to gameday
    Then advance proceeds with unspent SP advisory warning

  Scenario: TR-34 Mandatory advance blockers prevent sim when critical requirements unmet
    Given starting quarterback depth chart slot is vacant
    When user attempts to advance to gameday
    Then advance is strictly blocked until slot filled

  Scenario: TR-35 Isolated recruiting and progression states prevent cross-module side effects
    Given coach current XP is 400
    When recruiting hours are staged and committed
    Then coach current XP remains strictly 400

  Scenario: TR-36 Multi-tree SP investment allows dual-archetype perk access
    Given coach invests 20 SP in Recruiter and 20 SP in Tactician
    Then Tier 2 perks in both trees are unlocked

  Scenario: TR-37 Scheme mismatch neutralizes coordinator synergy bonus
    Given head coach offensive scheme is Spread Option
    When offensive coordinator has mismatched scheme Pro Style
    Then coordinator scheme synergy evaluates to 0

  Scenario: TR-38 Coach career progression tracks cumulative 50-year coaching history
    When coach completes 50 seasons
    Then career stats record 50 distinct seasonal results

  Scenario: TR-39 Coach contract buyout penalty applies when terminating contract early
    Given coach contract has 3 years remaining with buyout penalty
    When school terminates contract early
    Then buyout financial penalty is assessed

  Scenario: TR-40 Exact threshold match to Level 50 sets current XP to 0 and XP to next level to null
    Given coach is Level 49 with 10200 XP out of 10600 XP required for Level 50
    When coach earns 400 XP
    Then coach advances to Level 50
    And current XP evaluates to 0
    And numeric XP to next level evaluates to null

  Scenario: TR-41 Level cap at 50 freezes XP gain and preserves null next level
    Given coach is Level 50
    When coach earns 1000 XP
    Then coach remains Level 50
    And current XP evaluates to 0
    And numeric XP to next level evaluates to null

  Scenario: TR-42 Massive XP burst crossing into Level 50 consumes required XP, discards surplus, and sets next level to null
    Given coach is Level 49 with 9000 XP out of 10600 XP required for Level 50
    When coach earns 5000 XP
    Then coach advances to Level 50
    And current XP evaluates to 0
    And numeric XP to next level evaluates to null

  Scenario: TR-48 Reaching exactly 50 seasons coached triggers mandatory retirement without age 70
    Given coach completes 50 seasons
    When dynasty offseason evaluation executes
    Then coach mandatory retirement triggers

  Scenario: TR-49 Coach at age 69 with 49 seasons coached does not retire
    Given coach is age 69 with 49 seasons coached
    When dynasty offseason evaluation executes
    Then coach mandatory retirement does not trigger

  Scenario: TR-50 Earning zero XP leaves level and XP state untouched
    When coach earns 0 XP
    Then coach remains Level 1
    And current XP evaluates to 0
    And unspent SP evaluates to 15
