# Specialist Events Blueprint Implementation Plan

## Overview

This document provides a complete roadmap for implementing specialized event type blueprints (leagues, competitions, social events) that extend the base events blueprint functionality. The base events blueprint has been successfully implemented and is working at `/events/`.

## Current Architecture Status

### ✅ **Completed Foundation**

**Base Events Blueprint (`app/events/`):**
- ✅ Blueprint registered at `/events/` URL prefix
- ✅ Template folder configured correctly
- ✅ Core routes: `/list`, `/create`, `/manage/<id>`, `/delete/<id>`
- ✅ Forms: `EventForm`, `EventSelectionForm`, `EventManagerAssignmentForm`
- ✅ Utilities: Statistics, permissions, event creation helpers
- ✅ Templates: `list_events.html`, `create_event.html`
- ✅ Integration with existing Team and Booking models
- ✅ **NO EventTeam functionality** (deliberately excluded per requirements)

**Team-Event Integration Fixed:**
- ✅ `teams/routes.py` now uses `booking.event.format` (not `event.event_format`)
- ✅ Position assignment works with `TEAM_POSITIONS` config
- ✅ Missing `create_team.html` template created and working

**Event Model Structure:**
```python
class Event(db.Model):
    id: int
    name: str
    event_type: int          # Maps to EVENT_TYPES config
    gender: int             # Maps to EVENT_GENDERS config  
    format: int             # Maps to EVENT_FORMATS config
    scoring: Optional[str]
    has_pool: bool
    # Relationships:
    bookings: list[Booking]
    pool: Optional[EventPool]
    event_managers: list[Member]
```

## Recommended Hybrid Architecture

### **Philosophy: Type-Specific Blueprints with Shared Base**

Following the successful pattern of the rollups blueprint, create specialized blueprints for complex event types while maintaining shared functionality in the base events blueprint.

### **Blueprint Structure**

```
app/
├── events/              # ✅ Base functionality (COMPLETE)
│   ├── routes.py        # Generic event CRUD
│   ├── forms.py         # Shared forms
│   ├── utils.py         # Common utilities
│   └── templates/       # Base templates
├── leagues/             # 🚧 League-specific functionality (TODO)
│   ├── routes.py        # Fixtures, standings, seasons
│   ├── forms.py         # League forms
│   ├── models.py        # League extensions
│   └── templates/       # League templates
├── competitions/        # 🚧 Competition-specific functionality (TODO)
│   ├── routes.py        # Brackets, elimination
│   ├── forms.py         # Competition forms
│   ├── models.py        # Competition extensions
│   └── templates/       # Competition templates
├── social_events/       # 🚧 Simple social events (TODO)
│   ├── routes.py        # Basic event management
│   └── templates/       # Social event templates
└── rollups/            # ✅ Keep existing (WORKING)
    └── (existing)
```

### **Event Type Mapping**

```python
# From config.py EVENT_TYPES
EVENT_TYPE_BLUEPRINTS = {
    1: 'social_events',    # Social events
    2: 'competitions',     # Competition events  
    3: 'leagues',          # League events
    4: 'social_events',    # Friendly events (use social)
    5: 'rollups',          # Roll Up events (existing blueprint)
    6: 'social_events',    # Other events (use social)
}
```

## Implementation Roadmap

### **Phase 1: Social Events Blueprint** (Simplest - Start Here)

**Scope:** Handle basic social events and friendlies without complex features.

**Files to Create:**
```
app/social_events/
├── __init__.py
├── routes.py
├── forms.py  
└── templates/
    ├── create_social_event.html
    ├── manage_social_event.html
    └── list_social_events.html
```

**Key Routes:**
- `/social_events/create` - Simple event creation
- `/social_events/manage/<id>` - Basic event management
- `/social_events/list` - List social events

**Blueprint Registration:**
```python
# In app/__init__.py
from app.social_events import bp as social_events_bp
app.register_blueprint(social_events_bp, url_prefix='/social_events')
```

### **Phase 2: Leagues Blueprint** (Most Complex)

**Scope:** League management with seasons, fixtures, standings, and team assignments.

**Extended Models Needed:**
```python
class LeagueSeason(db.Model):
    id: int
    event_id: int  # Links to base Event
    season_name: str
    start_date: date
    end_date: date
    is_active: bool

class LeagueFixture(db.Model):
    id: int
    season_id: int
    home_team: str
    away_team: str  
    fixture_date: date
    venue: str
    result: Optional[str]

class LeagueStanding(db.Model):
    id: int
    season_id: int
    team_name: str
    points: int
    games_played: int
    games_won: int
    games_lost: int
```

**Key Features:**
- Season management
- Fixture generation and scheduling
- Results entry and standings calculation
- Team registration and management
- League table generation

### **Phase 3: Competitions Blueprint** (Complex)

**Scope:** Tournament-style competitions with brackets, eliminations, and progression.

