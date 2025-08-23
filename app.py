# ==============================================================================
# File: app.py
# ==============================================================================
import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from Tournament_Manager import DatabaseManager, TournamentApp, DB_NAME

# --- Setup ---
app = Flask(__name__)
app.secret_key = 'a-super-secret-key-that-you-should-change'

db_manager = DatabaseManager(DB_NAME)
tournament_app = TournamentApp(db_manager)

# A dummy password for our admin area
ADMIN_PASSWORD = "password123"

# --- Page Routes ---

@app.route('/')
def index():
    """Renders the main homepage."""
    return render_template('index.html')

# --- NEW: Standings Page Route ---
@app.route('/standings')
@app.route('/standings/<int:tournament_id>')
def standings(tournament_id=None):
    """Renders the dedicated standings page."""
    return render_template('standings.html', preselected_id=tournament_id, active_page='standings')

# --- NEW: Fixtures Page Route ---
@app.route('/fixtures')
@app.route('/fixtures/<int:tournament_id>')
def fixtures(tournament_id=None):
    """Renders the dedicated fixtures page."""
    return render_template('fixtures.html', preselected_id=tournament_id, active_page='fixtures')

@app.route('/reports')
@app.route('/reports/<int:tournament_id>')
def reports(tournament_id=None):
    """Renders the public reports page."""
    return render_template('reports.html', preselected_id=tournament_id, active_page='reports')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    """Renders the admin login page and handles the login form submission."""
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid password. Please try again.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/dashboard')
def admin_dashboard():
    """Renders the main admin control panel."""
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    tournaments = db_manager.get_all_tournaments()
    return render_template('admin_dashboard.html', tournaments=tournaments)

@app.route('/admin/manage/<int:tournament_id>')
def manage_tournament(tournament_id):
    """Renders the page for managing a single tournament's results."""
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    tournament_info = db_manager.get_tournament_by_id(tournament_id)
    fixtures = db_manager.get_all_fixtures(tournament_id)
    return render_template('manage_tournament.html', tournament=tournament_info, fixtures=fixtures)

# --- Add this new route to app.py ---

@app.route('/about')
def about():
    """Renders the new about page."""
    return render_template('about.html', active_page='about')

@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# --- API Routes (No changes needed here) ---

@app.route('/api/tournaments')
def get_tournaments():
    """API endpoint to get a list of all tournaments."""
    tournaments_raw = db_manager.get_all_tournaments()
    tournaments_list = [dict(row) for row in tournaments_raw]
    return jsonify(tournaments_list)

@app.route('/api/tournaments/<int:tournament_id>')
def get_tournament_data(tournament_id):
    """Returns all data for a specific tournament report as JSON."""
    all_teams = db_manager.get_all_teams(tournament_id)
    all_fixtures = db_manager.get_all_fixtures(tournament_id)
    tournament_info = db_manager.get_tournament_by_id(tournament_id)
    settings = json.loads(tournament_info['settings']) if tournament_info and tournament_info['settings'] else {}
    standings = {}
    for team in all_teams:
        if team.group_name not in standings:
            standings[team.group_name] = []
        standings[team.group_name].append(team)
    sorted_standings = {}
    for group_name, teams in standings.items():
        sorted_teams = sorted(teams, key=lambda t: (t.points, t.goal_difference, t.goals_for, t.name), reverse=True)
        
        team_list = []
        for team in sorted_teams:
            team_list.append({
                'name': team.name,
                'matches_played': team.matches_played,
                'wins': team.wins,
                'draws': team.draws,
                'losses': team.losses,
                'goals_for': team.goals_for,
                'goals_against': team.goals_against,
                'goal_difference': team.goal_difference,
                'points': team.points
            })
        sorted_standings[group_name] = team_list

    formatted_fixtures = []
    for i, match in enumerate(all_fixtures): 
        match_dict = {
            'display_no': i + 1,
            'match_no': match.match_no, 
            'stage': match.stage, 
            'round_in_stage': match.round_in_stage,
            'team1_name': match.team1_name, 
            'team2_name': match.team2_name,
            'team1_goals': match.team1_goals, 
            'team2_goals': match.team2_goals,
            'team1_pso': match.team1_pso, 
            'team2_pso': match.team2_pso, 
            'status': match.status
        }
        formatted_fixtures.append(match_dict)

    report_data = {
        'standings': sorted_standings,
        'fixtures': formatted_fixtures,
        'settings': settings,
        'season_number': tournament_info['season_number'] if tournament_info else 'N/A'
    }
    return jsonify(report_data)

