# BOOKING WITH POOLS IMPLEMENTATION PLAN

## Overview
This document outlines a staged approach to redesign and implement the Event/Bookings system with Pool registration functionality. The current system is complex, incomplete, and has database inconsistencies that need to be resolved.

## Current State Analysis

### ❌ Problems Identified:
1. **Database Inconsistency**: Tables exist (`event_pools`, `pool_members`) without corresponding models
2. **Broken Functionality**: Event team editing loses all data, booking creation fails
3. **Missing Pool Workflow**: User registration interest system not implemented
4. **Complex Architecture**: Overly complex relationships between Events, Teams, Bookings
5. **Incomplete UI**: No "Upcoming Events" menu or registration interface

### ✅ Working Components:
- Basic Event creation and management
- Member management and authentication
- Role-based access control
- Template system and blueprints

## Target Workflow

### 1. Event Lifecycle
```
Event Created (Open) → User Registration → Event Closed → Team Creation → Booking Creation
```

### 2. User Experience
- **My Games → Upcoming Events**: See open events, register interest
- **Registration Status**: Track user's registration in events
- **Event Visibility**: Only show closed events to registered users

### 3. Event Manager Workflow
- Create events (default: Open for Registration)
- Manage event status (Open/Closed)
- Create teams from registered pool
- Add additional members to pool if needed
- Create bookings that copy team templates

---

## STAGE 1: DATABASE CLEANUP AND MODEL REDESIGN

### Objectives:
- Remove database inconsistencies
- Create clean, simplified model structure
- Implement proper Pool functionality models

### Tasks:

#### 1.1 Database Schema Analysis
- [ ] Document all existing tables and their purposes
- [ ] Identify tables without backing models
- [ ] Map current relationships and dependencies
- [ ] Design simplified schema

#### 1.2 Model Redesign
- [ ] Create new simplified models:
  - `Event` (simplified)
  - `EventPool` (new)
  - `PoolRegistration` (new)
  - `EventTeam` (simplified)
  - `Booking` (simplified) 
  - `BookingTeam` (simplified)

#### 1.3 Database Rebuild
- [ ] Create migration to drop problematic tables
- [ ] Create fresh migration with new schema
- [ ] Implement data preservation strategy for critical data
- [ ] Create backup and restore procedures

#### 1.4 Model Implementation
```python
class Event(db.Model):
    # Core event information
    id, name, event_type, gender, format, scoring
    registration_status = 'open'|'closed'  # Simplified status
    created_at, closed_at
    
    # Relationships
    pool = relationship('EventPool', uselist=False, cascade='all, delete-orphan')
    event_teams = relationship('EventTeam', cascade='all, delete-orphan')
    bookings = relationship('Booking', cascade='all, delete-orphan')

class EventPool(db.Model):
    # Pool for member registrations
    id, event_id
    is_open, auto_close_date
    created_at, closed_at
    
    # Relationships
    registrations = relationship('PoolRegistration', cascade='all, delete-orphan')

class PoolRegistration(db.Model):
    # Member registration in event pool
    id, pool_id, member_id
    status = 'registered'|'withdrawn'
    registered_at, withdrawn_at
    
    # Relationships
    pool = relationship('EventPool')
    member = relationship('Member')
```

#### 1.5 Migration Strategy
- [ ] Create backup of current database
- [ ] Drop inconsistent tables: `event_pools`, `pool_members`
- [ ] Recreate with proper model backing
- [ ] Migrate essential data (events, members, roles)
- [ ] Verify database integrity

**Deliverables:**
- Clean database schema
- Simplified model structure
- Working migrations
- Data preservation for critical entities

---

## STAGE 2: POOL FUNCTIONALITY IMPLEMENTATION

### Objectives:
- Implement user registration system
- Create "Upcoming Events" interface
- Build pool management for Event Managers

### Tasks:

#### 2.1 User Registration System
- [ ] Create pool registration forms
- [ ] Implement registration/withdrawal logic
- [ ] Add validation and error handling
- [ ] Create audit logging for registrations

