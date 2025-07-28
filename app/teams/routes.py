"""
Independent team management routes and functionality.
Teams can exist independently and be associated with bookings when needed.
"""

from datetime import date, datetime
import sqlalchemy as sa
import json
from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm

from app import db
from app.teams import bp
from app.models import Booking, Team, TeamMember, Member
from app.routes import role_required
from app.audit import audit_log_create, audit_log_update, audit_log_delete, audit_log_security_event


@bp.route('/create/<int:booking_id>', methods=['GET', 'POST'])
@login_required
@role_required('Event Manager')
def create_team(booking_id):
    """
    Create a new team for a specific booking
    """
    try:
        from app.teams.forms import TeamForm
        
        # Get the booking to ensure it exists
        booking = db.session.get(Booking, booking_id)
        if not booking:
            flash('Booking not found.', 'error')
            return redirect(url_for('main.index'))
        
        form = TeamForm()
        
        if form.validate_on_submit():
            # Create team associated with booking
            team = Team(
                team_name=form.team_name.data,
                created_by=current_user.id,
                booking_id=booking_id
            )
            db.session.add(team)
            db.session.flush()  # Get team ID
            
            # Add team members if specified
            if form.member_ids.data:
                member_ids = [int(x.strip()) for x in form.member_ids.data.split(',') if x.strip()]
                
                # Get available positions for this booking's event format
                available_positions = ['Player']  # Default fallback
                if booking.event and booking.event.event_format:
                    team_positions_config = current_app.config.get('TEAM_POSITIONS', {})
                    if booking.event.event_format in team_positions_config:
                        available_positions = team_positions_config[booking.event.event_format]
                
                for i, member_id in enumerate(member_ids):
                    # Assign positions in order, default to first position if more members than positions
                    position = available_positions[i] if i < len(available_positions) else available_positions[0]
                    
                    team_member = TeamMember(
                        team_id=team.id,
                        member_id=member_id,
                        position=position,
                        availability_status='pending'
                    )
                    db.session.add(team_member)
            
            db.session.commit()
            
            # Audit log
            audit_log_create('Team', team.id, f'Created team: {team.team_name} for booking {booking_id}')
            
            flash(f'Team "{team.team_name}" created successfully for {booking.booking_date}!', 'success')
            return redirect(url_for('teams.manage_team', team_id=team.id))
        
        return render_template('create_team.html', form=form, booking=booking)
        
    except Exception as e:
        current_app.logger.error(f"Error creating team: {str(e)}")
        flash('An error occurred while creating the team.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/manage/<int:team_id>', methods=['GET', 'POST'])
