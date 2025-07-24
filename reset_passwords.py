#!/usr/bin/env python3

import os
from dotenv import load_dotenv

# Load environment variables from .flaskenv
load_dotenv('.flaskenv')

from app import create_app, db
from app.models import Member
import sqlalchemy as sa
from app.audit import audit_log_update

def reset_member_passwords():
    app = create_app()
    
    # List of members to update
    member_names = [
        ('Kenneth', 'Adams'),
        ('Amy', 'Allen'), 
        ('Stephanie', 'Anderson'),
        ('Helen', 'Bailey'),
        ('Melissa', 'Baker'),
        ('Eugene', 'Barnes'),
        ('Frank', 'Bell'),
        ('Arthur', 'Bennett')
    ]

    with app.app_context():
        updated_count = 0
        not_found = []
        
        for firstname, lastname in member_names:
            # Find member by first and last name
            member = db.session.scalar(
                sa.select(Member).where(
                    sa.and_(
                        Member.firstname == firstname,
                        Member.lastname == lastname
                    )
                )
            )
            
            if member:
                # Set simple password 'a' directly (bypassing complexity)
                member.set_password('a')
                updated_count += 1
                
                print(f'✅ Updated password for {firstname} {lastname} (ID: {member.id})')
            else:
                not_found.append(f'{firstname} {lastname}')
                print(f'❌ Could not find member: {firstname} {lastname}')
        
        if updated_count > 0:
            db.session.commit()
            
            # Manual audit logging for system operation
            from app.audit import write_audit_log
            for firstname, lastname in member_names:
                member = db.session.scalar(
                    sa.select(Member).where(
                        sa.and_(
                            Member.firstname == firstname,
                            Member.lastname == lastname
                        )
                    )
                )
                if member:
                    write_audit_log('UPDATE', 'Member', member.id, 
                                  f'Reset password to simple test password for {firstname} {lastname}',
                                  'System', 'system-script')
            
            print(f'\n🎉 Successfully updated passwords for {updated_count} members')
        
        if not_found:
            print(f'\n⚠️  Members not found: {', '.join(not_found)}')
        
        print(f'\nAll specified members now have password: a')

if __name__ == '__main__':
    reset_member_passwords()