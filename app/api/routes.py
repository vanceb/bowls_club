# API routes for the Bowls Club application
from flask import jsonify, request, current_app
from flask_login import login_required, current_user
import sqlalchemy as sa

from app.api import bp
from app import db
from app.models import Member, Event, Booking, EventPool, PoolRegistration
from app.routes import role_required, admin_required


# MOVED TO MEMBERS BLUEPRINT: /api/search_members → /members/api/v1/search


@bp.route('/event/<int:event_id>')
@login_required
@role_required('Event Manager')
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
        
        # Format event data with correct field names
        event_data = {
            'id': event.id,
            'name': event.name,
            'event_type': event.event_type,
            'gender': event.gender,
            'format': event.format,
            'scoring': event.scoring,
            # Add computed fields for JavaScript summaries
            'event_type_name': event.get_event_type_name(),
            'format_name': event.get_format_name(),
            'teams_count': len(event.event_teams) if event.event_teams else 0,
            'bookings_count': len(event.bookings) if event.bookings else 0,
            'has_pool_enabled': event.has_pool_enabled()
        }
        
        # Add event managers
        event_managers = []
        for manager in event.event_managers:
            event_managers.append({
                'id': manager.id,
                'name': f"{manager.firstname} {manager.lastname}"
            })
        event_data['event_managers'] = event_managers
        
        # Get event teams if they exist
        teams = []
        for team in event.event_teams:
            team_data = {
                'id': team.id,
                'team_name': team.team_name,
                'team_number': team.team_number,
                'members': []
            }
            
            for member in team.team_members:
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
            **event_data  # Return event data directly at root level
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


# MOVED TO MEMBERS BLUEPRINT: /api/users_with_roles → /members/api/v1/users_with_roles


@bp.route('/events/upcoming', methods=['GET'])
@login_required
def get_upcoming_events():
    """
    Get upcoming events with pool registration enabled
    Returns user's registration status for each event
    """
    try:
        # Get all events that have pools enabled
        events_with_pools = db.session.scalars(
            sa.select(Event)
            .join(Event.pool)
            .where(Event.has_pool == True)
            .order_by(Event.created_at.desc())
        ).all()
        
        # Format events data
        events_data = []
        for event in events_with_pools:
            event_info = {
                'id': event.id,
                'name': event.name,
                'event_type': event.get_event_type_name(),
                'gender': event.get_gender_name(),
                'format': event.get_format_name(),
                'scoring': event.scoring,
                'created_at': event.created_at.isoformat(),
                'pool_open': event.is_pool_open(),
                'pool_count': event.get_pool_member_count(),
                'registration_status': 'not_registered',
                'managers': [
                    {
                        'id': manager.id,
                        'name': f"{manager.firstname} {manager.lastname}"
                    }
                    for manager in event.event_managers
                ]
            }
            
            # Check if user is registered
            if event.pool:
                user_registration = event.pool.get_member_registration(current_user.id)
                if user_registration:
                    event_info['registration_status'] = 'registered'  # All pool registrations are 'registered'
                    event_info['registered_at'] = user_registration.registered_at.isoformat()
            
            events_data.append(event_info)
        
        return jsonify({
            'success': True,
            'events': events_data,
            'count': len(events_data)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_upcoming_events API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving upcoming events'
        }), 500


