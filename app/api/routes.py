# API routes for the Bowls Club application
from flask import jsonify, request, current_app
from flask_login import login_required, current_user
import sqlalchemy as sa

from app.api import bp
from app import db
from app.models import Member, Event, Booking


@bp.route('/search_members', methods=['GET'])
@login_required
def search_members():
    """
    Search for members by name (AJAX endpoint)
    """
    try:
        search_term = request.args.get('q', '').strip()
        
        if not search_term:
            # Return all active members if no search term
            members = db.session.scalars(
                sa.select(Member)
                .where(Member.status.in_(['Full', 'Social', 'Life']))
                .order_by(Member.firstname, Member.lastname)
            ).all()
        else:
            # Search members by name
            search_pattern = f'%{search_term}%'
            members = db.session.scalars(
                sa.select(Member)
                .where(
                    Member.status.in_(['Full', 'Social', 'Life']),
                    sa.or_(
                        Member.firstname.ilike(search_pattern),
                        Member.lastname.ilike(search_pattern),
                        sa.func.concat(Member.firstname, ' ', Member.lastname).ilike(search_pattern)
                    )
                )
                .order_by(Member.firstname, Member.lastname)
                .limit(20)  # Limit results for performance
            ).all()
        
        # Format results
        results = []
        for member in members:
            results.append({
                'id': member.id,
                'firstname': member.firstname,
                'lastname': member.lastname,
                'email': member.email,
                'phone': member.phone,
                'share_email': member.share_email,
                'share_phone': member.share_phone,
                'status': member.status
            })
        
        return jsonify({
            'success': True,
            'members': results,
            'count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in search_members API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while searching for members'
        }), 500


@bp.route('/event/<int:event_id>')
@login_required
def get_event(event_id):
    """
    Get event details (AJAX endpoint)
    """
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        # Format event data
        event_data = {
            'id': event.id,
            'name': event.name,
            'event_type': event.event_type,
            'event_gender': event.event_gender,
            'event_format': event.event_format,
            'description': event.description,
            'is_active': event.is_active
        }
        
        # Get event teams if they exist
        teams = []
        for team in event.teams:
            team_data = {
                'id': team.id,
                'name': team.name,
                'members': []
            }
            
            for member in team.members:
                team_data['members'].append({
                    'id': member.id,
                    'member_id': member.member_id,
                    'member_name': f"{member.member.firstname} {member.member.lastname}",
                    'position': member.position
                })
            
            teams.append(team_data)
        
        event_data['teams'] = teams
        
        return jsonify({
            'success': True,
            'event': event_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_event API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving event details'
        }), 500


@bp.route('/booking/<int:booking_id>')
@login_required
def get_booking(booking_id):
    """
    Get booking details (AJAX endpoint)
    """
    try:
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return jsonify({
                'success': False,
                'error': 'Booking not found'
            }), 404
        
        # Format booking data
        booking_data = {
            'id': booking.id,
            'booking_date': booking.booking_date.isoformat(),
            'session': booking.session,
            'rink_count': booking.rink_count,
            'booking_type': booking.booking_type,
            'organizer': {
                'id': booking.organizer.id,
                'name': f"{booking.organizer.firstname} {booking.organizer.lastname}",
                'email': booking.organizer.email
            },
            'organizer_notes': booking.organizer_notes,
            'vs': booking.vs,
            'home_away': booking.home_away
        }
        
        # Add event details if it's an event booking
        if booking.event:
            booking_data['event'] = {
                'id': booking.event.id,
                'name': booking.event.name,
                'event_type': booking.event.event_type,
                'event_gender': booking.event.event_gender,
                'event_format': booking.event.event_format
            }
        
        # Add team details if they exist
        if booking.booking_type == 'event' and booking.teams:
            teams = []
            for team in booking.teams:
                team_data = {
                    'id': team.id,
                    'team_name': team.team_name,
                    'members': []
                }
                
                for member in team.members:
                    team_data['members'].append({
                        'id': member.id,
                        'member_id': member.member_id,
                        'member_name': f"{member.member.firstname} {member.member.lastname}",
                        'position': member.position,
                        'availability_status': member.availability_status,
                        'confirmed_at': member.confirmed_at.isoformat() if member.confirmed_at else None
                    })
                
                teams.append(team_data)
            
            booking_data['teams'] = teams
        
        # Add roll-up players if it's a roll-up booking
        elif booking.booking_type == 'rollup':
            from app.models import BookingPlayer
            players = db.session.scalars(
                sa.select(BookingPlayer)
                .where(BookingPlayer.booking_id == booking_id)
                .order_by(BookingPlayer.member.firstname, BookingPlayer.member.lastname)
            ).all()
            
            booking_data['players'] = []
            for player in players:
                booking_data['players'].append({
                    'id': player.id,
                    'member_id': player.member_id,
                    'member_name': f"{player.member.firstname} {player.member.lastname}",
                    'status': player.status,
                    'response_at': player.response_at.isoformat() if player.response_at else None,
                    'is_organizer': player.member_id == booking.organizer_id
                })
        
        return jsonify({
            'success': True,
            'booking': booking_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_booking API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving booking details'
        }), 500


@bp.route('/get_availability/<string:selected_date>/<int:session_id>')
@login_required
def get_availability(selected_date, session_id):
    """
    Get rink availability for a specific date and session (AJAX endpoint)
    """
    try:
        from datetime import datetime
        
        # Parse the selected date
        booking_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # Get total rinks available
        total_rinks = current_app.config.get('RINKS', 6)
        
        # Get existing bookings for this date and session
        bookings = db.session.scalars(
            sa.select(Booking)
            .where(
                Booking.booking_date == booking_date,
                Booking.session == session_id
            )
        ).all()
        
        # Calculate used rinks
        used_rinks = sum(booking.rink_count for booking in bookings)
        available_rinks = total_rinks - used_rinks
        
        # Format booking details
        booking_details = []
        for booking in bookings:
            detail = {
                'id': booking.id,
                'rink_count': booking.rink_count,
                'booking_type': booking.booking_type,
                'organizer': f"{booking.organizer.firstname} {booking.organizer.lastname}",
                'organizer_notes': booking.organizer_notes
            }
            
            if booking.event:
                detail['event_name'] = booking.event.name
                detail['vs'] = booking.vs
            
            booking_details.append(detail)
        
        return jsonify({
            'success': True,
            'date': selected_date,
            'session': session_id,
            'total_rinks': total_rinks,
            'used_rinks': used_rinks,
            'available_rinks': available_rinks,
            'bookings': booking_details
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_availability API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while checking availability'
        }), 500