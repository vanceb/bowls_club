# Team Management System - Design Decisions

## Overview
This document captures the design decisions made for implementing the team management functionality in the Bowls Club application. The system allows event organizers to create teams for events and manage player assignments and availability.

## Core Requirements
- **Event-specific teams**: Teams are created for each event with configurable size based on format
- **Booking team instances**: When bookings are created, teams are copied allowing substitutions without affecting event templates
- **Player availability confirmation**: Players can confirm availability but cannot unconfirm (one-way process)
- **Substitution management**: Event managers can make substitutions with audit trail
- **Player dashboard**: Players see all upcoming commitments across events

## Data Model Architecture

### 1. Team Structure & Composition
**Decision**: Teams are event-specific with format-driven sizing
- Team size automatically determined by event format:
  - Singles = 1 player
  - Pairs = 2 players (Lead, Skip)
  - Triples = 3 players (Lead, Second, Skip)
  - Fours = 4 players (Lead, Second, Third, Skip)
- Teams have positional roles based on bowls traditions
- Each event can have multiple teams (Team A, Team B, etc.)

**Rationale**: This approach ensures consistency with bowls game formats while providing flexibility for different event types.

### 2. Database Models
**Decision**: Four main entities with clear separation of concerns

#### EventTeam Model
- **Purpose**: Template teams created when setting up an event
- **Fields**: id, event_id, team_name, team_number, created_at
- **Relationships**: 
  - Many-to-one with Event
  - One-to-many with TeamMember (positions)
  - One-to-many with BookingTeam (instances)

#### BookingTeam Model
- **Purpose**: Copied from EventTeam when booking is created, can be modified for substitutions
- **Fields**: id, booking_id, event_team_id, team_name, team_number, substitution_log, created_at
- **Relationships**:
  - Many-to-one with Booking
  - Many-to-one with EventTeam (source template)
  - One-to-many with BookingTeamMember

#### TeamMember Model
- **Purpose**: Links players to event team positions (template level)
- **Fields**: id, event_team_id, member_id, position, created_at
- **Relationships**:
  - Many-to-one with EventTeam
  - Many-to-one with Member

#### BookingTeamMember Model
- **Purpose**: Links players to specific booking team instances with availability tracking
- **Fields**: id, booking_team_id, member_id, position, is_substitute, confirmed_available, confirmed_at, substituted_at, created_at
- **Relationships**:
  - Many-to-one with BookingTeam
  - Many-to-one with Member

**Rationale**: This separation allows template teams at the event level while maintaining instance-specific modifications at the booking level. The copy-on-booking approach ensures substitutions don't affect the original event teams.

### 3. Team Lifecycle
**Decision**: Event-centric team management with copy-on-booking
- Teams created during event setup by Event Managers
- Event Managers specify number of teams needed
- Teams named automatically (Team A, Team B, etc.) but can be renamed
- Teams persist with the event for the entire season/competition
- When creating bookings, all EventTeams are copied to BookingTeams
- BookingTeams can be modified (substitutions) without affecting original EventTeams

**Rationale**: This provides a clean separation between event planning and game-day logistics while maintaining data integrity.

## Configuration & Constants

### Team Positions Configuration
**Decision**: Store position definitions in application configuration
```python
TEAM_POSITIONS = {
    1: ["Player"],  # Singles
    2: ["Lead", "Skip"],  # Pairs
    3: ["Lead", "Second", "Skip"],  # Triples
    4: ["Lead", "Second", "Third", "Skip"],  # Fours - 4 Wood
    5: ["Lead", "Second", "Third", "Skip"]   # Fours - 2 Wood
}

AVAILABILITY_DEADLINE_DAYS = 7  # Days before game that players must confirm availability
```

**Rationale**: Configuration-driven approach allows easy modification of team structures and business rules without code changes.

## User Interface Design

### 1. Event Creation Integration
**Decision**: Integrate team creation into existing event management workflow
- Add "Number of Teams" field to EventForm
- Teams created automatically when event is saved
- Teams displayed in event details alongside bookings
- Leverage existing event selection mechanism

**Rationale**: This maintains consistency with the existing UI patterns and keeps related functionality together.

