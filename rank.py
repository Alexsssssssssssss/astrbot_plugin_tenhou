"""Reconstruct rank/PT using nodocchi's published rules, never an official live value.

Reference: https://nodocchi.moe/tenhoulog/min/base.js (THR.ptcfg,
THR.VARIANTPTCFG) and main.js (assumegrade, _checkseq, _prepareptevents).
Rules inspected on 2026-10-08. No remote JavaScript is executed at runtime.
"""
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


GRADE_NAMES = ('新人', '9级', '8级', '7级', '6级', '5级', '4级', '3级',
               '2级', '1级', '初段', '二段', '三段', '四段', '五段',
               '六段', '七段', '八段', '九段', '十段', '天凤位')
# Values mirror the website's current base configuration. Before its two
# rule-change timestamps, use the corresponding historical configuration.
THRESHOLDS = (20, 20, 20, 20, 40, 60, 80, 100, 100, 100,
              400, 800, 1200, 1600, 2000, 2400, 2800, 3200, 3600, 4000, 4400)
HISTORICAL_THRESHOLDS = (30, 30, 30, 60, 60, 60, 90) + THRESHOLDS[7:]
RULE_CHANGE_2008 = 1220194800
RULE_CHANGE_2017 = 1508792400
ID_EXPIRY_SECONDS = 181 * 86400


class RankUnavailable(ValueError):
    pass


@dataclass
class Rank:
    grade: int = 0
    pt: float = 0
    games: int = 0
    updated: int | None = None

    @property
    def name(self):
        return GRADE_NAMES[self.grade]


def initial_pt(grade):
    return (grade - 9) * 200 if grade >= 10 else 0


def _confirmed_resets(rows):
    """Honor explicit game sequence numbers indicating recycled usernames."""
    ranked = {3: [], 4: []}
    confirmed = []
    for index, row in enumerate(rows):
        if row.get('sctype') not in ('b', 'c'):
            continue
        indices = ranked[row['playernum']]
        indices.append(index)
        if 'seq' not in row:
            continue
        seq = row['seq']
        if type(seq) is not int or seq < 1:
            raise RankUnavailable('对局序号异常')
        if len(indices) > seq:
            offset = len(indices) - seq - 1
            confirmed.append([indices[offset - 1] + 1 if offset > 0 else 0,
                              indices[offset + 1] - 1])
    # As in _checkseq, intersect overlapping reset windows before choosing
    # the first possible record for each reset.
    index = 0
    while index < len(confirmed):
        other = index + 1
        while other < len(confirmed):
            a, b = confirmed[index], confirmed[other]
            if a[1] >= b[0] and b[1] >= a[0]:
                confirmed[index] = [max(a[0], b[0]), min(a[1], b[1])]
                confirmed.pop(other)
            else:
                other += 1
        index += 1
    return {start for start, _ in confirmed}


def _attach_events(rows, events):
    """Apply website PT adjustments to the last preceding record per mode."""
    if not isinstance(events, list):
        raise RankUnavailable('PT 调整记录异常')
    previous = {}
    index = 0
    for event in events:
        if not isinstance(event, dict) or type(event.get('starttime')) is not int:
            raise RankUnavailable('PT 调整记录异常')
        while index < len(rows) and rows[index]['starttime'] <= event['starttime']:
            previous[rows[index]['playernum']] = index
            index += 1
        players = event.get('playernum')
        if not players:
            if index >= len(rows):
                raise RankUnavailable('账号重置后尚无可核对的对局')
            rows[index]['reinit'] = event
        elif players in previous:
            rows[previous[players]].setdefault('ptevents', []).append(event)
        else:
            raise RankUnavailable('PT 调整缺少对应对局')