#### 2.2 "Upcoming Events" Interface
- [ ] Add "Upcoming Events" to "My Games" menu
- [ ] Create upcoming events template
- [ ] Show registration status for each event
- [ ] Implement register/withdraw functionality
- [ ] Handle event visibility based on registration

#### 2.3 Event Manager Pool Management
- [ ] Pool overview in event management
- [ ] List of registered members
- [ ] Add members to pool manually
- [ ] Registration statistics and reporting
- [ ] Pool closure management

#### 2.4 API Endpoints
- [ ] `/api/events/upcoming` - Get open events for user
- [ ] `/api/events/{id}/register` - Register interest
- [ ] `/api/events/{id}/withdraw` - Withdraw registration
- [ ] `/api/events/{id}/pool` - Get pool members (Event Manager)

**Deliverables:**
- Working user registration system
- "Upcoming Events" menu and interface
- Pool management tools for Event Managers
- Complete API for registration workflow

---

## STAGE 3: EVENT MANAGEMENT REDESIGN

### Objectives:
- Simplify event creation and management
- Fix broken event status management
- Implement proper event lifecycle

### Tasks:

#### 3.1 Event Creation Simplification
- [ ] Streamline event creation form
- [ ] Default to "Open for Registration"
- [ ] Remove complex nested forms
- [ ] Add event status management

#### 3.2 Event Status Management
- [ ] Implement Open/Closed status toggle
- [ ] Auto-close functionality with date
- [ ] Status change validation and notifications
- [ ] Audit logging for status changes

#### 3.3 Event Overview Dashboard
- [ ] Event status at-a-glance
- [ ] Registration statistics
- [ ] Quick actions (close, manage teams, create bookings)
- [ ] Event timeline view

#### 3.4 Event Manager Permissions
- [ ] Verify Event Manager role functionality
- [ ] Implement proper access controls
- [ ] Event assignment to managers
- [ ] Manager notifications and alerts

**Deliverables:**
- Simplified event management interface
- Working event status system
- Event Manager dashboard
- Proper permission controls

---

## STAGE 4: TEAM CREATION FROM POOLS

### Objectives:
- Fix team creation/editing data loss
- Implement team creation from pool
- Simplify team management interface

### Tasks:

#### 4.1 Fix Team Editing Data Loss
- [ ] Identify and fix delete-all-before-save issue
- [ ] Implement proper update logic
- [ ] Add form validation and error handling
- [ ] Create team editing transaction safety

#### 4.2 Team Creation from Pool
- [ ] Pool-to-team assignment interface
- [ ] Drag-and-drop or selection-based team building
- [ ] Position assignment from pool members
- [ ] Team validation (complete/incomplete)

#### 4.3 Team Management Simplification
- [ ] Single-page team management interface
- [ ] Real-time team composition updates
- [ ] Team member substitution preview
- [ ] Team readiness indicators

#### 4.4 Pool Member Addition
- [ ] Add non-registered members to pool
- [ ] Member search and selection
- [ ] Bulk member addition
- [ ] Pool member status management

**Deliverables:**
- Fixed team editing without data loss
- Pool-based team creation system
- Simplified team management interface
- Ability to add members to pools

---

## STAGE 5: BOOKING SYSTEM REDESIGN

### Objectives:
- Simplify booking creation
- Implement team template copying
- Fix booking form validation issues

### Tasks:

#### 5.1 Booking Creation Simplification
- [ ] Single-step booking creation
- [ ] Event team template selection
- [ ] Automatic team copying on booking creation
- [ ] Booking validation and conflict checking

#### 5.2 Team Template System
- [ ] Copy Event Teams to Booking Teams
- [ ] Maintain link to original templates
- [ ] Independent booking team modifications
- [ ] Template vs instance differentiation

#### 5.3 Booking Management Interface
- [ ] Booking overview with teams
- [ ] Individual booking team management
- [ ] Substitution management per booking
- [ ] Booking status and readiness indicators

#### 5.4 Booking Validation
- [ ] Date/time conflict checking
- [ ] Rink availability validation
- [ ] Team completeness validation
- [ ] Form error handling and user feedback

