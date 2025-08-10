#!/usr/bin/env python3
"""
Update 90% of members to Full status
"""

from app import create_app, db
from app.models import Member
import sqlalchemy as sa
import math

def main():
    app = create_app()
    with app.app_context():
        # Get all members
        members = db.session.scalars(sa.select(Member)).all()
        total_members = len(members)
        
        print(f'Total members: {total_members}')
        
        # Calculate 90% (rounded down)
        target_full_count = int(total_members * 0.9)
        print(f'Target Full members (90%): {target_full_count}')
        
        # Count current Full members
        current_full = sum(1 for m in members if m.status == 'Full')
        print(f'Current Full members: {current_full}')
        
        # How many need to be changed?
        need_to_change = target_full_count - current_full
        print(f'Need to change {need_to_change} members from other status to Full')
        
        if need_to_change > 0:
            # Get members that are not Full
            non_full_members = [m for m in members if m.status != 'Full']
            print(f'Non-Full members available: {len(non_full_members)}')
            
            # Change the first N members to Full status
            members_to_change = non_full_members[:need_to_change]
            
            for member in members_to_change:
                print(f'Changing {member.firstname} {member.lastname} from {member.status} to Full')
                member.status = 'Full'
            
            # Commit the changes
            db.session.commit()
            
            print(f'Successfully updated {len(members_to_change)} members to Full status')
            
            # Verify the results
            updated_members = db.session.scalars(sa.select(Member)).all()
            status_counts = {}
            for member in updated_members:
                status = member.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print('\nFinal status distribution:')
            for status, count in status_counts.items():
                percentage = (count / total_members) * 100
                print(f'  {status}: {count} ({percentage:.1f}%)')
        else:
            print('No changes needed - already have enough Full members')

if __name__ == '__main__':
    main()