def estimate_ranks(name, data):
    """Return latest record-based estimates, including username reset handling.

    Missing inputs yield unavailable instead of substituting fake numeric PT.
    Input records are copied because adjustment events are attached locally.
    """
    if not isinstance(data, dict) or data.get('name') != name or not isinstance(data.get('list'), list):
        raise RankUnavailable('缺少有效玩家记录')
    rows = deepcopy(data['list'])
    for row in rows:
        if not isinstance(row, dict) or type(row.get('starttime')) is not int:
            raise RankUnavailable('对局时间异常')
        if type(row.get('playernum')) is not int or row['playernum'] not in (3, 4):
            raise RankUnavailable('对局人数异常')
    rows.sort(key=lambda row: row['starttime'])
    resets = _confirmed_resets(rows)
    if data.get('ptevents'):
        _attach_events(rows, data['ptevents'])
    ranges = data.get('rseq', [])
    # The API also uses scalar rseq=1. The website only reads range arrays.
    if not isinstance(ranges, list):
        ranges = []
    if any(not isinstance(pair, list) or len(pair) != 2
           or any(type(value) is not int for value in pair) for pair in ranges):
        raise RankUnavailable('账号连续性记录异常')
    ranks = {3: Rank(), 4: Rank()}
    previous_time = None
    for index, row in enumerate(rows):
        timestamp = row['starttime']
        reinit = row.get('reinit')
        if reinit is not None and not isinstance(reinit, dict):
            raise RankUnavailable('账号重置信息异常')
        explicit_reset = reinit is not None and not reinit.get('continuous')
        expired = (previous_time is not None and timestamp - previous_time >= ID_EXPIRY_SECONDS
                   and all(rank.grade < 16 for rank in ranks.values())
                   and not any(start <= timestamp <= end for start, end in ranges))
        if index in resets or explicit_reset or (reinit is None and expired):
            ranks = {3: Rank(), 4: Rank()}
        previous_time = timestamp
        players = row['playernum']
        rank = ranks[players]
        if row.get('sctype') not in ('a', 'b', 'c', 'd', 'e', 'f'):
            raise RankUnavailable('未知对局类型')
        if row['sctype'] in ('b', 'c'):
            positions = [i for i in range(1, players + 1) if row.get(f'player{i}') == name]
            level, length = row.get('playerlevel'), row.get('playlength')
            if (len(positions) != 1 or type(level) is not int or level not in range(4)
                    or type(length) is not int or length not in (1, 2)):
                raise RankUnavailable('段位战规则信息缺失或不支持')
            rank.games += 1
            rank.updated = timestamp
            order = positions[0]
            multiplier = 1 if length == 1 or timestamp < RULE_CHANGE_2008 else 1.5
            thresholds = THRESHOLDS if timestamp >= RULE_CHANGE_2017 else HISTORICAL_THRESHOLDS
            gains4 = ((20, 10) if timestamp >= RULE_CHANGE_2017 else (30, 0),
                      (40, 10), (50, 20), (60, 30))
            gains3 = (30, 50, 70, 90)
            # At tenhou-i the website freezes ordinary PT; virtual PT is a
            # separate metric and is deliberately not presented as real PT.
            if rank.grade < 20:
                delta = 0
                if order == players:
                    delta = -max(0, rank.grade - 7) * 10
                elif players == 4 and order <= 2:
                    delta = gains4[level][order - 1]
                elif players == 3 and order == 1:
                    delta = gains3[level]
                rank.pt += delta * multiplier
        else:
            thresholds = THRESHOLDS if timestamp >= RULE_CHANGE_2017 else HISTORICAL_THRESHOLDS
        adjustments = row.get('ptevents', [])
        if not isinstance(adjustments, list):
            raise RankUnavailable('PT 调整记录异常')
        for event in adjustments:
            if not isinstance(event, dict):
                raise RankUnavailable('PT 调整记录异常')
            if 'addpt' in event:
                value = event['addpt']
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise RankUnavailable('PT 调整数值异常')
                rank.pt += value
            elif 'newgrade' in event and 'newpt' in event:
                grade, pt = event['newgrade'], event['newpt']
                if (type(grade) is not int or grade not in range(21)
                        or type(pt) not in (int, float) or not math.isfinite(pt) or pt < 0):
                    raise RankUnavailable('PT 调整数值异常')
                rank.grade, rank.pt = grade, pt
            else:
                raise RankUnavailable('未知 PT 调整类型')
        if rank.grade < 20:
            if rank.pt < 0:
                if rank.grade >= 10:
                    rank.grade -= 1
                    rank.pt = initial_pt(rank.grade)
                else:
                    rank.pt = 0
            elif rank.pt >= thresholds[rank.grade]:
                rank.grade += 1
                rank.pt = initial_pt(rank.grade)
    return ranks


def format_rank_lines(name, data):
    try:
        ranks = estimate_ranks(name, data)
    except RankUnavailable as exc:
        return [f'段位/PT（推算）：暂不可用（{exc}）']
    lines = ['段位/PT（最新牌谱推算，非官方实时值）：']
    for players in (4, 3):
        rank = ranks[players]
        mode = '四麻' if players == 4 else '三麻'
        if rank.updated is None:
            lines.append(f'{mode}：无可用段位战记录，无法推算')
            continue
        date = datetime.fromtimestamp(rank.updated, timezone(timedelta(hours=8)))
        pt = '不适用（天凤位不计普通段位 PT）' if rank.grade == 20 else f'{rank.pt:g} PT'
        lines.append(f'{mode}：{rank.name} / {pt}（截至 {date:%Y-%m-%d %H:%M} UTC+8）')
    lines.append('根据收录段位战重建；漏收、账号重置或未同步对局可能造成偏差。')
    return lines