### 2. Player Availability System
**Decision**: Confirmation-only workflow with deadline enforcement
- Players see "My Upcoming Games" page showing all BookingTeam assignments
- Players can only tick "Available" - cannot untick once confirmed
- Deadline system: players must confirm availability X days before game
- Players who don't confirm by deadline are flagged as "Needs Follow-up"

**Rationale**: One-way confirmation prevents last-minute cancellations while providing clear visibility into availability status.

### 3. Substitution Management
**Decision**: Event Manager controlled with audit trail
- Only Event Managers can make substitutions in BookingTeams
- System shows availability status when selecting substitutes
- Substitutes drawn from same event's player pool initially, but can select any eligible member
- Substitution log maintained in JSON format for audit trail

**Rationale**: This maintains proper authorization while providing flexibility and accountability.

## Permissions & Roles

### Access Control
**Decision**: Extend existing Event Manager role rather than creating new roles
- Event Managers can create/modify teams for their events
- Event Managers can make substitutions in their event bookings
- Players can view their own commitments and confirm availability
- Admins can see all teams and bookings

**Rationale**: Leverages existing role infrastructure and maintains principle of least privilege.

## Technical Implementation Details

### 1. Database Relationships
**Key Relationships**:
- Event -> EventTeam (one-to-many, cascade delete)
- EventTeam -> TeamMember (one-to-many, cascade delete)
- Booking -> BookingTeam (one-to-many, cascade delete)
- BookingTeam -> BookingTeamMember (one-to-many, cascade delete)
- EventTeam -> BookingTeam (one-to-many, reference only)

### 2. Form Design
**Dynamic Form Generation**: TeamMemberForm dynamically creates position fields based on event format
```python
for position in positions:
    field_name = f"position_{position.lower().replace(' ', '_')}"
    setattr(self, field_name, SelectField(...))
```

### 3. Business Logic Helpers
**Model Methods**:
- `EventTeam.get_team_size()`: Returns expected team size based on event format
- `EventTeam.get_available_positions()`: Returns list of positions for team
- `BookingTeam.get_team_size()` and `get_available_positions()`: Delegate to EventTeam

## User Experience Flow

### 1. Event Manager Workflow
1. Create event with basic details
2. Specify number of teams needed
3. Teams automatically created with default names
4. Assign players to team positions (optional at event level)
5. Create bookings for specific dates
6. Teams copied to booking instances
7. Manage substitutions as needed

### 2. Player Workflow
1. Receive notification of team assignment
2. View "My Games" dashboard showing upcoming commitments
3. Confirm availability for each booking by deadline
4. Contact event manager if unable to play (cannot self-cancel)

### 3. Booking Workflow
1. Event Manager creates booking for event
2. System automatically copies all event teams to booking
3. Teams can be modified for this specific booking
4. Players confirm availability
5. Event Manager handles substitutions for unavailable players

## Future Considerations

### Potential Enhancements
1. **Notification System**: Automated emails/notifications for team assignments and reminders
2. **Team Statistics**: Track player performance and participation
3. **Team Templates**: Reusable team configurations across similar events
4. **Advanced Substitution Logic**: Suggest substitutes based on position experience and availability
5. **Mobile Interface**: Simplified mobile view for availability confirmation

### Scalability Considerations
- Current design supports up to 20 teams per event
- Position definitions are extensible for new game formats
- Audit trail in JSON format allows for complex substitution tracking
- Relationship design supports efficient queries for player dashboards

## Migration Strategy

### Database Migration
- New tables: `event_teams`, `booking_teams`, `team_members`, `booking_team_members`
- Foreign key relationships with existing Event, Booking, and Member tables
- No modifications to existing table structures

### Rollout Plan
1. Deploy database schema changes
2. Update event creation workflow to include team management
3. Update booking workflow to handle team copying
4. Launch player availability dashboard
5. Add substitution management interface
6. Implement notification system (future phase)

## Success Metrics
- Event managers can create events with teams in under 5 minutes
- Players confirm availability within 48 hours of assignment
- Substitution rate reduced by 50% through better availability tracking
- Player satisfaction with visibility into upcoming commitments

---

*This document represents the comprehensive design decisions for the team management system as of the initial implementation. Updates should be made as the system evolves and new requirements emerge.*