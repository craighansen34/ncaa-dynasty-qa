# Feature: Player Management, Roster Changes, and Season Progression

Covers roster-cap enforcement, player departures (cuts and transfer portal),
redshirt eligibility preservation, offseason year advancement and senior
graduation, depth-chart promotion, and season record tracking.

  Scenario: TR-51 Cutting a player frees a roster slot below the 85-man cap
    Given the roster holds 85 players
    When the user cuts player P1 from the roster
    Then roster size evaluates to 84
    And player P1 is no longer on the roster

  Scenario: TR-52 Signing a player at the 85-man cap is blocked with roster full error
    Given the roster holds 85 players
    When the user attempts to sign player NewGuy to a full roster
    Then system raises a roster full error
    And roster size evaluates to 85
    And player NewGuy is no longer on the roster

  Scenario: TR-53 Transfer portal departure removes the player and decrements roster count
    Given the roster holds 70 players
    When player P1 enters the transfer portal
    Then roster size evaluates to 69
    And player P1 is no longer on the roster

  Scenario: TR-54 Redshirting a freshman preserves a year of eligibility across the offseason
    Given the roster holds 60 players
    And player P1 is a freshman
    When the user applies a redshirt to player P1
    And the season ends and the offseason advance executes
    Then player P1 remains on the roster
    And player P1 eligibility year evaluates to 1

  Scenario: TR-55 Seniors graduate and are removed from the roster at offseason advance
    Given the roster holds 60 players
    And player P1 is a senior
    When the season ends and the offseason advance executes
    Then player P1 is no longer on the roster
    And roster size evaluates to 59

  Scenario: TR-56 Returning players advance one eligibility year at offseason advance
    Given the roster holds 60 players
    And player P1 is a freshman
    When the season ends and the offseason advance executes
    Then player P1 remains on the roster
    And player P1 eligibility year evaluates to 2

  Scenario: TR-57 Promoting a bench player to starter updates depth chart status
    Given the roster holds 60 players
    When player P1 is promoted to starter
    Then player P1 starter status evaluates to true

  Scenario: TR-58 Season record tracks wins and losses across a 12 game schedule
    Given the roster holds 60 players
    When the team wins 9 games and loses 3
    Then the season record evaluates to 9 wins and 3 losses
    And games played evaluates to 12

  Scenario: TR-59 Season rollover archives the final record and resets the season record
    Given the roster holds 60 players
    When the team wins 9 games and loses 3
    And the season rollover executes
    Then season 1 is archived with 9 wins and 3 losses
    And the season record resets to 0 wins and 0 losses
    And the current season evaluates to 2

  Scenario: TR-60 Season rollover graduates seniors and advances returning players
    Given the roster holds 60 players
    And player P1 is a senior
    And player P2 is a freshman
    When the season rollover executes
    Then player P1 is no longer on the roster
    And player P2 eligibility year evaluates to 2
    And roster size evaluates to 59

  Scenario: TR-61 Season rollover resets starters and clears the roster full error
    Given the roster holds 85 players
    When player P2 is promoted to starter
    And the user attempts to sign player NewGuy to a full roster
    And the season rollover executes
    Then player P2 starter status evaluates to false
    And the roster full error is cleared

  Scenario: TR-62 Incoming transfer on the deadline week is accepted
    Given the roster holds 70 players
    And the current week is 8
    When the user attempts to add incoming transfer Portal1
    Then player Portal1 is on the roster
    And roster size evaluates to 71

  Scenario: TR-63 Incoming transfer one week after the deadline is blocked
    Given the roster holds 70 players
    And the current week is 9
    When the user attempts to add incoming transfer Portal1
    Then system raises a transfer deadline error
    And player Portal1 is no longer on the roster
    And roster size evaluates to 70

  Scenario: TR-64 Season rollover reopens the transfer window at week 1
    Given the roster holds 70 players
    And the current week is 12
    When the season rollover executes
    And the user attempts to add incoming transfer Portal1
    Then the current week evaluates to 1
    And player Portal1 is on the roster

  Scenario: TR-65 Injuring a starter removes them from the starting lineup
    Given the roster holds 60 players
    And player P1 is promoted to starter
    When player P1 suffers an injury of 3 weeks
    Then player P1 starter status evaluates to false
    And player P1 injury weeks remaining evaluate to 3

  Scenario: TR-66 Injured player cannot be promoted until fully healed
    Given the roster holds 60 players
    And player P1 suffers an injury of 2 weeks
    When the user attempts to promote injured player P1
    Then system raises a player injured error
    And player P1 starter status evaluates to false
    When 2 game weeks pass
    And player P1 is promoted to starter
    Then player P1 starter status evaluates to true

  Scenario: TR-67 Revising an injury replaces the timeline instead of adding to it
    Given the roster holds 60 players
    And player P1 suffers an injury of 6 weeks
    When the injury for player P1 is revised to 2 weeks
    And 1 game weeks pass
    Then player P1 injury weeks remaining evaluate to 1
    When the injury for player P1 is revised to 0 weeks
    Then player P1 injury weeks remaining evaluate to 0

  Scenario: TR-68 Injury healing stops at zero and never goes negative
    Given the roster holds 60 players
    And player P1 suffers an injury of 1 weeks
    When 3 game weeks pass
    Then player P1 injury weeks remaining evaluate to 0
    And the current week evaluates to 4

  Scenario: TR-69 Injuring a player who is not on the roster is rejected
    Given the roster holds 60 players
    When the user attempts to injure unknown player Ghost
    Then system raises an unknown player error
    And roster size evaluates to 60

  Scenario: TR-70 A ten-win season raises prestige but never above 5 stars
    Given the roster holds 60 players
    And program prestige is 5 stars
    And the team wins 10 games and loses 2
    When the season rollover executes
    Then program prestige evaluates to 5 stars
    And season 1 is archived with 10 wins and 2 losses

  Scenario: TR-71 A losing dynasty season lowers prestige but never below half a star and heals injuries
    Given the roster holds 60 players
    And program prestige is 0.5 stars
    And player P2 suffers an injury of 5 weeks
    And the team wins 3 games and loses 9
    When the season rollover executes
    Then program prestige evaluates to 0.5 stars
    And player P2 injury weeks remaining evaluate to 0
    And the current season evaluates to 2

  Scenario: TR-72 Advancing past the final regular-season week is rejected
    Given the roster holds 60 players
    And the current week is 12
    When the user attempts to advance past the final week
    Then system raises a season over error
    And the current week evaluates to 12

  Scenario: TR-83 Injury status categories track the recovery timeline
    Given the roster holds 1 players
    Then player P1 injury status evaluates to healthy
    When player P1 suffers an injury of 3 weeks
    Then player P1 injury status evaluates to out
    When the injury for player P1 is revised to 1 weeks
    Then player P1 injury status evaluates to questionable
    When the injury for player P1 is revised to 0 weeks
    Then player P1 injury status evaluates to healthy

  Scenario: TR-84 A player recovers exactly on schedule
    Given the roster holds 1 players
    And player P1 suffers an injury of 3 weeks
    When 1 game weeks pass
    Then player P1 injury weeks remaining evaluate to 2
    When 1 game weeks pass
    Then player P1 injury weeks remaining evaluate to 1
    And player P1 injury status evaluates to questionable
    When 1 game weeks pass
    Then player P1 injury weeks remaining evaluate to 0
    And player P1 injury status evaluates to healthy

  Scenario: TR-85 The injury report lists every injured player with weeks remaining
    Given the roster holds 3 players
    And player P1 suffers an injury of 4 weeks
    And player P3 suffers an injury of 1 weeks
    Then the injury report lists 2 injured players
    And the injury report shows player P1 with 4 weeks remaining
    And the injury report shows player P3 with 1 weeks remaining

  Scenario: TR-86 A healthy backup is elevated to replace an injured starter
    Given the roster holds 2 players
    And player P1 is promoted to starter
    And player P1 suffers an injury of 2 weeks
    When backup player P2 is elevated to replace injured starter P1
    Then player P2 starter status evaluates to true
    And player P1 starter status evaluates to false

  Scenario: TR-87 An injured backup cannot be elevated to the starting lineup
    Given the roster holds 2 players
    And player P1 is promoted to starter
    And player P1 suffers an injury of 2 weeks
    And player P2 suffers an injury of 1 weeks
    When the user attempts to elevate injured backup P2 for starter P1
    Then system raises a player injured error
    And player P2 starter status evaluates to false

  Scenario: TR-88 A recovered player can return to the starting lineup
    Given the roster holds 1 players
    And player P1 is promoted to starter
    And player P1 suffers an injury of 2 weeks
    And player P1 starter status evaluates to false
    When 2 game weeks pass
    Then player P1 injury status evaluates to healthy
    When player P1 is promoted to starter
    Then player P1 starter status evaluates to true

  Scenario: TR-89 Demoting a healthy starter moves them to the bench
    Given the roster holds 1 players
    And player P1 is promoted to starter
    When player P1 is demoted to the bench
    Then player P1 starter status evaluates to false
    And player P1 remains on the roster

  Scenario: TR-90 Recording the same injury length again preserves the timeline
    Given the roster holds 1 players
    And player P1 suffers an injury of 3 weeks
    When 1 game weeks pass
    Then player P1 injury weeks remaining evaluate to 2
    When the injury for player P1 is recorded again as 2 weeks
    Then player P1 injury weeks remaining evaluate to 2

  Scenario: TR-91 A late-season injury heals fully during the offseason rollover
    Given the roster holds 1 players
    And the current week is 11
    And player P1 suffers an injury of 3 weeks
    When 1 game weeks pass
    Then the current week evaluates to 12
    And player P1 injury weeks remaining evaluate to 2
    When the season rollover executes
    Then player P1 injury weeks remaining evaluate to 0
    And player P1 injury status evaluates to healthy

  Scenario: TR-92 The injury report is empty when every player is healthy
    Given the roster holds 3 players
    Then the injury report is empty
    When player P2 suffers an injury of 2 weeks
    Then the injury report lists 1 injured players
    When the injury for player P2 is revised to 0 weeks
    Then the injury report is empty

