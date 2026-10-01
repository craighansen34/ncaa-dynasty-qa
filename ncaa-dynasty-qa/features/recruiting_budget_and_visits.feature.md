# Feature: Recruiting Hour Budget, Visit Lifecycle, and Rollover State Machine
# Path: features/recruiting_budget_and_visits.feature

Feature: Recruiting Hour Budget, Visit Lifecycle, and Rollover State Machine
  As the game simulation engine
  I want deterministic accounting for recruiting hour allocations, visits, and rollovers
  So that multi-week budgets, mid-week relief injections, and eligibility invalidations evaluate accurately across 50 simulated seasons.

  Background:
    Given base weekly recruiting budget is 500 hours
    And total available hours evaluate to 500
    And total committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-01 Staging action reserves draft hours immediately without committing
    When the user stages a 50 hour recruiting action
    Then staged hours evaluate to 50
    And remaining available hours evaluate to 450
    And committed hours evaluate to 0

  Scenario: TR-02 Confirming staged actions converts them to committed hours
    Given the user stages a 50 hour recruiting action
    When the user confirms staged recruiting actions
    Then staged hours evaluate to 0
    And committed hours evaluate to 50
    And remaining available hours evaluate to 450

  Scenario: TR-03 Overdraft prevention blocks confirmation when allocation exceeds available hours
    When the user attempts to stage a 550 hour recruiting action
    Then system raises an overdraft rejection error
    And committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-04 Exact zero remaining hours confirmation succeeds at full budget
    When the user stages a 500 hour recruiting action
    And the user confirms staged recruiting actions
    Then remaining available hours evaluate to 0
    And committed hours evaluate to 500

  Scenario: TR-05 Editing staged action updates staged delta and restores budget
    Given the user stages a 100 hour recruiting action
    When the user edits staged action cost to 40 hours
    Then staged hours evaluate to 40
    And remaining available hours evaluate to 460

  Scenario: TR-06 Dismissing recruit dossier drawer discards all unconfirmed staged hours
    Given the user stages a 75 hour recruiting action
    When the user dismisses the recruit dossier drawer without confirming
    Then staged hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-07 Removing target from recruiting board refunds current-week committed hours
    Given the user stages a 60 hour recruiting action
    And the user confirms staged recruiting actions
    When the user removes target from recruiting board
    Then committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-08 Booking official visit immediately charges 50 hour deposit to committed bank
    When the user books an official visit costing 50 hours
    Then committed hours evaluate to 50
    And remaining available hours evaluate to 450

  Scenario: TR-09 Same-week manual visit cancellation fully refunds 50 hours to active budget
    Given the user books an official visit costing 50 hours
    When the user manually cancels the visit in the same week
    Then committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-10 Later manual visit cancellation forfeits 50 hour deposit with zero refund
    Given the user books an official visit costing 50 hours
    And recruiting cycle advances to next week
    When the user manually cancels the visit in a subsequent week
    Then active week refund amount evaluates to 0 hours

  Scenario: TR-11 Rival commitment triggers automatic visit cancellation and awards 25 hour relief credit
    Given the user books an official visit costing 50 hours
    When a rival program secures commitment from the scheduled recruit
    Then system cancels the scheduled visit
    And awards an emergency relief credit of 25 hours

  Scenario: TR-12 Recruit lockout triggers automatic visit cancellation and awards 25 hour relief credit
    Given the user books an official visit costing 50 hours
    When the recruit locks out the program from their top list
    Then system cancels the scheduled visit
    And awards an emergency relief credit of 25 hours

  Scenario: TR-13 Relief credit arriving with partially allocated budget stacks on top of available hours
    Given the user stages a 200 hour recruiting action
    And the user confirms staged recruiting actions
    When awards an emergency relief credit of 50 hours
    Then total available hours evaluate to 550
    And remaining available hours evaluate to 350

  Scenario: TR-14 Multiple relief credits in single week stack additively
    When awards an emergency relief credit of 25 hours
    And awards an emergency relief credit of 25 hours
    Then total available hours evaluate to 550
    And remaining available hours evaluate to 550

  Scenario: TR-15 Relief credit arriving at 100 percent cap increases available hours beyond base bank
    When awards an emergency relief credit of 50 hours
    Then total available hours evaluate to 550

  Scenario: TR-16 Relief credits expire strictly at week rollover and never carry over
    Given awards an emergency relief credit of 50 hours
    When recruiting cycle advances to next week
    Then relief credit balance evaluates to 0 hours
    And total available hours evaluate to 500

  Scenario: TR-17 Auto-renewal maintains recurring eligible actions into next week budget
    Given the user stages a 100 hour recurring action
    And the user confirms staged recruiting actions
    When recruiting cycle advances to next week
    Then committed hours evaluate to 100
    And remaining available hours evaluate to 400

  Scenario: TR-18 Ineligible recruits have recurring actions purged prior to auto-renewal
    Given the user stages a 100 hour recurring action for recruit Alpha
    And the user confirms staged recruiting actions
    When recruit Alpha commits to a rival before rollover
    And recruiting cycle advances to next week
    Then committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-19 Auto-renewal under budget reduction prioritizes high-value actions and drops unfunded with alert
    Given base weekly recruiting budget is 200 hours
    And recurring actions of 150 hours and 100 hours are scheduled
    When auto-renewal executes under reduced budget
    Then committed hours evaluate to 150
    And dropped actions trigger advisory notification

  Scenario: TR-20 Weekly home game visitor capacity limits bookings to 4 recruits per week
    When the user attempts to book 5 official visits for single home game
    Then booking 5 is blocked with visitor capacity error

  Scenario: TR-21 Single visit per recruit enforcement blocks second booking in same season
    Given the user books an official visit costing 50 hours for recruit Beta
    When the user attempts to book second visit for recruit Beta in same season
    Then system blocks second visit booking

  Scenario: TR-43 Relief credit raises the overdraft ceiling beyond the base budget
    Given awards an emergency relief credit of 50 hours
    When the user stages a 550 hour recruiting action
    Then no overdraft error is raised
    And staged hours evaluate to 550
    When the user attempts to stage a 1 hour recruiting action
    Then system raises an overdraft rejection error

  Scenario: TR-44 Staging a zero hour action is a harmless no-op
    When the user stages a 0 hour recruiting action
    Then staged hours evaluate to 0
    And remaining available hours evaluate to 500
    And committed hours evaluate to 0

  Scenario: TR-45 Booking exactly 4 visits succeeds and the 5th is blocked by capacity
    When the user books 4 official visits costing 50 hours each
    Then active visit count evaluates to 4
    And committed hours evaluate to 200
    When the user attempts to book 5 official visits for single home game
    Then booking 5 is blocked with visitor capacity error

  Scenario: TR-46 Same-week cancellation refund never drives committed hours below zero
    Given the user books an official visit costing 50 hours
    And committed hours are reduced to 25
    When the user manually cancels the visit in the same week
    Then committed hours evaluate to 0
    And active week refund amount evaluates to 50 hours

  Scenario: TR-47 Unconfirmed staged hours are discarded at week rollover
    Given the user stages a 120 hour recruiting action
    When recruiting cycle advances to next week
    Then unconfirmed staged hours are discarded at rollover
    And committed hours evaluate to 0
    And remaining available hours evaluate to 500

  Scenario: TR-73 Adding a prospect to the recruiting board tracks their star rating
    When prospect Hayes rated 4 stars is added to the recruiting board
    Then the recruiting board prospect count evaluates to 1
    And prospect Hayes is on the recruiting board with 4 stars

  Scenario: TR-74 Adding the same prospect twice is rejected
    Given prospect Hayes rated 4 stars is added to the recruiting board
    When prospect Hayes rated 5 stars is added to the recruiting board
    Then the recruiting board rejects the action with a duplicate prospect error
    And prospect Hayes is on the recruiting board with 4 stars

  Scenario: TR-75 A full 35-prospect recruiting board rejects a new prospect
    Given the recruiting board holds 35 prospects
    When prospect Hayes rated 3 stars is added to the recruiting board
    Then the recruiting board rejects the action with a board full error
    And the recruiting board prospect count evaluates to 35

  Scenario: TR-76 Offering a scholarship to a board prospect records one offer
    Given prospect Hayes rated 4 stars is added to the recruiting board
    When the user offers a scholarship to prospect Hayes
    Then outstanding scholarship offers evaluate to 1

  Scenario: TR-77 Offering a scholarship to a prospect not on the board is rejected
    When the user offers a scholarship to prospect Ghost
    Then the recruiting board rejects the action with a unknown prospect error
    And outstanding scholarship offers evaluate to 0

  Scenario: TR-78 A rescinded offer blocks the prospect from signing
    Given prospect Hayes rated 4 stars is added to the recruiting board
    And the user offers a scholarship to prospect Hayes
    When the user rescinds the scholarship offer to prospect Hayes
    And prospect Hayes signs with the program
    Then the recruiting board rejects the action with a no offer error
    And signing class size evaluates to 0

  Scenario: TR-79 Signing an offered prospect moves them from the board into the class
    Given prospect Hayes rated 4 stars is added to the recruiting board
    And prospect Cole rated 3 stars is added to the recruiting board
    And the user offers a scholarship to prospect Hayes
    And the user offers a scholarship to prospect Cole
    When prospect Hayes signs with the program
    And prospect Cole signs with the program
    Then signing class size evaluates to 2
    And signing class star total evaluates to 7
    And the recruiting board prospect count evaluates to 0

  Scenario: TR-80 A full 25-player signing class rejects another signee
    Given the signing class holds 25 signees
    And prospect Hayes rated 5 stars is added to the recruiting board
    And the user offers a scholarship to prospect Hayes
    When prospect Hayes signs with the program
    Then the recruiting board rejects the action with a class full error
    And signing class size evaluates to 25

  Scenario: TR-81 Signing is blocked when no scholarships remain under the 85-man limit
    Given the roster holds 80 players
    And the signing class holds 5 signees
    And prospect Hayes rated 4 stars is added to the recruiting board
    And the user offers a scholarship to prospect Hayes
    When prospect Hayes signs with the program
    Then the recruiting board rejects the action with a no scholarships error
    And signing class size evaluates to 5

  Scenario: TR-82 Enrolling the signing class adds every signee to the roster as a freshman
    Given the roster holds 60 players
    And prospect Hayes rated 4 stars is added to the recruiting board
    And the user offers a scholarship to prospect Hayes
    And prospect Hayes signs with the program
    When the signing class enrolls
    Then roster size evaluates to 61
    And player Hayes is on the roster as a freshman
    And signing class size evaluates to 0
