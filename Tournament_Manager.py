# Tournament_Manager.py (Full Code, Updated for Custom Brackets)

import sqlite3
import os
import datetime
import random
import json
from tabulate import tabulate
from colorama import Fore, Style, init
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch



# --- INITIALIZATION ---
init(autoreset=True)
DB_NAME = "tournament_database.db"

# <<< ORDINAL TITLE OF PLACE HOLDERS: >>>
def to_ordinal(n):
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix} Place"


# --- DATABASE MANAGER CLASS (No changes here) ---
class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tournaments (
                                tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                season_number INTEGER NOT NULL,
                                created_date TEXT,
                                settings TEXT 
                             )''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS teams (
                                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                tournament_id INTEGER NOT NULL,
                                team_name TEXT NOT NULL, 
                                group_name TEXT,
                                matches_played INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                                draws INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
                                goals_for INTEGER DEFAULT 0, goals_against INTEGER DEFAULT 0,
                                FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
                                UNIQUE(tournament_id, team_name)
                             )''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS fixtures (
                                match_no INTEGER PRIMARY KEY AUTOINCREMENT,
                                tournament_id INTEGER NOT NULL,
                                team1_id INTEGER, team2_id INTEGER,
                                placeholder_t1 TEXT, placeholder_t2 TEXT,
                                team1_goals INTEGER, team2_goals INTEGER,
                                team1_pso INTEGER, team2_pso INTEGER,
                                status TEXT DEFAULT 'Not Played', stage TEXT, round_in_stage INTEGER,
                                FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
                                FOREIGN KEY(team1_id) REFERENCES teams(team_id),
                                FOREIGN KEY(team2_id) REFERENCES teams(team_id)
                             )''')
        self.conn.commit()

    def recalculate_team_stats(self, team_id):
        self.cursor.execute("UPDATE teams SET matches_played=0, wins=0, draws=0, losses=0, goals_for=0, goals_against=0 WHERE team_id = ?", (team_id,))
        self.cursor.execute("SELECT * FROM fixtures WHERE (team1_id = ? OR team2_id = ?) AND status = 'Played' AND (stage LIKE 'Group%' OR stage = 'League')", (team_id, team_id))
        played_fixtures = self.cursor.fetchall()
        stats = {'mp': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0}
        for match in played_fixtures:
            stats['mp'] += 1
            if match['team1_id'] == team_id:
                stats['gf'] += match['team1_goals']
                stats['ga'] += match['team2_goals']
                if match['team1_goals'] > match['team2_goals']: stats['w'] += 1
                elif match['team1_goals'] == match['team2_goals']: stats['d'] += 1
                else: stats['l'] += 1
            else:
                stats['gf'] += match['team2_goals']
                stats['ga'] += match['team1_goals']
                if match['team2_goals'] > match['team1_goals']: stats['w'] += 1
                elif match['team1_goals'] == match['team2_goals']: stats['d'] += 1
                else: stats['l'] += 1
        self.cursor.execute("UPDATE teams SET matches_played=?, wins=?, draws=?, losses=?, goals_for=?, goals_against=? WHERE team_id = ?", (stats['mp'], stats['w'], stats['d'], stats['l'], stats['gf'], stats['ga'], team_id))
        self.conn.commit()
        
    def create_new_tournament(self, season_number, settings_json):
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute("INSERT INTO tournaments (season_number, created_date, settings) VALUES (?, ?, ?)", (season_number, date, settings_json))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_tournaments(self):
        self.cursor.execute("SELECT tournament_id, season_number, created_date FROM tournaments ORDER BY season_number DESC")
        return self.cursor.fetchall()

    def get_tournament_by_id(self, tournament_id):
        self.cursor.execute("SELECT * FROM tournaments WHERE tournament_id = ?", (tournament_id,))
        return self.cursor.fetchone()

    def delete_tournament(self, tournament_id):
        self.cursor.execute("DELETE FROM tournaments WHERE tournament_id = ?", (tournament_id,))
        self.conn.commit()
        
    def add_team(self, tournament_id, team_name, group_name):
        try:
            self.cursor.execute("INSERT INTO teams (tournament_id, team_name, group_name) VALUES (?, ?, ?)", (tournament_id, team_name, group_name))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def add_fixture(self, tournament_id, t1_id, t2_id, p1, p2, stage, round_in_stage):
        self.cursor.execute("INSERT INTO fixtures (tournament_id, team1_id, team2_id, placeholder_t1, placeholder_t2, stage, round_in_stage) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (tournament_id, t1_id, t2_id, p1, p2, stage, round_in_stage))
        self.conn.commit()

    def get_all_fixtures(self, tournament_id):
        self.cursor.execute("SELECT * FROM fixtures WHERE tournament_id = ? ORDER BY match_no ASC", (tournament_id,))
        rows = self.cursor.fetchall()
        matches = []
        for r in rows:
            t1 = self.get_team_by_id(r['team1_id']) if r['team1_id'] is not None else None
            t2 = self.get_team_by_id(r['team2_id']) if r['team2_id'] is not None else None
            matches.append(Match(db_manager=self, **dict(r), team1=t1, team2=t2))
        return matches

    def get_fixture_by_id(self, match_no):
        self.cursor.execute("SELECT * FROM fixtures WHERE match_no=?", (match_no,))
        r = self.cursor.fetchone()
        if not r: return None
        t1 = self.get_team_by_id(r['team1_id']) if r['team1_id'] is not None else None
        t2 = self.get_team_by_id(r['team2_id']) if r['team2_id'] is not None else None
        return Match(db_manager=self, **dict(r), team1=t1, team2=t2)
    
    def get_all_teams(self, tournament_id):
        self.cursor.execute("SELECT * FROM teams WHERE tournament_id=?", (tournament_id,))
        rows = self.cursor.fetchall()
        return [Team(**dict(r)) for r in rows]
    
    def get_team_by_id(self, team_id):
        self.cursor.execute("SELECT * FROM teams WHERE team_id=?", (team_id,))
        r = self.cursor.fetchone()
        return Team(**dict(r)) if r else None

    def update_team_stats(self, team):
        self.cursor.execute("UPDATE teams SET matches_played = ?, wins = ?, draws = ?, losses = ?, goals_for = ?, goals_against = ? WHERE team_id = ?",
                            (team.matches_played, team.wins, team.draws, team.losses, team.goals_for, team.goals_against, team.team_id))
        self.conn.commit()

    def update_fixture_result(self, match):
        self.cursor.execute("UPDATE fixtures SET team1_goals = ?, team2_goals = ?, team1_pso = ?, team2_pso = ?, status = 'Played' WHERE match_no = ?",
                            (match.team1_goals, match.team2_goals, match.team1_pso, match.team2_pso, match.match_no))
        self.conn.commit()

    def update_fixture_teams(self, match_no, t1_id, t2_id):
        if t1_id: self.cursor.execute("UPDATE fixtures SET team1_id = ?, placeholder_t1 = NULL WHERE match_no = ?", (t1_id, match_no))
        if t2_id: self.cursor.execute("UPDATE fixtures SET team2_id = ?, placeholder_t2 = NULL WHERE match_no = ?", (t2_id, match_no))
        self.conn.commit()

# --- TEAM AND MATCH CLASSES (No changes here) ---
class Team:
    def __init__(self, **kwargs):
        self.team_id = kwargs.get('team_id')
        self.tournament_id = kwargs.get('tournament_id')
        self.name = kwargs.get('team_name')
        self.group_name = kwargs.get('group_name')
        self.matches_played = kwargs.get('matches_played', 0)
        self.wins = kwargs.get('wins', 0)
        self.draws = kwargs.get('draws', 0)
        self.losses = kwargs.get('losses', 0)
        self.goals_for = kwargs.get('goals_for', 0)
        self.goals_against = kwargs.get('goals_against', 0)

    @property
    def goal_difference(self): return self.goals_for - self.goals_against

    @property
    def points(self): return (self.wins * 3) + self.draws

class Match:
    def __init__(self, db_manager, team1=None, team2=None, **kwargs):
        self.db = db_manager
        self.match_no = kwargs.get('match_no')
        self.tournament_id = kwargs.get('tournament_id')
        self.team1 = team1
        self.team2 = team2
        self.p1 = kwargs.get('placeholder_t1')
        self.p2 = kwargs.get('placeholder_t2')
        self.team1_goals = kwargs.get('team1_goals')
        self.team2_goals = kwargs.get('team2_goals')
        self.team1_pso = kwargs.get('team1_pso')
        self.team2_pso = kwargs.get('team2_pso')
        self.status = kwargs.get('status', 'Not Played')
        self.stage = kwargs.get('stage')
        self.round_in_stage = kwargs.get('round_in_stage')

    @property
    def team1_name(self): return self.team1.name if self.team1 else self.p1
    
    @property
    def team2_name(self): return self.team2.name if self.team2 else self.p2

    def update_stats(self, new_t1_goals, new_t2_goals, pso_t1=None, pso_t2=None):
        self.team1_goals, self.team2_goals, self.team1_pso, self.team2_pso = new_t1_goals, new_t2_goals, pso_t1, pso_t2
        self.status = 'Played'
        self.db.update_fixture_result(self)
        is_initial_stage = "Group" in self.stage or "League" in self.stage
        if self.team1 and self.team2 and is_initial_stage:
            self.db.recalculate_team_stats(self.team1.team_id)
            self.db.recalculate_team_stats(self.team2.team_id)

# --- TOURNAMENT APP CLASS (Major changes here) ---
class TournamentApp:
    def __init__(self, db_manager):
        self.db = db_manager

    # <<< NEW: This function only handles the group/league stage now >>>
    def generate_group_stage_fixtures(self, tournament_id, settings, teams_by_group):
        is_league_mode = settings['is_league_mode']
        num_legs = settings['num_legs']
        group_names = sorted(teams_by_group.keys())
        schedules_by_group, max_rounds, matches_per_round = {}, 0, 0
        
        for name, teams_in_group in teams_by_group.items():
            if len(teams_in_group) < 2: continue
            if len(teams_in_group) // 2 > matches_per_round: matches_per_round = len(teams_in_group) // 2
            random.shuffle(teams_in_group)
            if len(teams_in_group) % 2 != 0: teams_in_group.append(None)
            num_rounds_in_group = len(teams_in_group) - 1
            if num_rounds_in_group > max_rounds: max_rounds = num_rounds_in_group
            rounds = [[] for _ in range(num_rounds_in_group)]
            for i in range(num_rounds_in_group):
                for j in range(len(teams_in_group) // 2):
                    t1_id, t2_id = teams_in_group[j], teams_in_group[len(teams_in_group) - 1 - j]
                    if t1_id and t2_id: rounds[i].append((t1_id, t2_id))
                teams_in_group.insert(1, teams_in_group.pop())
            schedules_by_group[name] = rounds
            
        for leg in range(num_legs):
            for round_idx in range(max_rounds):
                for match_idx in range(matches_per_round):
                    for name in group_names:
                        if name in schedules_by_group and round_idx < len(schedules_by_group[name]) and match_idx < len(schedules_by_group[name][round_idx]):
                            team1_id, team2_id = schedules_by_group[name][round_idx][match_idx]
                            t1, t2 = (team2_id, team1_id) if leg % 2 == 1 else (team1_id, team2_id)
                            stage_name = "League" if is_league_mode else f"Group {name}"
                            self.db.add_fixture(tournament_id, t1, t2, None, None, stage_name, round_idx + 1)
    
    # <<< NEW: This function handles all knockout logic and accepts custom formats >>>
    def generate_knockout_fixtures(self, tournament_id, settings, custom_qf_pairings=None, custom_sf_pairings=None):
        knockout_mode = settings['knockout_mode']
        is_league_mode = settings['is_league_mode']
        num_groups = settings['num_groups']
        qualifiers_per_group = settings['qualifiers_per_group']
        group_names = ['A', 'B', 'C', 'D'][:num_groups]
        placeholders = []
        for g_name in group_names:
            for i in range(1, qualifiers_per_group + 1):
                placeholders.append(to_ordinal(i) if is_league_mode else f"{g_name}{i}")
        if knockout_mode == '3':
            qf_pairings = []
            if custom_qf_pairings: qf_pairings = custom_qf_pairings
            else:
                if is_league_mode: default = [(0, 7), (3, 4), (2, 5), (1, 6)]
                elif num_groups == 2: default = [(0, 7), (2, 5), (4, 3), (6, 1)]
                else: default = [(0, 3), (4, 7), (2, 1), (6, 5)]
                qf_pairings = [(placeholders[p[0]], placeholders[p[1]]) for p in default]
            for i, (p1, p2) in enumerate(qf_pairings): self.db.add_fixture(tournament_id, None, None, p1, p2, "Quarter-Final", i + 1)
        if knockout_mode in ['2', '3']:
            sf_pairings = []
            if custom_sf_pairings: sf_pairings = custom_sf_pairings
            else:
                if knockout_mode == '2':
                    if is_league_mode: default = [(0, 3), (1, 2)]
                    elif num_groups == 2: default = [(0, 3), (2, 1)]
                    else: default = [(0, 1), (2, 3)]
                    sf_pairings = [(placeholders[p[0]], placeholders[p[1]]) for p in default]
                else:
                    sf_pairings = [("Winner Quarter-Final 1", "Winner Quarter-Final 2"), ("Winner Quarter-Final 3", "Winner Quarter-Final 4")]
            for i, (p1, p2) in enumerate(sf_pairings): self.db.add_fixture(tournament_id, None, None, p1, p2, "Semi-Final", i + 1)
        if knockout_mode in ['1', '2', '3']:
            if knockout_mode == '1':
                final_pairings = [(placeholders[0], placeholders[1])]
            else:
                # <<< FIX IS HERE: Use the full stage name "Semi-Final" >>>
                final_pairings = [("Winner Semi-Final 1", "Winner Semi-Final 2")]
            for i, (p1, p2) in enumerate(final_pairings): self.db.add_fixture(tournament_id, None, None, p1, p2, "Final", i + 1)

    

    # (check_and_promote and other methods remain unchanged)
    def check_and_promote(self, tournament_id):
        # This function doesn't need changes as it relies on placeholders which are now set either by default or custom logic
        all_fixtures = self.db.get_all_fixtures(tournament_id)
        tournament_info = self.db.get_tournament_by_id(tournament_id)
        settings = json.loads(tournament_info['settings'])
        is_league_mode = settings['is_league_mode']
        qualifiers_per_group = settings['qualifiers_per_group']
        initial_stage_fixtures = [f for f in all_fixtures if "Group" in f.stage or "League" in f.stage]
        if not initial_stage_fixtures: return False
        initial_stage_complete = all(f.status == 'Played' for f in initial_stage_fixtures)
        first_knockout_fixture = next((f for f in all_fixtures if f.stage in ["Quarter-Final", "Semi-Final", "Final"]), None)
        if first_knockout_fixture and initial_stage_complete:
            knockouts_started = first_knockout_fixture.team1 is not None or first_knockout_fixture.team2 is not None
            if not knockouts_started:
                self._promote_group_winners(tournament_id, all_fixtures, is_league_mode, qualifiers_per_group)
                return True
        knockout_stages = ["Quarter-Final", "Semi-Final"]
        for stage in knockout_stages:
            stage_fixtures = [f for f in all_fixtures if f.stage == stage]
            if not stage_fixtures or not all(f.status == 'Played' for f in stage_fixtures): continue
            next_stage_name = self._get_next_stage(stage)
            if not next_stage_name: continue
            next_stage_fixture = next((f for f in all_fixtures if f.stage == next_stage_name), None)
            if next_stage_fixture and next_stage_fixture.team1 is None:
                self._promote_knockout_winners(all_fixtures, stage)
                return True
        return False

    def _promote_group_winners(self, tournament_id, all_fixtures, is_league_mode, qualifiers_per_group):
        all_teams = self.db.get_all_teams(tournament_id)
        group_names = sorted(list(set(team.group_name for team in all_teams)))
        knockout_fixtures = [f for f in all_fixtures if "Group" not in f.stage and "League" not in f.stage]
        
        # This needs to handle 'Top Seed #X' for league mode
        for group in group_names:
            teams_in_group = [t for t in all_teams if t.group_name == group]
            standings = sorted(teams_in_group, key=lambda t: (t.points, t.goal_difference, t.goals_for, -t.goals_against), reverse=True)
            for i in range(len(standings)):
                rank, team_to_promote = i + 1, standings[i]
                placeholder = to_ordinal(rank) if is_league_mode else f"{group}{rank}"
                for fixture in knockout_fixtures:
                    if fixture.p1 == placeholder: self.db.update_fixture_teams(fixture.match_no, t1_id=team_to_promote.team_id, t2_id=None)
                    if fixture.p2 == placeholder: self.db.update_fixture_teams(fixture.match_no, t1_id=None, t2_id=team_to_promote.team_id)

    def _promote_knockout_winners(self, all_fixtures, completed_stage):
        completed_fixtures = [f for f in all_fixtures if f.stage == completed_stage]
        next_stage_name = self._get_next_stage(completed_stage)
        next_stage_fixtures = [f for f in all_fixtures if f.stage == next_stage_name]
        for match in completed_fixtures:
            winner = match.team1 if (match.team1_pso is not None and match.team1_pso > match.team2_pso) or \
                                   (match.team1_pso is None and match.team1_goals > match.team2_goals) else match.team2
            placeholder = f"Winner {match.stage} {match.round_in_stage}"
            for next_fixture in next_stage_fixtures:
                if next_fixture.p1 == placeholder: self.db.update_fixture_teams(next_fixture.match_no, t1_id=winner.team_id, t2_id=None)
                if next_fixture.p2 == placeholder: self.db.update_fixture_teams(next_fixture.match_no, t1_id=None, t2_id=winner.team_id)
    
    def _get_next_stage(self, current_stage):
        return {"Quarter-Final": "Semi-Final", "Semi-Final": "Final"}.get(current_stage)

    def autogenerate_group_results(self, tournament_id):
        all_fixtures = self.db.get_all_fixtures(tournament_id)
        fixtures_to_play = [f for f in all_fixtures if ("Group" in f.stage or "League" in f.stage) and f.status == 'Not Played' and f.team1 and f.team2]
        if not fixtures_to_play:
            return 0
        for match in fixtures_to_play:
            score1 = random.randint(0, 5)
            score2 = random.randint(0, 5)
            match.update_stats(score1, score2)
        self.check_and_promote(tournament_id)
        return len(fixtures_to_play)