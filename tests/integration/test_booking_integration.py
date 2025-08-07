"""
Integration tests for booking functionality across different components.
"""
import pytest
import json
from datetime import date, timedelta
from app.models import Member, Booking


@pytest.mark.integration
class TestBookingIntegration:
    """Integration tests for booking functionality."""
    
    def test_complete_rollup_booking_workflow(self, authenticated_client, db_session, test_member):
        """Test complete roll-up booking workflow from creation to response."""
        # Create additional members to invite
        player1 = Member(
            username='player1', firstname='Player', lastname='One',
            email='player1@test.com', status='Full'
        )
        player2 = Member(
            username='player2', firstname='Player', lastname='Two',
            email='player2@test.com', status='Full'
        )
        db_session.add_all([player1, player2])
        db_session.commit()
        
        # Step 1: Create roll-up booking
        form_data = {
            'booking_date': (date.today() + timedelta(days=3)).isoformat(),
            'session': '2',
            'organizer_notes': 'Test integration rollup',
            'invited_players': f'{player1.id},{player2.id}',
            'csrf_token': 'dummy'
        }
        
        response = authenticated_client.post('/bookings/rollup/book', 
                                           data=form_data, 
                                           follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Roll-up booking created successfully!' in response.data
        
        # Verify booking was created
        booking = db_session.query(Booking).filter_by(booking_type='rollup').first()
        assert booking is not None
        assert booking.organizer_id == test_member.id
        
        # Verify organizer is confirmed
        organizer_player = db_session.query(BookingPlayer).filter_by(
            booking_id=booking.id, member_id=test_member.id
        ).first()
        assert organizer_player is not None
        assert organizer_player.status == 'confirmed'
        
        # Verify invitations were created
        invitations = db_session.query(BookingPlayer).filter_by(
            booking_id=booking.id
        ).all()
        assert len(invitations) == 3  # Organizer + 2 invited players
        
        # Step 2: Test booking appears in API
        api_response = authenticated_client.get(f'/bookings/api/v1/booking/{booking.id}')
        assert api_response.status_code == 200
        api_data = json.loads(api_response.data)
        assert api_data['success'] is True
        assert api_data['booking']['booking_type'] == 'rollup'
        
        # Step 3: Test manage rollup page
        manage_response = authenticated_client.get(f'/bookings/rollup/manage/{booking.id}')
        assert manage_response.status_code == 200
        assert b'Manage Roll-Up' in manage_response.data
        assert b'Player One' in manage_response.data
        assert b'Player Two' in manage_response.data
    
    def test_booking_rink_availability_integration(self, authenticated_client, db_session):
        """Test booking rink availability across different booking types."""
        # Create test members
        organizer1 = Member(
            username='org1', firstname='Organizer', lastname='One',
            email='org1@test.com', status='Full'
        )
        organizer2 = Member(
            username='org2', firstname='Organizer', lastname='Two',
            email='org2@test.com', status='Full'
        )
        db_session.add_all([organizer1, organizer2])
        db_session.commit()
        
        test_date = date.today() + timedelta(days=5)
        
        # Create initial booking using 4 rinks
        booking1 = Booking(
            booking_date=test_date,
            session=1,
            rink_count=4,
            organizer_id=organizer1.id,
            booking_type='event',
            home_away='home'
        )
        db_session.add(booking1)
        db_session.commit()
        
        # Test bookings range API shows correct availability
        start_date = test_date.isoformat()
        end_date = test_date.isoformat()
        
        response = authenticated_client.get(f'/bookings/get_bookings_range/{start_date}/{end_date}')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should show 4 rinks booked, 2 available
        booking_data = data['bookings'][start_date][1][0]
        assert booking_data['rink_count'] == 4
        
        # Try to book 3 more rinks (should fail)
        form_data = {
            'booking_date': test_date.isoformat(),
            'session': '1',
            'rink_count': '3',
            'csrf_token': 'dummy'
        }
        
        # This would need to be tested via the booking form validation
        # The form should reject this as only 2 rinks are available
        
        # Create away game using all 6 rinks (should not affect availability)
        away_booking = Booking(
            booking_date=test_date,
            session=2,  # Different session
            rink_count=6,
            organizer_id=organizer2.id,
            booking_type='event',
            home_away='away'
        )
        db_session.add(away_booking)
        db_session.commit()
        
        # Test that away game doesn't affect home availability
        response = authenticated_client.get(f'/bookings/get_bookings_range/{start_date}/{end_date}')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Session 2 should show away game
        session2_bookings = data['bookings'][start_date][2]
        assert len(session2_bookings) == 1
        # Away games should still appear in the calendar
    
    def test_event_booking_with_teams_integration(self, admin_client, db_session):
        """Test complete event booking workflow with team management."""
        # Create organizer and players
        organizer = Member(
            username='organizer', firstname='Event', lastname='Organizer',
            email='organizer@test.com', status='Full'
        )
        lead = Member(
            username='lead', firstname='Lead', lastname='Player',
            email='lead@test.com', status='Full'
        )
        skip = Member(
            username='skip', firstname='Skip', lastname='Player',
            email='skip@test.com', status='Full'
        )
        db_session.add_all([organizer, lead, skip])
        db_session.commit()
        
        # Create booking (which includes all event information in booking-centric architecture)
        booking = Booking(
            name='Integration Championship',
            booking_date=date.today() + timedelta(days=7),
            session=1,
            rink_count=2,
            organizer_id=organizer.id,
            event_type=2,  # Competition
            format=2,  # Pairs
            gender=3,  # Mixed
            vs='Championship Opponents'
        )
        db_session.add(booking)
        db_session.commit()
        
        # Test booking appears in API with event details
        response = admin_client.get(f'/bookings/api/v1/booking/{booking.id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['booking']['event_name'] == 'Integration Championship'
        assert data['booking']['vs'] == 'Championship Opponents'
        
        # Test team management access
        teams_response = admin_client.get(f'/bookings/admin/manage_teams/{booking.id}')
        assert teams_response.status_code == 200
        assert b'Integration Championship' in teams_response.data
        
        # Add team via team management
        form_data = {
            'action': 'add_team',
            'team_name': 'Home Team',
            'csrf_token': 'dummy'
        }
        
        add_team_response = admin_client.post(f'/bookings/admin/manage_teams/{booking.id}',
                                            data=form_data,
                                            follow_redirects=True)
        assert add_team_response.status_code == 200
        assert b'Team added successfully' in add_team_response.data
        
        # Verify team was created
        team = db_session.query(BookingTeam).filter_by(booking_id=booking.id).first()
        assert team is not None
        assert team.team_name == 'Home Team'
        
        # Add players to team
        add_lead_data = {
            'action': 'add_player',
            'team_id': str(team.id),
            'member_id': str(lead.id),
            'position': 'Lead',
            'csrf_token': 'dummy'
        }
        
        add_player_response = admin_client.post(f'/bookings/admin/manage_teams/{booking.id}',
                                              data=add_lead_data,
                                              follow_redirects=True)
        assert add_player_response.status_code == 200
        assert b'Player added successfully' in add_player_response.data
        
        # Verify player was added
        team_member = db_session.query(BookingTeamMember).filter_by(
            team_id=team.id, member_id=lead.id
        ).first()
        assert team_member is not None
        assert team_member.position == 'Lead'
    
    def test_booking_calendar_integration(self, authenticated_client, db_session):
        """Test booking calendar displays different booking types correctly."""
        # Create test members
        event_organizer = Member(
            username='event_org', firstname='Event', lastname='Organizer',
            email='event@test.com', status='Full'
        )
        rollup_organizer = Member(
            username='rollup_org', firstname='Rollup', lastname='Organizer',
            email='rollup@test.com', status='Full'
        )
        db_session.add_all([event_organizer, rollup_organizer])
        db_session.commit()
        
        test_date = date.today() + timedelta(days=4)
        
        # Create event booking (which includes all event information in booking-centric architecture)
        event_booking = Booking(
            name='Calendar Test Event',
            booking_date=test_date,
            session=1,
            rink_count=3,
            organizer_id=event_organizer.id,
            event_type=1,  # Social
            format=3,  # Triples
            gender=2,  # Ladies
            vs='Calendar Opponents'
        )
        db_session.add(event_booking)
        db_session.commit()
        
        # Create rollup booking
        rollup_booking = Booking(
            booking_date=test_date,
            session=2,
            rink_count=1,
            organizer_id=rollup_organizer.id,
            booking_type='rollup',
            organizer_notes='Calendar rollup test'
        )
        db_session.add(rollup_booking)
        db_session.commit()
        
        # Add player to rollup
        rollup_player = BookingPlayer(
            booking_id=rollup_booking.id,
            member_id=rollup_organizer.id,
            status='confirmed',
            invited_by=rollup_organizer.id
        )
        db_session.add(rollup_player)
        db_session.commit()
        
        # Test calendar data API
        start_date = test_date.isoformat()
        end_date = test_date.isoformat()
        
        response = authenticated_client.get(f'/bookings/get_bookings_range/{start_date}/{end_date}')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify both bookings appear
        date_bookings = data['bookings'][start_date]
        assert 1 in date_bookings  # Session 1 has event booking
        assert 2 in date_bookings  # Session 2 has rollup booking
        
        # Verify event booking data
        event_booking_data = date_bookings[1][0]
        assert event_booking_data['booking_type'] == 'event'
        assert event_booking_data['event_name'] == 'Calendar Test Event'
        assert event_booking_data['vs'] == 'Calendar Opponents'
        assert event_booking_data['rink_count'] == 3
        
        # Verify rollup booking data
        rollup_booking_data = date_bookings[2][0]
        assert rollup_booking_data['booking_type'] == 'rollup'
        assert rollup_booking_data['organizer'] == 'Rollup Organizer'
        assert rollup_booking_data['player_count'] == 1
        assert rollup_booking_data['rink_count'] == 1
    
    def test_booking_permissions_integration(self, client, db_session, test_member, admin_member):
        """Test booking permissions across different user roles."""
        # Create booking as admin
        booking = Booking(
            booking_date=date.today() + timedelta(days=6),
            session=1,
            rink_count=2,
            organizer_id=admin_member.id,
            booking_type='event'
        )
        db_session.add(booking)
        db_session.commit()
        
        # Test regular user access
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_member.id)
            sess['_fresh'] = True
        
        # Regular user can view booking via API
        response = client.get(f'/bookings/api/v1/booking/{booking.id}')
        assert response.status_code == 200
        
        # Regular user cannot edit booking
        response = client.get(f'/bookings/admin/edit/{booking.id}')
        assert response.status_code == 302  # Redirect due to role requirement
        
        # Regular user cannot update via API
        response = client.put(f'/bookings/api/v1/booking/{booking.id}', 
                            json={'rink_count': 3})
        assert response.status_code == 302  # Redirect due to role requirement
        
        # Test admin access
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_member.id)
            sess['_fresh'] = True
        
        # Admin can edit booking
        response = client.get(f'/bookings/admin/edit/{booking.id}')
        assert response.status_code == 200
        
        # Admin can update via API
        response = client.put(f'/bookings/api/v1/booking/{booking.id}', 
                            json={'rink_count': 3})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