## EA College Football 26 rules: recruiting hours, scholarship offers, SEC standings

  Scenario: TR-93 Weekly recruiting hours follow program prestige with a preseason bonus
    Given a 5-star program starts recruiting
    Then available recruiting hours evaluate to 1250
    When a new recruiting week starts
    Then available recruiting hours evaluate to 1000
    Given a 0.5-star program starts recruiting
    When a new recruiting week starts
    Then available recruiting hours evaluate to 300

  Scenario: TR-94 Unused recruiting hours do not carry over to the next week
    Given a 3-star program starts recruiting
    When a new recruiting week starts
    And the coach spends 50 hours on prospect Smith
    Then available recruiting hours evaluate to 550
    When a new recruiting week starts
    Then available recruiting hours evaluate to 600

  Scenario: TR-95 A prospect can receive at most 50 hours per week
    Given a 3-star program starts recruiting
    When a new recruiting week starts
    And the coach spends 40 hours on prospect Smith
    And the coach spends 20 hours on prospect Smith
    Then recruiting rejects the action with a prospect hour cap error
    And available recruiting hours evaluate to 560
    When a new recruiting week starts
    And the coach spends 50 hours on prospect Smith
    Then available recruiting hours evaluate to 550

  Scenario: TR-96 Spending more hours than remain this week is rejected
    Given a 0.5-star program starts recruiting
    When a new recruiting week starts
    And the coach spends 50 hours on prospect A1
    And the coach spends 50 hours on prospect A2
    And the coach spends 50 hours on prospect A3
    And the coach spends 50 hours on prospect A4
    And the coach spends 50 hours on prospect A5
    And the coach spends 45 hours on prospect A6
    Then available recruiting hours evaluate to 5
    When the coach spends 10 hours on prospect A7
    Then recruiting rejects the action with a not enough hours error
    And available recruiting hours evaluate to 5

  Scenario: TR-97 A scholarship offer costs 5 hours and uses one of 35 offers
    Given a 3-star program starts recruiting
    When a new recruiting week starts
    And the coach offers a scholarship to prospect Smith
    Then available recruiting hours evaluate to 595
    And scholarship offers remaining evaluate to 34
    When the coach offers a scholarship to prospect Smith
    Then recruiting rejects the action with a already offered error
    And scholarship offers remaining evaluate to 34

  Scenario: TR-98 A 36th scholarship offer is rejected until the next season
    Given a 5-star program starts recruiting
    When the coach offers scholarships to 35 prospects
    Then scholarship offers remaining evaluate to 0
    When the coach offers a scholarship to prospect Extra
    Then recruiting rejects the action with a no offers left error
    When a new recruiting season starts
    Then scholarship offers remaining evaluate to 35

  Scenario: TR-99 Prestige moves in half-star steps and sets next season's recruiting hours
    Given the roster holds 60 players
    And program prestige is 3 stars
    And the team wins 11 games and loses 1
    When the season rollover executes
    Then program prestige evaluates to 3 stars
    Given the team wins 11 games and loses 1
    When the season rollover executes
    Then program prestige evaluates to 3.5 stars
    Given recruiting hours are set from program prestige
    When a new recruiting week starts
    Then available recruiting hours evaluate to 700

  Scenario: TR-100 SEC standings rank teams by conference winning percentage
    Given Georgia beats Alabama in conference play
    And Georgia beats Texas in conference play
    And Alabama beats Texas in conference play
    Then the SEC standings evaluate to Georgia, Alabama, Texas

  Scenario: TR-101 A two-team SEC tie is broken by head-to-head result
    Given Texas beats Georgia in conference play
    And Georgia beats Auburn in conference play
    And Texas beats Auburn in conference play
    And Georgia beats Florida in conference play
    And Florida beats Texas in conference play
    Then the SEC standings evaluate to Texas, Georgia, Florida, Auburn

  Scenario: TR-102 A tie between SEC teams that did not meet is broken by record against common opponents
    Given Alabama beats Auburn in conference play
    And Alabama beats LSU in conference play
    And Missouri beats Alabama in conference play
    And Georgia beats Auburn in conference play
    And LSU beats Georgia in conference play
    And Georgia beats Kentucky in conference play
    Then the SEC standings evaluate to Missouri, Alabama, Georgia, LSU, Auburn, Kentucky

  Scenario: TR-103 Team prestige is the composite of the school report card
    Given the school report card is all B
    Then program prestige evaluates to 3 stars
    Given school grade academic_prestige is A+
    Then program prestige evaluates to 3 stars
    Given school grade athletic_facilities is A+
    Then program prestige evaluates to 3.5 stars

  Scenario: TR-104 A ten-win season raises Championship Contender and Brand Exposure one step
    Given the roster holds 60 players
    And the school report card is all B
    And the team wins 10 games and loses 2
    When the season rollover executes
    Then school grade championship_contender evaluates to B+
    And school grade brand_exposure evaluates to B+
    And school grade program_tradition evaluates to B
    And program prestige evaluates to 3 stars

  Scenario: TR-105 A two-win season lowers every result-driven grade and a middling season changes none
    Given the roster holds 60 players
    And the school report card is all B
    And the team wins 2 games and loses 10
    When the season rollover executes
    Then school grade championship_contender evaluates to B-
    And school grade brand_exposure evaluates to B-
    And school grade program_tradition evaluates to B-
    Given the team wins 6 games and loses 6
    When the season rollover executes
    Then school grade championship_contender evaluates to B-
    And school grade brand_exposure evaluates to B-
    And school grade program_tradition evaluates to B-

  Scenario: TR-106 School grades stay between F and A+ and prestige never drops below half a star
    Given the roster holds 60 players
    And the school report card is all F
    Then program prestige evaluates to 0.5 stars
    Given school grade championship_contender is A+
    And the team wins 12 games and loses 0
    When the season rollover executes
    Then school grade championship_contender evaluates to A+
    Given the team wins 0 games and loses 12
    When the season rollover executes
    Then school grade brand_exposure evaluates to F
    And program prestige evaluates to 0.5 stars

  Scenario: TR-107 Static school grades never change with results
    Given the roster holds 60 players
    And the school report card is all B
    And the team wins 12 games and loses 0
    When the season rollover executes
    Then school grade academic_prestige evaluates to B
    And school grade coach_stability evaluates to B
    And school grade stadium_atmosphere evaluates to B
    And school grade program_tradition evaluates to B+

  Scenario: TR-108 Retrying a rollover does not apply grade changes twice
    Given the roster holds 60 players
    And the school report card is all B
    And the team wins 10 games and loses 2
    When the season rollover executes
    And the season 1 rollover is retried
    Then school grade championship_contender evaluates to B+
    And the current season evaluates to 2