@bp.route('/events/<int:event_id>/register', methods=['POST'])
@login_required
def register_for_event_api():
    """
    Register current user for an event pool (API endpoint)
    """
    try:
        from app.audit import audit_log_create
        
        event_id = request.view_args.get('event_id')
        if not event_id:
            return jsonify({
                'success': False,
                'error': 'Missing event ID'
            }), 400
        
        # Get the event
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            return jsonify({
                'success': False,
                'error': 'This event does not have pool registration enabled'
            }), 400
        
        # Check if pool is open
        if not event.is_pool_open():
            return jsonify({
                'success': False,
                'error': 'Registration for this event is closed'
            }), 400
        
        # Check if user is already registered
        existing_registration = event.pool.get_member_registration(current_user.id)
        if existing_registration and existing_registration.is_active:
            return jsonify({
                'success': False,
                'error': f'You are already registered for {event.name}'
            }), 400
        
        # Create new registration
        registration = PoolRegistration(
            pool_id=event.pool.id,
            member_id=current_user.id
        )
        
        db.session.add(registration)
        db.session.commit()
        
        # Audit log
        audit_log_create('PoolRegistration', registration.id, 
                        f'User {current_user.username} registered for event: {event.name}')
        
        return jsonify({
            'success': True,
            'message': f'Successfully registered for {event.name}',
            'registration': {
                'id': registration.id,
                'status': 'registered',  # All pool registrations are 'registered'
                'registered_at': registration.registered_at.isoformat()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in register_for_event_api: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while registering for the event'
        }), 500


@bp.route('/events/<int:event_id>/withdraw', methods=['POST'])
@login_required
def withdraw_from_event_api():
    """
    Withdraw current user from an event pool (API endpoint)
    """
    try:
        from app.audit import audit_log_update
        
        event_id = request.view_args.get('event_id')
        if not event_id:
            return jsonify({
                'success': False,
                'error': 'Missing event ID'
            }), 400
        
        # Get the event
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            return jsonify({
                'success': False,
                'error': 'This event does not have pool registration'
            }), 400
        
        # Get user's registration
        registration = event.pool.get_member_registration(current_user.id)
        if not registration or not registration.is_active:
            return jsonify({
                'success': False,
                'error': f'You are not registered for {event.name}'
            }), 400
        
        # Check if pool is still open
        if not event.is_pool_open():
            return jsonify({
                'success': False,
                'error': 'Registration for this event is closed. Contact the event manager to make changes.'
            }), 400
        
        # Withdraw the registration
        registration.withdraw()
        db.session.commit()
        
        # Audit log
        audit_log_update('PoolRegistration', registration.id, 
                        f'User {current_user.username} withdrew from event: {event.name}')
        
        return jsonify({
            'success': True,
            'message': f'Successfully withdrawn from {event.name}',
            'registration': {
                'id': registration.id,
                'status': 'registered',  # All pool registrations are 'registered'
                'last_updated': registration.last_updated.isoformat()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in withdraw_from_event_api: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while withdrawing from the event'
        }), 500


@bp.route('/events/<int:event_id>/pool', methods=['GET'])
@login_required
@role_required('Event Manager')
def get_event_pool():
    """
    Get pool members for an event (Event Manager access)
    """
    try:
        event_id = request.view_args.get('event_id')
        if not event_id:
            return jsonify({
                'success': False,
                'error': 'Missing event ID'
            }), 400
        
        # Get the event
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        
        # Check if event has pool enabled
        if not event.has_pool_enabled():
            return jsonify({
                'success': False,
                'error': 'This event does not have pool registration enabled'
            }), 400
        
        # Get pool registrations
        registrations = db.session.scalars(
            sa.select(PoolRegistration)
            .join(PoolRegistration.member)
            .where(PoolRegistration.pool_id == event.pool.id)
            .order_by(Member.firstname, Member.lastname)
        ).all()
        
        # Format pool data
        pool_data = {
            'event': {
                'id': event.id,
                'name': event.name,
                'event_type': event.get_event_type_name(),
                'gender': event.get_gender_name(),
                'format': event.get_format_name()
            },
            'pool': {
                'id': event.pool.id,
                'is_open': event.pool.is_open,
                'created_at': event.pool.created_at.isoformat(),
                'closed_at': event.pool.closed_at.isoformat() if event.pool.closed_at else None,
                'auto_close_date': event.pool.auto_close_date.isoformat() if event.pool.auto_close_date else None
            },
            'registrations': []
        }
        
        for registration in registrations:
            pool_data['registrations'].append({
                'id': registration.id,
                'member': {
                    'id': registration.member.id,
                    'name': f"{registration.member.firstname} {registration.member.lastname}",
                    'email': registration.member.email if registration.member.share_email else None,
                    'phone': registration.member.phone if registration.member.share_phone else None
                },
                'status': 'registered',  # All pool registrations are 'registered'
                'registered_at': registration.registered_at.isoformat(),
                'last_updated': registration.last_updated.isoformat(),
                'is_active': registration.is_active
            })
        
        # Group by status
        pool_data['summary'] = {
            'total': len(registrations),
            'registered': len([r for r in registrations if r.status == 'registered']),
            'selected': len([r for r in registrations if r.status == 'selected'])
        }
        
        return jsonify({
            'success': True,
            **pool_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_event_pool API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving event pool data'
        }), 500