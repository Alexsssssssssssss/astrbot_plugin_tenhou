import copy
import unittest
from rank import ID_EXPIRY_SECONDS, RankUnavailable, estimate_ranks, format_rank_lines

NOW = 1700000000


def game(players=4, order=1, level=0, length=1, time=NOW, kind='b'):
    row = {'playernum': players, 'sctype': kind, 'playerlevel': level,
           'playlength': length, 'starttime': time}
    for i in range(1, players + 1):
        row[f'player{i}'] = '玩家' if i == order else f'other{i}'
    return row


def seeded(grade, pt, *rows):
    first = game(time=rows[0]['starttime']-1, kind='a')
    first['ptevents'] = [{'newgrade': grade, 'newpt': pt}]
    return {'name': '玩家', 'list': [first, *rows]}


class RankTests(unittest.TestCase):
    def test_newbie_promotion_and_no_mutation(self):
        data = {'name': '玩家', 'list': [game()]}
        before = copy.deepcopy(data)
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.name, r.pt, r.games), ('9级', 0, 1))
        self.assertEqual(data, before)

    def test_half_length_gain(self):
        r = estimate_ranks('玩家', seeded(10, 200, game(order=2, level=3, length=2)))[4]
        self.assertEqual((r.name, r.pt), ('初段', 245))

    def test_promotion(self):
        r = estimate_ranks('玩家', seeded(10, 390, game(level=2)))[4]
        self.assertEqual((r.name, r.pt), ('二段', 400))

    def test_demotion_and_kyu_floor(self):
        r = estimate_ranks('玩家', seeded(11, 0, game(order=4)))[4]
        self.assertEqual((r.name, r.pt), ('初段', 200))
        r = estimate_ranks('玩家', seeded(9, 0, game(order=4)))[4]
        self.assertEqual((r.name, r.pt), ('1级', 0))

    def test_three_player_and_independent_modes(self):
        rows = [game(players=3, level=3), game(order=3, time=NOW+1)]
        r = estimate_ranks('玩家', {'name': '玩家', 'list': rows})
        self.assertEqual((r[3].grade, r[3].pt, r[3].games), (1, 0, 1))
        self.assertEqual((r[4].grade, r[4].pt, r[4].games), (0, 0, 1))

    def test_historical_rules(self):
        for row, expected in [(game(time=1200000000, length=2, order=4), 170),
                              (game(time=1400000000, order=2), 200),
                              (game(order=2), 210)]:
            r = estimate_ranks('玩家', seeded(10, 200, row))[4]
            self.assertEqual(r.pt, expected)

    def test_non_ranked_games(self):
        for kind in ('a', 'd', 'e', 'f'):
            r = estimate_ranks('玩家', seeded(11, 400, game(kind=kind)))[4]
            self.assertEqual((r.grade, r.pt, r.games, r.updated), (11, 400, 0, None))

    def test_expiry_and_continuity(self):
        later = NOW + ID_EXPIRY_SECONDS + 1
        data = seeded(10, 200, game(order=3), game(time=later, order=3))
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.grade, r.pt, r.games), (0, 0, 1))
        data['rseq'] = [[NOW, later]]
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.grade, r.pt, r.games), (10, 200, 2))

    def test_seven_dan_does_not_expire(self):
        data = seeded(16, 1400, game(order=3), game(time=NOW+ID_EXPIRY_SECONDS+1, order=3))
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.grade, r.pt), (16, 1400))

    def test_pt_adjustment(self):
        data = seeded(10, 200, game(order=3))
        data['ptevents'] = [{'starttime': NOW+1, 'playernum': 4, 'addpt': 80}]
        self.assertEqual(estimate_ranks('玩家', data)[4].pt, 280)

    def test_explicit_reset(self):
        row = game(order=3)
        row['reinit'] = {}
        r = estimate_ranks('玩家', seeded(10, 200, row))[4]
        self.assertEqual((r.grade, r.pt), (0, 0))

    def test_sequence_reset(self):
        rows = [game(time=NOW), game(time=NOW+1), game(time=NOW+2)]
        rows[-1]['seq'] = 1
        r = estimate_ranks('玩家', {'name': '玩家', 'list': rows})[4]
        self.assertEqual((r.grade, r.pt, r.games), (2, 0, 2))

    def test_tenhou_i_does_not_show_virtual_pt(self):
        data = seeded(19, 3990, game(level=3, length=2))
        data['list'].append(game(time=NOW+1, order=4))
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.grade, r.pt), (20, 2200))
        text = '\n'.join(format_rank_lines('玩家', data))
        self.assertIn('天凤位 / PT 不适用', text)
        self.assertNotIn('2200 PT', text)

    def test_missing_rules_unavailable(self):
        row = game()
        del row['playerlevel']
        data = {'name': '玩家', 'list': [row]}
        with self.assertRaises(RankUnavailable):
            estimate_ranks('玩家', data)
        self.assertIn('暂不可用', '\n'.join(format_rank_lines('玩家', data)))

    def test_compact_rank_labels_keep_estimate_marker(self):
        data = {'name': '玩家', 'list': [game(), game(time=NOW+86400, kind='a')]}
        text = '\n'.join(format_rank_lines('玩家', data))
        self.assertIn('段位/PT（推算）', text)
        self.assertNotIn('UTC+8', text)
        self.assertNotIn('可能造成偏差', text)
        self.assertIn('三麻：无可用段位战记录', text)

    def test_peak_survives_pt_loss(self):
        data = seeded(11, 400, game(), game(order=4, time=NOW+1))
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.grade, r.pt), (11, 380))
        self.assertEqual((r.highest_grade, r.highest_pt), (11, 420))

    def test_peak_pt_is_paired_with_highest_grade(self):
        data = seeded(11, 750, game(), game(level=2, time=NOW+1))
        r = estimate_ranks('玩家', data)[4]
        self.assertEqual((r.highest_grade, r.highest_pt), (12, 600))

    def test_highest_rate_includes_latest_metadata(self):
        rows = [game(time=NOW), game(time=NOW+1), game(time=NOW+2)]
        for row, rate in zip(rows, (2500, 1800, 1750)):
            row['rate'] = rate
        data = {'name': '玩家', 'list': rows, 'rate': {'4': 1820}}
        r = estimate_ranks('玩家', data)[4]
        # First pre-game R is discarded, as in the website's initial reset.
        self.assertEqual(r.highest_rate, 1820)
        data['rate']['4'] = 1700
        self.assertEqual(estimate_ranks('玩家', data)[4].highest_rate, 1800)

    def test_missing_historical_rate_is_not_replaced_with_current(self):
        data = {'name': '玩家', 'list': [game(), game(time=NOW+1)], 'rate': {'4': 1820}}
        self.assertIsNone(estimate_ranks('玩家', data)[4].highest_rate)

    def test_reset_clears_peak_rank_and_rate(self):
        rows = [game(time=NOW), game(time=NOW+1), game(time=NOW+2), game(time=NOW+3)]
        rows[1]['rate'] = 2000
        rows[2]['reinit'] = {}
        rows[2]['rate'] = 2100
        rows[3]['rate'] = 1600
        r = estimate_ranks('玩家', {'name': '玩家', 'list': rows})[4]
        self.assertEqual((r.highest_grade, r.highest_pt, r.highest_rate), (2, 0, 1600))

    def test_peak_modes_are_independent(self):
        rows = [game(time=NOW), game(time=NOW+1),
                game(players=3, time=NOW+2), game(players=3, time=NOW+3)]
        rows[1]['rate'] = 1800
        rows[2]['rate'] = 1600
        rows[3]['rate'] = 1700
        ranks = estimate_ranks('玩家', {'name': '玩家', 'list': rows})
        self.assertEqual(ranks[4].highest_rate, 1800)
        self.assertEqual(ranks[3].highest_rate, 1700)