**Extended Models Needed:**
```python
class CompetitionBracket(db.Model):
    id: int
    event_id: int
    bracket_type: str  # 'single_elimination', 'double_elimination', 'round_robin'
    max_participants: int

class CompetitionMatch(db.Model):
    id: int
    bracket_id: int
    round_number: int
    match_number: int
    participant1: str
    participant2: str
    winner: Optional[str]
    match_date: Optional[date]

class CompetitionParticipant(db.Model):
    id: int
    bracket_id: int
    participant_name: str
    seeding: Optional[int]
    eliminated: bool
```

**Key Features:**
- Bracket generation (single/double elimination, round-robin)
- Match scheduling and result entry
- Automatic progression and elimination
- Seeding management
- Tournament tree visualization

## Implementation Guidelines

### **Blueprint Creation Pattern**

Follow the established pattern from rollups and teams blueprints:

**1. Blueprint Structure (`__init__.py`):**
```python
from flask import Blueprint

bp = Blueprint('blueprint_name', __name__, 
               url_prefix='/blueprint_name', 
               template_folder='templates')

from app.blueprint_name import routes
```

**2. Route Security:**
```python
@bp.route('/route')
@login_required
@role_required('Event Manager')
def route_function():
    # Route implementation
```

**3. Template Organization:**
- Templates in `blueprint/templates/` folder
- Use `render_template('template_name.html')` (no subdirectories)
- Extend `base.html` and follow Bulma CSS patterns

**4. Database Integration:**
- Use existing Event model as base
- Create extension models for specialized functionality
- Maintain foreign key relationships to Event table
- Follow audit logging requirements for all database operations

### **Integration Points**

**1. Event Type Routing:**
```python
# In events/utils.py (already implemented)
def get_event_type_blueprint(event_type: int) -> str:
    blueprint_mapping = {
        3: 'leagues',
        2: 'competitions', 
        1: 'social_events',
        4: 'social_events',
        5: 'rollups',
        6: 'social_events',
    }
    return blueprint_mapping.get(event_type, 'social_events')
```

**2. Cross-Blueprint Navigation:**
```python
# Redirect from base events to specialist blueprint
@bp.route('/manage/<int:event_id>')
def manage_event(event_id):
    event = db.session.get(Event, event_id)
    specialist_blueprint = get_event_type_blueprint(event.event_type)
    
    if specialist_blueprint != 'events':
        return redirect(url_for(f'{specialist_blueprint}.manage_event', event_id=event_id))
    
    # Handle in base blueprint
```

**3. Shared Utilities:**
- Use `events/utils.py` functions across all blueprints
- `can_user_manage_event()`, `get_event_statistics()`, etc.
- Extend base utilities as needed for specialized features

### **Database Schema Considerations**

**Existing Schema (DO NOT MODIFY):**
- Event table with integer fields for type, format, gender
- Booking table linked to events
- Team table linked to bookings (NOT events)
- No EventTeam functionality

**Extension Pattern:**
- Create new tables that reference Event.id
- Do NOT modify existing core tables
- Use proper foreign key constraints
- Follow existing naming conventions

### **Configuration Integration**

**Use Existing Config:**
```python
# From config.py
EVENT_TYPES = {
    "Social": 1,
    "Competition": 2, 
    "League": 3,
    "Friendly": 4,
    "Roll Up": 5,
    "Other": 6
}

EVENT_FORMATS = {
    "Singles": 1,
    "Pairs": 2,
    "Triples": 3, 
    "Fours - 4 Wood": 4,
    "Fours - 2 Wood": 5
}

TEAM_POSITIONS = {
    1: ["Player"],  # Singles
    2: ["Lead", "Skip"],  # Pairs
    3: ["Lead", "Second", "Skip"],  # Triples
    4: ["Lead", "Second", "Third", "Skip"],  # Fours
    5: ["Lead", "Second", "Third", "Skip"]   # Fours - 2 Wood
}
```

**Add Specialist Config:**
```python
# League-specific configuration
LEAGUE_POINT_SYSTEMS = {
    'win_loss': {'win': 2, 'loss': 0, 'draw': 1},
    'percentage': {'calculation': 'shots_for / (shots_for + shots_against)'}
}

# Competition bracket types
COMPETITION_FORMATS = {
    'single_elimination': 'Single Elimination',
    'double_elimination': 'Double Elimination', 
    'round_robin': 'Round Robin',
    'swiss': 'Swiss System'
}
```

## Security & Audit Requirements

### **Authentication & Authorization**
- All routes require `@login_required`
- Management routes require `@role_required('Event Manager')` 
- Use `can_user_manage_event()` for specific event permissions
- Event managers can only manage events they're assigned to (unless admin)

### **Audit Logging** (CRITICAL)
Every database operation must include audit logging:

```python
from app.audit import audit_log_create, audit_log_update, audit_log_delete

# Example patterns
audit_log_create('LeagueSeason', season.id, f'Created season: {season.season_name}')
audit_log_update('CompetitionMatch', match.id, f'Updated match result', changes_dict)
audit_log_delete('LeagueFixture', fixture_id, f'Deleted fixture: {fixture_info}')
```

