"""Regression tests for recruiting prospects, scholarship offers and signing
classes (TR-73..TR-82). Stdlib only."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import RecruitingBoard, Roster, Player, BOARD_LIMIT, SIGNING_CLASS_LIMIT, MAX_ROSTER


def roster_of(n):
    r = Roster()
    for i in range(1, n + 1):
        r.add(Player(f"P{i}"))
    return r


def offered(board, name, stars=3):
    board.add_prospect(name, stars)
    board.offer(name)


class TestRecruitingBoard(unittest.TestCase):
    def test_prospect_added_with_stars(self):
        """TR-73: a new prospect is tracked with their star rating."""
        b = RecruitingBoard()
        b.add_prospect("Hayes", 4)
        self.assertEqual(b.prospects["Hayes"].stars, 4)
        self.assertIsNone(b.error)

    def test_star_rating_out_of_range_rejected(self):
        """TR-73: only 1-5 star ratings are accepted."""
        b = RecruitingBoard()
        for bad in (0, 6):
            b.add_prospect("X", bad)
            self.assertEqual(b.error, "INVALID_STARS")
        self.assertEqual(b.prospects, {})

    def test_duplicate_prospect_keeps_original(self):
        """TR-74: re-adding a prospect errors and keeps the first rating."""
        b = RecruitingBoard()
        b.add_prospect("Hayes", 4)
        b.add_prospect("Hayes", 5)
        self.assertEqual(b.error, "DUPLICATE_PROSPECT")
        self.assertEqual(b.prospects["Hayes"].stars, 4)

    def test_signed_prospect_cannot_be_re_added(self):
        """TR-74: a prospect who already signed can't reappear on the board."""
        b = RecruitingBoard()
        offered(b, "Hayes")
        b.sign("Hayes", Roster())
        b.add_prospect("Hayes", 3)
        self.assertEqual(b.error, "DUPLICATE_PROSPECT")
        self.assertNotIn("Hayes", b.prospects)

    def test_board_full_at_limit(self):
        """TR-75: the board holds 35 prospects; the 36th is rejected."""
        b = RecruitingBoard()
        for i in range(BOARD_LIMIT):
            b.add_prospect(f"R{i}", 3)
        self.assertIsNone(b.error)
        b.add_prospect("Hayes", 3)
        self.assertEqual(b.error, "BOARD_FULL")
        self.assertEqual(len(b.prospects), BOARD_LIMIT)


class TestScholarshipOffers(unittest.TestCase):
    def test_offer_recorded(self):
        """TR-76: offering a board prospect counts one outstanding offer."""
        b = RecruitingBoard()
        offered(b, "Hayes")
        self.assertEqual(b.offers, 1)

    def test_double_offer_rejected(self):
        """TR-76: a second offer to the same prospect errors and still counts once."""
        b = RecruitingBoard()
        offered(b, "Hayes")
        b.offer("Hayes")
        self.assertEqual(b.error, "ALREADY_OFFERED")
        self.assertEqual(b.offers, 1)

    def test_offer_to_unknown_prospect(self):
        """TR-77: offering someone not on the board is rejected."""
        b = RecruitingBoard()
        b.offer("Ghost")
        self.assertEqual(b.error, "UNKNOWN_PROSPECT")
        self.assertEqual(b.offers, 0)

    def test_rescinded_offer_blocks_signing(self):
        """TR-78: after rescinding, signing fails with a no-offer error."""
        b = RecruitingBoard()
        offered(b, "Hayes")
        b.rescind("Hayes")
        self.assertEqual(b.offers, 0)
        b.sign("Hayes", Roster())
        self.assertEqual(b.error, "NO_OFFER")
        self.assertEqual(b.signed, [])
        self.assertIn("Hayes", b.prospects)

    def test_rescind_without_offer(self):
        """TR-78: rescinding an offer that was never made is rejected."""
        b = RecruitingBoard()
        b.add_prospect("Hayes", 4)
        b.rescind("Hayes")
        self.assertEqual(b.error, "NO_OFFER")


class TestSigningClass(unittest.TestCase):
    def test_signing_moves_prospect_into_class(self):
        """TR-79: signees leave the board; class stars add up."""
        b = RecruitingBoard()
        offered(b, "Hayes", 4)
        offered(b, "Cole", 3)
        b.sign("Hayes", Roster())
        b.sign("Cole", Roster())
        self.assertEqual([p.name for p in b.signed], ["Hayes", "Cole"])
        self.assertEqual(b.class_stars, 7)
        self.assertEqual(b.prospects, {})
        self.assertEqual(b.offers, 0)

    def test_class_full_at_limit(self):
        """TR-80: a 25-player class rejects the 26th signee, who stays on the board."""
        b, r = RecruitingBoard(), Roster()
        for i in range(SIGNING_CLASS_LIMIT):
            offered(b, f"S{i}")
            b.sign(f"S{i}", r)
        self.assertIsNone(b.error)
        offered(b, "Hayes", 5)
        b.sign("Hayes", r)
        self.assertEqual(b.error, "CLASS_FULL")
        self.assertEqual(len(b.signed), SIGNING_CLASS_LIMIT)
        self.assertIn("Hayes", b.prospects)

    def test_no_scholarships_left(self):
        """TR-81: roster plus class can't exceed 85; the last open slot can be signed."""
        b, r = RecruitingBoard(), roster_of(MAX_ROSTER - 1)
        offered(b, "Last")
        b.sign("Last", r)
        self.assertIsNone(b.error)
        offered(b, "Hayes")
        b.sign("Hayes", r)
        self.assertEqual(b.error, "NO_SCHOLARSHIPS")
        self.assertEqual(len(b.signed), 1)

    def test_enroll_adds_freshmen_and_empties_class(self):
        """TR-82: signees join the roster as freshmen and the class empties."""
        b, r = RecruitingBoard(), roster_of(60)
        offered(b, "Hayes", 4)
        b.sign("Hayes", r)
        b.enroll(r)
        self.assertEqual(r.count, 61)
        self.assertEqual(r.players["Hayes"].year, 1)
        self.assertEqual(b.signed, [])

    def test_enroll_is_all_or_nothing(self):
        """TR-82: if the roster grew past room for the class, nobody enrolls."""
        b, r = RecruitingBoard(), roster_of(83)
        offered(b, "A"); b.sign("A", r)
        offered(b, "B"); b.sign("B", r)
        r.add(Player("Walkon"))
        b.enroll(r)
        self.assertEqual(b.error, "NO_SCHOLARSHIPS")
        self.assertEqual(r.count, 84)
        self.assertEqual(len(b.signed), 2)


if __name__ == "__main__":
    unittest.main()