**Deliverables:**
- Working booking creation system
- Team template copying functionality
- Simplified booking management
- Robust validation and error handling

---

## STAGE 6: USER INTERFACE INTEGRATION

### Objectives:
- Integrate all functionality into cohesive interface
- Create intuitive user workflows
- Implement responsive design

### Tasks:

#### 6.1 Navigation Integration
- [ ] Add "Upcoming Events" to My Games menu
- [ ] Update Event Manager navigation
- [ ] Breadcrumb navigation for complex workflows
- [ ] Mobile-responsive menu design

#### 6.2 Dashboard Creation
- [ ] User dashboard with registered events
- [ ] Event Manager dashboard with event overview
- [ ] Admin dashboard with system overview
- [ ] Status indicators and notifications

#### 6.3 Workflow Optimization
- [ ] Streamline user registration flow
- [ ] Optimize Event Manager workflows
- [ ] Reduce clicks and form complexity
- [ ] Add helpful tooltips and guidance

#### 6.4 Notification System
- [ ] Registration confirmations
- [ ] Event status change notifications
- [ ] Team assignment notifications
- [ ] Booking creation alerts

**Deliverables:**
- Integrated user interface
- Comprehensive dashboards
- Optimized user workflows
- Working notification system

---

## STAGE 7: TESTING AND VALIDATION

### Objectives:
- Comprehensive testing of all functionality
- Performance optimization
- User acceptance testing

### Tasks:

#### 7.1 Unit Testing
- [ ] Model validation tests
- [ ] Form submission tests
- [ ] API endpoint tests
- [ ] Database integrity tests

#### 7.2 Integration Testing
- [ ] End-to-end workflow tests
- [ ] Cross-browser compatibility
- [ ] Mobile device testing
- [ ] Performance testing

#### 7.3 User Acceptance Testing
- [ ] Event Manager workflow testing
- [ ] Member registration testing
- [ ] Booking creation testing
- [ ] Error handling validation

#### 7.4 Performance Optimization
- [ ] Database query optimization
- [ ] Front-end performance tuning
- [ ] Caching strategy implementation
- [ ] Load testing and optimization

**Deliverables:**
- Comprehensive test suite
- Performance benchmarks
- User acceptance validation
- Production-ready system

---

## Implementation Guidelines

### Development Approach:
1. **One Stage at a Time**: Complete each stage fully before moving to next
2. **Test Early**: Test each component as it's built
3. **Backup First**: Always backup before major changes
4. **Document Changes**: Update this plan as issues are discovered
5. **User Feedback**: Involve Event Managers in testing each stage

### Risk Management:
- **Database Backup**: Full backup before Stage 1
- **Rollback Plan**: Ability to restore previous version
- **Incremental Deployment**: Test each stage in development first
- **User Communication**: Inform users of planned changes and downtime

### Success Criteria:
- [ ] Users can register for open events
- [ ] Event Managers can create teams from pools
- [ ] Bookings are created with team templates
- [ ] No data loss during team editing
- [ ] All workflows are intuitive and fast
- [ ] System is stable and performant

---

## Technical Notes

### Database Cleanup Commands:
```sql
-- Backup current database
.backup main backup.db

-- Drop inconsistent tables
DROP TABLE IF EXISTS event_pools;
DROP TABLE IF EXISTS pool_members;

-- Recreate with proper model backing via migrations
```

### Key Files to Modify:
- `app/models.py` - New simplified models
- `app/admin/routes.py` - Event management routes
- `app/main/routes.py` - User registration routes
- `app/api/routes.py` - API endpoints
- `migrations/` - Database schema changes
- Templates in `app/*/templates/` - User interfaces

### Configuration Updates:
```python
# config.py additions
POOL_REGISTRATION_ENABLED = True
AUTO_CLOSE_POOL_DAYS = 7
MAX_POOL_REGISTRATIONS = 50
```

---

*This plan serves as a living document and should be updated as implementation progresses and issues are discovered.*