@pytest.mark.integration
class TestPoolStrategyIntegration:
    """Integration tests for pool strategy functionality across booking scenarios."""
    
    def test_booking_strategy_pool_creation(self, app, db_session):
        """Test that 'booking' strategy creates separate pools for each booking."""
        with app.app_context():
            from app.models import Pool
            from tests.fixtures.factories import BookingFactory, PoolFactory
            
            # Create original booking with pool (Social event = 'booking' strategy)
            original = BookingFactory(event_type=1, has_pool=True, series_id='test-series')
            original_pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = original_pool
            
            # Simulate duplication logic 
            from app.bookings.utils import should_create_pool_for_duplication
            duplicate = BookingFactory(event_type=1, series_id='test-series')
            db_session.commit()
            
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is True
            assert "'booking'" in reason
            
            # Create new pool for duplicate (simulating duplication logic)
            if should_create:
                duplicate_pool = PoolFactory(booking_id=duplicate.id)
                db_session.commit()
                duplicate.pool = duplicate_pool
            
            # Verify each booking has its own pool
            assert original.pool.id != duplicate.pool.id
            assert original.get_effective_pool().id == original.pool.id
            assert duplicate.get_effective_pool().id == duplicate.pool.id
    
    def test_event_strategy_pool_sharing(self, app, db_session):
        """Test that 'event' strategy shares pools across bookings in a series."""
        with app.app_context():
            from app.models import Pool
            from tests.fixtures.factories import BookingFactory, PoolFactory
            
            # Create primary booking with pool (Competition event = 'event' strategy)
            primary = BookingFactory(
                event_type=2, 
                has_pool=True, 
                series_id='competition-series',
                booking_date=date.today() + timedelta(days=3)  # Earlier date
            )
            primary_pool = PoolFactory(booking_id=primary.id)
            db_session.commit()
            primary.pool = primary_pool
            
            # Create secondary booking in same series (later date)
            secondary = BookingFactory(
                event_type=2,
                series_id='competition-series', 
                booking_date=date.today() + timedelta(days=7)  # Later date
            )
            db_session.commit()
            
            # Verify pool sharing logic
            from app.bookings.utils import should_create_pool_for_duplication
            should_create, reason = should_create_pool_for_duplication(primary, secondary)
            assert should_create is False
            assert "'event'" in reason
            
            # Verify secondary booking gets primary's pool
            assert secondary.get_effective_pool().id == primary_pool.id
            assert secondary.has_effective_pool() is True
            assert primary.is_primary_booking_in_series() is True
            assert secondary.is_primary_booking_in_series() is False
    
    def test_none_strategy_no_pool_creation(self, app, db_session):
        """Test that 'none' strategy prevents pool creation for duplicates."""
        with app.app_context():
            from app.models import Pool
            from tests.fixtures.factories import BookingFactory, PoolFactory
            
            # Create original rollup booking with pool (Roll Up event = 'none' strategy)
            original = BookingFactory(event_type=5, has_pool=True, series_id='rollup-series')
            original_pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = original_pool
            
            # Simulate duplication
            duplicate = BookingFactory(event_type=5, series_id='rollup-series')
            db_session.commit()
            
            from app.bookings.utils import should_create_pool_for_duplication
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is False
            assert "'none'" in reason
            
            # Verify duplicate has no effective pool
            assert duplicate.get_effective_pool() is None
            assert duplicate.has_effective_pool() is False
    
    def test_mixed_event_types_in_series(self, app, db_session):
        """Test behavior when series contains bookings of different event types."""
        with app.app_context():
            from app.models import Pool
            from tests.fixtures.factories import BookingFactory, PoolFactory
            
            # Create bookings with different strategies in same series
            # This shouldn't normally happen but tests edge case handling
            
            # Competition booking (event strategy) 
            competition_booking = BookingFactory(
                event_type=2,  # Competition = 'event' 
                series_id='mixed-series',
                booking_date=date.today() + timedelta(days=3)
            )
            competition_pool = PoolFactory(booking_id=competition_booking.id)
            db_session.commit()
            competition_booking.pool = competition_pool
            
            # Social booking (booking strategy) in same series
            social_booking = BookingFactory(
                event_type=1,  # Social = 'booking'
                series_id='mixed-series', 
                booking_date=date.today() + timedelta(days=5)
            )
            db_session.commit()
            
            # Each booking should use its own strategy
            assert competition_booking.get_pool_strategy() == 'event'
            assert social_booking.get_pool_strategy() == 'booking'
            
            # Competition booking (primary) should have own pool
            assert competition_booking.get_effective_pool().id == competition_pool.id
            
            # Social booking should not share (booking strategy overrides series)
            assert social_booking.get_effective_pool() is None
            assert social_booking.has_effective_pool() is False
    
    def test_pool_member_count_across_strategies(self, app, db_session):
        """Test pool member counting works correctly for different strategies."""
        with app.app_context():
            from app.models import Pool, PoolRegistration
            from tests.fixtures.factories import BookingFactory, PoolFactory, MemberFactory
            
            # Create primary booking with pool and members
            primary = BookingFactory(
                event_type=2,  # Competition = 'event' strategy
                series_id='member-count-series',
                booking_date=date.today() + timedelta(days=3)
            )
            pool = PoolFactory(booking_id=primary.id)
            
            # Add members to pool
            members = [MemberFactory() for _ in range(5)]
            registrations = [
                PoolRegistration(pool_id=pool.id, member_id=member.id) 
                for member in members
            ]
            db_session.add_all(registrations)
            db_session.commit()
            
            primary.pool = pool
            
            # Create secondary booking in same series
            secondary = BookingFactory(
                event_type=2,
                series_id='member-count-series',
                booking_date=date.today() + timedelta(days=7)
            )
            db_session.commit()
            
            # Both bookings should report same member count
            assert primary.get_effective_pool_member_count() == 5
            assert secondary.get_effective_pool_member_count() == 5
            
            # Verify they're using the same pool
            assert primary.get_effective_pool().id == secondary.get_effective_pool().id
    
    def test_series_primary_booking_selection(self, app, db_session):
        """Test that primary booking selection works correctly across different dates."""
        with app.app_context():
            from tests.fixtures.factories import BookingFactory
            
            series_id = 'primary-selection-series'
            
            # Create bookings on different dates (not in chronological order)
            booking_middle = BookingFactory(
                series_id=series_id,
                booking_date=date.today() + timedelta(days=5)
            )
            booking_latest = BookingFactory(
                series_id=series_id,
                booking_date=date.today() + timedelta(days=10)
            )
            booking_earliest = BookingFactory(
                series_id=series_id,
                booking_date=date.today() + timedelta(days=2)
            )
            db_session.commit()
            
            # Earliest booking should be primary
            assert booking_earliest.is_primary_booking_in_series() is True
            assert booking_middle.is_primary_booking_in_series() is False
            assert booking_latest.is_primary_booking_in_series() is False
            
            # Verify primary booking retrieval
            from app.bookings.utils import get_primary_booking_in_series
            primary = get_primary_booking_in_series(series_id)
            assert primary.id == booking_earliest.id
    
    def test_edge_case_empty_series_handling(self, app, db_session):
        """Test handling of edge cases with empty or invalid series."""
        with app.app_context():
            from tests.fixtures.factories import BookingFactory
            from app.bookings.utils import get_primary_booking_in_series, get_effective_pool_for_booking
            
            # Test booking with no series_id
            standalone_booking = BookingFactory(series_id=None)
            db_session.commit()
            
            assert standalone_booking.is_primary_booking_in_series() is True
            assert get_effective_pool_for_booking(standalone_booking) is None
            
            # Test non-existent series
            assert get_primary_booking_in_series('nonexistent-series') is None
            assert get_primary_booking_in_series('') is None
            assert get_primary_booking_in_series(None) is None
    
    def test_unknown_event_type_default_handling(self, app, db_session):
        """Test that unknown event types default to 'booking' strategy."""
        with app.app_context():
            from app.models import Pool
            from tests.fixtures.factories import BookingFactory, PoolFactory
            
            # Create booking with unknown event type
            original = BookingFactory(event_type=999, has_pool=True)  # Unknown type
            pool = PoolFactory(booking_id=original.id)
            db_session.commit()
            original.pool = pool
            
            # Should default to 'booking' strategy
            assert original.get_pool_strategy() == 'booking'
            
            # Duplication should create new pool (booking strategy behavior)
            duplicate = BookingFactory(event_type=999)
            db_session.commit()
            
            from app.bookings.utils import should_create_pool_for_duplication
            should_create, reason = should_create_pool_for_duplication(original, duplicate)
            assert should_create is True