@login_required
def manage_team(team_id):
    """
    Manage an independent team (accessible to team creator and Event Managers)
    """
    try:
        # Get the team
        team = db.session.get(Team, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('main.index'))
        
        # Check if user has permission to manage this team
        if not current_user.is_admin and not current_user.has_role('Event Manager') and team.created_by != current_user.id:
            audit_log_security_event('ACCESS_DENIED', 
                                   f'Unauthorized attempt to manage team {team_id}')
            flash('You do not have permission to manage this team.', 'error')
            return redirect(url_for('main.index'))
        
        # Handle POST request for team management
        if request.method == 'POST':
            csrf_form = FlaskForm()
            if not csrf_form.validate_on_submit():
                flash('Security validation failed.', 'error')
                return redirect(url_for('teams.manage_team', team_id=team_id))
            
            # Check if we should redirect back to rollup management
            redirect_to = request.form.get('redirect_to')
            booking_id = request.form.get('booking_id')
            
            # Handle different actions
            action = request.form.get('action')
            
            if action == 'add_member':
                member_id = request.form.get('member_id')
                position = request.form.get('position', 'Player')
                
                if member_id:
                    # Check if member is already in the team
                    existing = db.session.scalar(
                        sa.select(TeamMember).where(
                            TeamMember.team_id == team_id,
                            TeamMember.member_id == member_id
                        )
                    )
                    
                    if existing:
                        flash('Member is already in this team.', 'warning')
                    else:
                        member = db.session.get(Member, int(member_id))
                        if member:
                            team_member = TeamMember(
                                team_id=team_id,
                                member_id=member_id,
                                position=position,
                                availability_status='pending'
                            )
                            db.session.add(team_member)
                            db.session.commit()
                            
                            audit_log_create('TeamMember', team_member.id, 
                                           f'Added {member.firstname} {member.lastname} to team {team.team_name}')
                            flash(f'{member.firstname} {member.lastname} added to team.', 'success')
                            
                            # Handle redirect if coming from rollup management
                            if redirect_to == 'rollup' and booking_id:
                                return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
                        else:
                            flash('Member not found.', 'error')
                else:
                    flash('Member selection required.', 'error')
            
            elif action == 'substitute_player':
                team_member_id = request.form.get('team_member_id')
                new_member_id = request.form.get('new_member_id')
                reason = request.form.get('reason', 'No reason provided')
                
                if team_member_id and new_member_id:
                    team_member = db.session.get(TeamMember, int(team_member_id))
                    new_member = db.session.get(Member, int(new_member_id))
                    
                    if team_member and new_member:
                        # Get original player info before substitution
                        original_player_name = f"{team_member.member.firstname} {team_member.member.lastname}"
                        substitute_player_name = f"{new_member.firstname} {new_member.lastname}"
                        position = team_member.position
                        
                        # Log the substitution
                        substitution_log_entry = {
                            'timestamp': datetime.utcnow().isoformat(),
                            'action': 'substitution',
                            'original_player': original_player_name,
                            'substitute_player': substitute_player_name,
                            'position': position,
                            'made_by': f"{current_user.firstname} {current_user.lastname}",
                            'reason': reason
                        }
                        
                        # Update the booking team member
                        team_member.member_id = new_member.id
                        team_member.is_substitute = True
                        team_member.substituted_at = datetime.utcnow()
                        team_member.availability_status = 'pending'  # New player needs to confirm
                        
                        # Update substitution log on the team
                        current_log = json.loads(team.substitution_log or '[]')
                        current_log.append(substitution_log_entry)
                        team.substitution_log = json.dumps(current_log)
                        
                        db.session.commit()
                        
                        # Audit log the substitution
                        audit_log_update('TeamMember', team_member.id,
                                       f'Substituted {original_player_name} with {substitute_player_name} for position {position}',
                                       substitution_log_entry)
                        
                        flash(f'Successfully substituted {original_player_name} with {substitute_player_name}.', 'success')
                    else:
                        flash('Invalid player selection.', 'error')
                else:
                    flash('Player and substitute information required.', 'error')
            
            elif action == 'delete_player':
                team_member_id = request.form.get('team_member_id')
                
                if team_member_id:
                    team_member = db.session.get(TeamMember, int(team_member_id))
                    if team_member and team_member.team_id == team_id:
                        player_name = f"{team_member.member.firstname} {team_member.member.lastname}"
                        
                        db.session.delete(team_member)
                        db.session.commit()
                        
                        audit_log_delete('TeamMember', int(team_member_id),
                                       f'Removed {player_name} from team {team.team_name}')
                        
                        flash(f'{player_name} removed from team successfully.', 'success')
                        
                        # Handle redirect if coming from rollup management
                        if redirect_to == 'rollup' and booking_id:
                            return redirect(url_for('rollups.manage_rollup', booking_id=booking_id))
                    else:
                        flash('Team member not found.', 'error')
                else:
                    flash('Team member ID required.', 'error')
            
            elif action == 'update_position':
                team_member_id = request.form.get('team_member_id')
                new_position = request.form.get('position')
                
                if team_member_id and new_position:
                    team_member = db.session.get(TeamMember, int(team_member_id))
                    if team_member and team_member.team_id == team_id:
                        old_position = team_member.position
                        team_member.position = new_position
                        db.session.commit()
                        
                        player_name = f"{team_member.member.firstname} {team_member.member.lastname}"
                        audit_log_update('TeamMember', team_member.id,
                                       f'Updated {player_name} position from {old_position} to {new_position}',
                                       {'old_position': old_position, 'new_position': new_position})
                        
                        flash(f'{player_name} position updated to {new_position}.', 'success')
                    else:
                        flash('Team member not found.', 'error')
                else:
                    flash('Team member ID and position required.', 'error')
        
        # Get team members
        team_members = db.session.scalars(
            sa.select(TeamMember)
            .join(TeamMember.member)
            .where(TeamMember.team_id == team_id)
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        # Get available members for additions/substitutions
        available_members = db.session.scalars(
            sa.select(Member)
            .where(Member.status.in_(['Full', 'Life', 'Social']))
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        # Create CSRF form for template
        csrf_form = FlaskForm()
        
        # Get available positions based on event format
        available_positions = ['Player']  # Default fallback for rollups and events without format
        
        if team.booking.event and team.booking.event.event_format:
            # Get positions from config based on event format
            event_format = team.booking.event.event_format
            team_positions_config = current_app.config.get('TEAM_POSITIONS', {})
            
            if event_format in team_positions_config:
                available_positions = team_positions_config[event_format]
        
        return render_template('manage_team.html',
                             team=team,
                             team_members=team_members,
                             available_members=available_members,
                             available_positions=available_positions,
                             csrf_form=csrf_form,
                             today=date.today())
        
    except Exception as e:
        current_app.logger.error(f"Error managing team {team_id}: {str(e)}")
        flash('An error occurred while managing the team.', 'error')
        return redirect(url_for('main.index'))


@bp.route('/add_substitute/<int:team_id>', methods=['POST'])
@login_required
def add_substitute(team_id):
    """
    Add a substitute to a team
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('teams.manage_team', team_id=team_id))
        
        team = db.session.get(Team, team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('main.index'))
        
        # Check permission
        if not current_user.is_admin and not current_user.has_role('Event Manager') and team.created_by != current_user.id:
            flash('You do not have permission to modify this team.', 'error')
            return redirect(url_for('main.index'))
        
        member_id = request.form.get('member_id', type=int)
        position = request.form.get('position', '')
        
        if not member_id or not position:
            flash('Member and position are required.', 'error')
            return redirect(url_for('teams.manage_team', team_id=team_id))
        
        # Check if member is already in the team
        existing = db.session.scalar(
            sa.select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.member_id == member_id
            )
        )
        
        if existing:
            flash('Member is already in this team.', 'warning')
            return redirect(url_for('teams.manage_team', team_id=team_id))
        
        # Add substitute
        substitute = TeamMember(
            team_id=team_id,
            member_id=member_id,
            position=position,
            is_substitute=True,
            availability_status='pending'
        )
        db.session.add(substitute)
        db.session.commit()
        
        # Get member for audit log
        member = db.session.get(Member, member_id)
        audit_log_create('TeamMember', substitute.id, 
                        f'Added substitute {member.firstname} {member.lastname} to team {team.team_name}')
        
        flash(f'Substitute {member.firstname} {member.lastname} added successfully.', 'success')
        return redirect(url_for('teams.manage_team', team_id=team_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding substitute: {str(e)}")
        flash('An error occurred while adding the substitute.', 'error')
        return redirect(url_for('teams.manage_team', team_id=team_id))


@bp.route('/update_member_availability/<int:team_member_id>', methods=['POST'])
@login_required
def update_member_availability(team_member_id):
    """
    Update a team member's availability status (accessible to team members and managers)
    """
    try:
        # Validate CSRF token
        csrf_form = FlaskForm()
        if not csrf_form.validate_on_submit():
            flash('Security validation failed.', 'error')
            return redirect(url_for('main.index'))
        
        team_member = db.session.get(TeamMember, team_member_id)
        if not team_member:
            flash('Team member not found.', 'error')
            return redirect(url_for('main.index'))
        
        # Check permission - member can update their own availability, or team managers
        team = team_member.team
        can_update = (
            current_user.id == team_member.member_id or
            current_user.is_admin or
            current_user.has_role('Event Manager') or
            (team and team.created_by == current_user.id)
        )
        
        if not can_update:
            flash('You can only update your own availability.', 'error')
            return redirect(url_for('main.index'))
        
        new_status = request.form.get('status')
        if new_status not in ['pending', 'available', 'unavailable']:
            flash('Invalid status.', 'error')
            return redirect(url_for('main.index'))
        
        old_status = team_member.availability_status
        team_member.availability_status = new_status
        
        if new_status != 'pending':
            team_member.confirmed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Audit log
        audit_log_update('TeamMember', team_member.id,
                        f'Availability updated from {old_status} to {new_status}',
                        {'old_status': old_status, 'new_status': new_status})
        
        flash(f'Availability updated to {new_status}.', 'success')
        
        # Redirect back to team management page
        return redirect(url_for('teams.manage_team', team_id=team.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating availability: {str(e)}")
        flash('An error occurred while updating availability.', 'error')
        return redirect(url_for('main.index'))




@bp.route('/list')
@login_required
@role_required('Event Manager')
def list_teams():
    """
    List all teams
    """
    try:
        # Get all teams
        teams = db.session.scalars(
            sa.select(Team)
            .order_by(Team.team_name)
        ).all()
        
        return render_template('list_teams.html', teams=teams)
        
    except Exception as e:
        current_app.logger.error(f"Error listing teams: {str(e)}")
        flash('An error occurred while loading teams.', 'error')
        return redirect(url_for('main.index'))


# API endpoints for team management

@bp.route('/api/v1/team/<int:team_id>', methods=['GET'])
@login_required
def api_get_team(team_id):
    """
    Get team details (AJAX endpoint)
    """
    try:
        team = db.session.get(Team, team_id)
        if not team:
            return jsonify({
                'success': False,
                'error': 'Team not found'
            }), 404
        
        # Check permission
        can_view = (
            current_user.is_admin or
            current_user.has_role('Event Manager') or
            team.created_by == current_user.id
        )
        
        if not can_view:
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403
        
        # Format team data
        team_data = {
            'id': team.id,
            'team_name': team.team_name,
            'created_by': team.created_by,
            'booking_id': team.booking_id,
            'members': []
        }
        
        for member in team.members:
            member_data = {
                'id': member.id,
                'name': f"{member.member.firstname} {member.member.lastname}",
                'position': member.position,
                'is_substitute': member.is_substitute,
                'availability_status': member.availability_status,
                'confirmed_at': member.confirmed_at.isoformat() if member.confirmed_at else None
            }
            team_data['members'].append(member_data)
        
        return jsonify({
            'success': True,
            'team': team_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting team {team_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500