@app.route('/api/admin/create', methods=['POST'])
def create_tournament_api():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    try:
        num_groups = int(data['num_groups'])
        num_teams_per_group = int(data['num_teams_per_group'])
        knockout_mode = data['knockout_mode']
        knockout_teams_map = {'1': 2, '2': 4, '3': 8}
        total_qualifiers = knockout_teams_map[knockout_mode]
        settings = {
            "num_groups": num_groups, "num_teams_per_group": num_teams_per_group,
            "is_league_mode": num_groups == 1, "knockout_mode": knockout_mode,
            "qualifiers_per_group": total_qualifiers // num_groups, "num_legs": int(data['num_legs'])
        }
        settings_json = json.dumps(settings)
        season_number = int(data['season_number'])
        tournament_id = db_manager.create_new_tournament(season_number, settings_json)
        teams_by_group = {}
        group_names = ['A', 'B', 'C', 'D']
        for i in range(num_groups):
            group_name = group_names[i]
            teams_by_group[group_name] = []
            for j in range(num_teams_per_group):
                team_name = data[f'team_{group_name}_{j}']
                db_manager.add_team(tournament_id, team_name.strip().upper(), group_name)
        all_teams_in_db = db_manager.get_all_teams(tournament_id)
        team_ids_by_group = {g: [] for g in group_names[:num_groups]}
        for team in all_teams_in_db:
            team_ids_by_group[team.group_name].append(team.team_id)
        tournament_app.generate_fixtures(tournament_id, settings, team_ids_by_group, settings['num_legs'])
        return jsonify({'success': True, 'message': f'Successfully created Season {season_number}!'})
    except Exception as e:
        print(f"Error creating tournament: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500

@app.route('/api/admin/update_result', methods=['POST'])
def update_result_api():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json()
    try:
        match_no = int(data['match_no'])
        team1_goals = int(data['team1_goals'])
        team2_goals = int(data['team2_goals'])
        pso_t1 = data.get('pso_t1')
        pso_t2 = data.get('pso_t2')
        pso_t1 = int(pso_t1) if pso_t1 else None
        pso_t2 = int(pso_t2) if pso_t2 else None
        match = db_manager.get_fixture_by_id(match_no)
        if not match: return jsonify({'success': False, 'message': 'Match not found'}), 404
        if not match.team1 or not match.team2: return jsonify({'success': False, 'message': 'Cannot enter result for a match with placeholder teams.'}), 400
        match.update_stats(team1_goals, team2_goals, pso_t1, pso_t2)
        tournament_app.check_and_promote(match.tournament_id)
        return jsonify({'success': True, 'message': f'Result for Match {match_no} updated successfully!'})
    except Exception as e:
        print(f"Error updating result: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500

@app.route('/api/admin/delete/<int:tournament_id>', methods=['POST'])
def delete_tournament_api(tournament_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        tournament_info = db_manager.get_tournament_by_id(tournament_id)
        if not tournament_info: return jsonify({'success': False, 'message': 'Tournament not found'}), 404
        db_manager.delete_tournament(tournament_id)
        return jsonify({'success': True, 'message': f'Successfully deleted Season {tournament_info["season_number"]}.'})
    except Exception as e:
        print(f"Error deleting tournament: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500

@app.route('/api/admin/autogenerate/<int:tournament_id>', methods=['POST'])
def autogenerate_api(tournament_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        updated_count = tournament_app.autogenerate_group_results(tournament_id)
        if updated_count > 0: message = f"Successfully generated random results for {updated_count} matches."
        else: message = "No group stage matches needed to be updated."
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        print(f"Error autogenerating results: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {e}'}), 500

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=False)