### **CSRF Protection**
- All forms must include `{{ form.hidden_tag() }}`
- POST routes must validate CSRF tokens
- Use `FlaskForm()` for manual CSRF validation

## Testing Strategy

### **Test Structure**
Follow the pattern established in `tests/integration/test_team_routes.py`:

```
tests/integration/
├── test_social_events_routes.py
├── test_leagues_routes.py
└── test_competitions_routes.py
```

### **Test Categories**
1. **Authentication & Authorization Tests**
   - Login requirements
   - Role requirements  
   - Permission boundaries

2. **CRUD Operation Tests**
   - Create, read, update, delete functionality
   - Form validation
   - Database integrity

3. **Integration Tests**
   - Cross-blueprint navigation
   - Event type routing
   - Team assignment functionality

4. **Business Logic Tests**
   - League standings calculations
   - Competition bracket generation
   - Match progression logic

## Migration Strategy

### **Backward Compatibility (CRITICAL)**
- All existing URLs must continue to work
- No breaking changes to existing functionality
- Admin routes should gradually redirect to new blueprints
- Maintain database schema compatibility

### **Gradual Migration Steps**

**Step 1:** Implement social_events blueprint
- Handle simple social events and friendlies
- Test thoroughly with existing functionality
- Ensure no regressions

**Step 2:** Create URL routing layer
- Implement automatic routing based on event type
- Add redirects from base events to specialist blueprints
- Maintain admin route compatibility

**Step 3:** Implement leagues blueprint
- Add complex league functionality
- Migrate existing league events gradually
- Test standing calculations and fixture management

**Step 4:** Implement competitions blueprint  
- Add tournament bracket functionality
- Test elimination and progression logic
- Handle complex competition formats

**Step 5:** Cleanup and optimization
- Remove redundant admin routes
- Optimize cross-blueprint integration
- Performance testing and optimization

## Current Implementation Status

### **✅ Completed (Working in Production)**
1. Base events blueprint (`/events/`)
2. Team-event integration fixes
3. Template rendering system
4. Event statistics without EventTeam dependencies
5. Blueprint registration and routing

### **🚧 Next Immediate Steps**
1. Create social_events blueprint (simplest starting point)
2. Implement event type routing in base events blueprint
3. Test cross-blueprint navigation
4. Add redirect mechanisms for backward compatibility

### **📋 Future Development Queue**
1. Leagues blueprint with full season management
2. Competitions blueprint with bracket generation
3. Advanced reporting and analytics
4. Mobile-responsive improvements
5. API endpoints for specialist functionality

## Key Implementation Notes

### **Critical Decisions Made**
- **No EventTeam functionality** - Teams are managed at booking level only
- **Hybrid architecture** - Specialized blueprints with shared base
- **Integer-based configuration** - Event types, formats, genders use integer IDs
- **Backward compatibility maintained** - All existing URLs and functionality preserved

### **Technical Debt to Address**
- Deprecation warnings for `datetime.utcnow()` - should use `datetime.now(datetime.UTC)`
- Missing pytest markers - register `@pytest.mark.integration` properly
- Template path inconsistencies - some templates use subdirectories, others don't

### **Performance Considerations**
- Event statistics calculation can be expensive with many bookings/teams
- Consider caching for frequently accessed league standings
- Database indexes may be needed for specialist queries
- Bulk operations should use audit_log_bulk_operation()

## Reference Information

### **Key Files and Locations**
- Base events blueprint: `app/events/`
- Configuration: `config.py` EVENT_TYPES, EVENT_FORMATS, TEAM_POSITIONS
- Team integration: `app/teams/routes.py` lines 54-56, 276-279
- Blueprint registration: `app/__init__.py` lines 239, 249
- Audit logging: `app/audit.py`
- Test examples: `tests/integration/test_team_routes.py`

### **Working Examples to Follow**
- Rollups blueprint: `app/rollups/` - Simple, focused functionality
- Teams blueprint: `app/teams/` - Medium complexity with member management
- Bookings blueprint: `app/bookings/` - Integration with multiple systems

### **Configuration Values**
```python
EVENT_TYPES = {"Social": 1, "Competition": 2, "League": 3, "Friendly": 4, "Roll Up": 5, "Other": 6}
EVENT_FORMATS = {"Singles": 1, "Pairs": 2, "Triples": 3, "Fours - 4 Wood": 4, "Fours - 2 Wood": 5}
TEAM_POSITIONS = {1: ["Player"], 2: ["Lead", "Skip"], 3: ["Lead", "Second", "Skip"], 4: ["Lead", "Second", "Third", "Skip"], 5: ["Lead", "Second", "Third", "Skip"]}
```

---

## Summary

This plan provides everything needed to implement specialized event blueprints while maintaining the successful architecture patterns already established. The foundation is solid, tested, and ready for extension. Start with social_events blueprint as the simplest implementation to validate the architecture, then proceed to the more complex leagues and competitions blueprints.

**The key to success:** Follow the established patterns, maintain backward compatibility, and implement comprehensive testing at each step.